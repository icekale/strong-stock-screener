from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import Mock

import httpx
import pytest
from pydantic import ValidationError

from app.models import (
    SentimentAnalysisResult,
    SentimentDecisionResponse,
    SentimentMainSectorSignal,
    SentimentPercentileAnalysisResponse,
    SentimentPercentileFactor,
    SentimentPercentileFactors,
    SentimentPercentilePoint,
    SentimentSummaryMetrics,
    SentimentSummaryResponse,
    ShortTermSentimentIndustryItem,
)
from app.services.market_sentiment_analysis import (
    MarketSentimentAnalysisService,
    _prompt_input_payload,
    _streaming_chat_payload,
    build_sentiment_analysis_input,
    hash_sentiment_analysis_input,
    sentiment_analysis_record_is_reusable,
)
from app.services.market_sentiment_analysis_store import MarketSentimentAnalysisStore
from app.services.runtime_settings import EffectiveAiAnalysisSettings


def _point(
    trade_date: str = "2026-07-22",
    score: float = 62.0,
    level: str = "偏热",
) -> SentimentPercentilePoint:
    factor = SentimentPercentileFactor(score=60.0, raw_value=2.5, raw_unit="%")
    return SentimentPercentilePoint(
        trade_date=trade_date,
        score=score,
        level=level,  # type: ignore[arg-type]
        factors=SentimentPercentileFactors(
            volume=factor.model_copy(update={"raw_value": 123_000_000, "raw_unit": "CNY"}),
            index_move_5d=factor,
            price_position=factor.model_copy(update={"raw_value": 64.0}),
            amplitude_5d=factor.model_copy(update={"raw_value": 3.6}),
            volume_trend=factor.model_copy(update={"raw_value": 1.2}),
        ),
    )


def _summary() -> SentimentSummaryResponse:
    return SentimentSummaryResponse(
        trade_date="2026-07-22",
        metrics=SentimentSummaryMetrics(
            advance_count=3_012,
            decline_count=1_845,
            limit_up_count=68,
            limit_down_count=9,
            break_board_count=17,
            max_consecutive_boards=5,
            seal_rate_pct=71.5,
            turnover_cny=1_250_000_000_000,
        ),
        hot_industries=[
            ShortTermSentimentIndustryItem(
                name="存储芯片",
                strength_score=92,
                limit_up_count=11,
                break_board_count=2,
                max_consecutive_boards=4,
                leader="示例个股",
                symbols=["300001.SZ"],
            )
        ],
    )


def _decision() -> SentimentDecisionResponse:
    return SentimentDecisionResponse(
        trade_date="2026-07-22",
        market_state="修复",
        trade_permission="轻仓试错",
        risk_level="中",
        score_change=8.5,
        main_sectors=[
            SentimentMainSectorSignal(
                name="存储芯片",
                strength_score=92,
                limit_up_count=11,
                break_board_count=2,
                max_consecutive_boards=4,
                leader="示例个股",
                symbols=["300001.SZ"],
            )
        ],
    )


def _validation() -> dict[str, object]:
    return {
        "data_end": "2026-07-21",
        "conclusion": "Walk-forward metrics are descriptive.",
        "samples": [{"trade_date": "2026-07-21", "unrelated": "must not leak"}],
        "buckets": [
            {"level": "偏热", "sample_count": 37, "windows": [{"sample_count": 12}]},
            {"level": "中性", "sample_count": 42, "windows": [{"sample_count": 15}]},
        ],
        "notes": ["must not leak"],
    }


def _input_payload() -> dict[str, object]:
    return build_sentiment_analysis_input(
        _point(),
        [
            _point("2026-07-14", 47.0, "中性"),
            _point("2026-07-15", 49.0, "中性"),
            _point("2026-07-16", 50.0, "中性"),
            _point("2026-07-17", 52.0, "中性"),
            _point("2026-07-18", 54.0, "中性"),
            _point("2026-07-21", 58.0, "中性"),
            _point(),
        ],
        _summary(),
        _decision(),
        _validation(),
    )


def _config(*, model: str = "test-model", enabled: bool = True, api_key: str = "test-key") -> EffectiveAiAnalysisSettings:
    return EffectiveAiAnalysisSettings(
        enabled=enabled,
        provider="openai_compatible",
        base_url="https://ai.example/v1",
        model=model,
        api_key=api_key,
        api_key_source="runtime",
        run_after_daily_review=False,
        run_after_weekly_calibration=False,
    )


def _result_payload() -> dict[str, object]:
    return {
        "market_conclusion": "市场情绪处于偏热区间，结构仍有分化。",
        "key_drivers": ["综合分 62.0，处于偏热", "涨停 68 家且封板率 71.5%"],
        "factor_divergence": "量能趋势 1.2%，但5日涨幅仅 2.5%。",
        "historical_context": "偏热分层当前有 37 个历史样本。",
        "risk_posture": "defensive",
        "next_session_watch": ["封板率维持在 70% 以上", "跌停数量低于 10 家"],
        "risk_note": "仅作市场复盘参考，不构成投资建议。",
    }


def _compact_result_payload() -> dict[str, object]:
    result = _result_payload()
    return {
        "c": result["market_conclusion"],
        "d": result["key_drivers"],
        "v": result["factor_divergence"],
        "h": result["historical_context"],
        "p": result["risk_posture"],
        "w": result["next_session_watch"],
        "n": result["risk_note"],
    }


class _Response:
    def __init__(self, content: str) -> None:
        self.content = content

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return {"choices": [{"message": {"content": self.content}}]}


class _ReasoningOnlyResponse(_Response):
    def json(self) -> dict[str, object]:
        return {
            "choices": [
                {
                    "message": {
                        "content": "",
                        "reasoning_content": self.content,
                    }
                }
            ]
        }


class _ContentBlocksResponse(_Response):
    def json(self) -> dict[str, object]:
        return {
            "choices": [
                {
                    "message": {
                        "content": [{"type": "text", "text": self.content}],
                    }
                }
            ]
        }


class _Client:
    def __init__(self, responses: list[object]) -> None:
        self.post = Mock(side_effect=responses)


class _StreamResponse:
    def __init__(self, lines: list[str]) -> None:
        self.lines = lines

    def __enter__(self) -> "_StreamResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def raise_for_status(self) -> None:
        return None

    def iter_lines(self) -> list[str]:
        return self.lines


class _StreamClient:
    def __init__(self, lines: list[str]) -> None:
        self.response = _StreamResponse(lines)
        self.stream = Mock(return_value=self.response)


class _PendingInspectingClient:
    def __init__(self, store: MarketSentimentAnalysisStore) -> None:
        self.store = store
        self.pending_status: str | None = None
        self.post = Mock(side_effect=self._post)

    def _post(self, *_args: object, **_kwargs: object) -> _Response:
        pending = self.store.load("2026-07-22")
        self.pending_status = pending.status if pending else None
        return _Response(json.dumps(_result_payload(), ensure_ascii=False))


class _TimeoutClient:
    def __init__(self) -> None:
        self.post = Mock(side_effect=httpx.ReadTimeout("provider timed out"))


def test_input_is_allowlisted_canonical_and_hashes_sorted_json() -> None:
    payload = _input_payload()

    assert payload == {
        "trade_date": "2026-07-22",
        "percentile": {
            "score": 62.0,
            "level": "偏热",
            "weights": {
                "amplitude_5d": 0.2,
                "index_move_5d": 0.2,
                "price_position": 0.2,
                "volume": 0.2,
                "volume_trend": 0.2,
            },
            "factors": {
                "volume": {"score": 60.0, "raw_value": 123_000_000, "raw_unit": "CNY"},
                "index_move_5d": {"score": 60.0, "raw_value": 2.5, "raw_unit": "%"},
                "price_position": {"score": 60.0, "raw_value": 64.0, "raw_unit": "%"},
                "amplitude_5d": {"score": 60.0, "raw_value": 3.6, "raw_unit": "%"},
                "volume_trend": {"score": 60.0, "raw_value": 1.2, "raw_unit": "%"},
            },
        },
        "score_change_1d": 4.0,
        "score_change_5d": 13.0,
        "zone_transitions": {
            "one_day": {"from": "中性", "to": "偏热"},
            "five_day": {"from": "中性", "to": "偏热"},
        },
        "market": {
            "source_date": "2026-07-22",
            "status": "available",
            "breadth": {"advance_count": 3012, "decline_count": 1845},
            "limits": {"limit_up_count": 68, "limit_down_count": 9, "break_board_count": 17},
            "boards": {"max_consecutive_boards": 5},
            "seal_rate_pct": 71.5,
            "turnover_cny": 1_250_000_000_000,
        },
        "decision": {
            "source_date": "2026-07-22",
            "status": "available",
            "market_state": "修复",
            "trade_permission": "轻仓试错",
            "risk_level": "中",
            "score_change": 8.5,
        },
        "main_sectors": {
            "source_date": "2026-07-22",
            "status": "available",
            "items": [
                {
                    "name": "存储芯片",
                    "strength_score": 92.0,
                    "limit_up_count": 11,
                    "break_board_count": 2,
                    "max_consecutive_boards": 4,
                }
            ],
        },
        "validation": {
            "source_date": "2026-07-21",
            "status": "available",
            "sample_count": 79,
            "sample_counts": {"中性": 42, "偏热": 37},
            "conclusion": "Walk-forward metrics are descriptive.",
        },
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    assert hash_sentiment_analysis_input(payload) == hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    assert hash_sentiment_analysis_input({key: payload[key] for key in reversed(payload)}) == hash_sentiment_analysis_input(payload)


def test_exported_hash_rejects_noncanonical_input() -> None:
    payload = _input_payload()
    payload["secret"] = "must-not-leak"

    with pytest.raises(ValidationError):
        hash_sentiment_analysis_input(payload)


def test_build_rejects_sector_security_identifiers() -> None:
    sector = _decision().main_sectors[0].model_copy(update={"name": "存储芯片 300001.SZ"})
    decision = _decision().model_copy(update={"main_sectors": [sector]})

    with pytest.raises(ValidationError):
        build_sentiment_analysis_input(_point(), [_point()], _summary(), decision, _validation())


def test_input_marks_missing_auxiliary_context_explicitly() -> None:
    payload = build_sentiment_analysis_input(_point(), [_point()], None, None, None)

    assert payload["market"] == {
        "source_date": None,
        "status": "unavailable",
        "breadth": {"advance_count": None, "decline_count": None},
        "limits": {"limit_up_count": None, "limit_down_count": None, "break_board_count": None},
        "boards": {"max_consecutive_boards": None},
        "seal_rate_pct": None,
        "turnover_cny": None,
    }
    assert payload["decision"]["status"] == "unavailable"
    assert payload["main_sectors"] == {"source_date": None, "status": "unavailable", "items": []}
    assert payload["validation"] == {
        "source_date": None,
        "status": "unavailable",
        "sample_count": 0,
        "sample_counts": {},
        "conclusion": None,
    }


def test_input_marks_missing_snapshot_context_unavailable() -> None:
    missing_summary = _summary().model_copy(update={"snapshot_status": "missing"})

    payload = build_sentiment_analysis_input(_point(), [_point()], missing_summary, _decision(), None)

    assert payload["market"] == {
        "source_date": None,
        "status": "unavailable",
        "breadth": {"advance_count": None, "decline_count": None},
        "limits": {"limit_up_count": None, "limit_down_count": None, "break_board_count": None},
        "boards": {"max_consecutive_boards": None},
        "seal_rate_pct": None,
        "turnover_cny": None,
    }


def test_prompt_input_hides_trade_permission_and_risk_level_without_mutating_input() -> None:
    payload = _input_payload()

    prompt_payload = _prompt_input_payload(payload)

    assert prompt_payload["decision"] == {
        "source_date": "2026-07-22",
        "status": "available",
        "market_state": "修复",
    }
    assert payload["decision"]["trade_permission"] == "轻仓试错"
    assert payload["decision"]["risk_level"] == "中"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload.__setitem__("secret", "must-not-leak"),
        lambda payload: payload["market"].__setitem__("secret", "must-not-leak"),
        lambda payload: payload["main_sectors"]["items"][0].__setitem__("symbols", ["300001.SZ"]),
        lambda payload: payload["validation"].__setitem__("samples", []),
        lambda payload: payload["validation"]["sample_counts"].__setitem__("secret", 1),
        lambda payload: payload["main_sectors"].__setitem__(
            "items", payload["main_sectors"]["items"] * 6
        ),
    ],
)
def test_service_rejects_noncanonical_input_before_hash_or_provider_request(
    tmp_path: Path,
    mutate: object,
) -> None:
    payload = _input_payload()
    mutate(payload)  # type: ignore[operator]
    store = MarketSentimentAnalysisStore(tmp_path)
    client = _Client([])
    service = MarketSentimentAnalysisService(store, http_client=client)

    with pytest.raises(ValidationError):
        service.generate(payload, _config())

    assert client.post.call_count == 0
    assert not store.record_path("2026-07-22").exists()


def test_provider_request_sets_a_stable_user_agent(tmp_path: Path) -> None:
    client = _Client([_Response(json.dumps(_result_payload(), ensure_ascii=False))])
    service = MarketSentimentAnalysisService(MarketSentimentAnalysisStore(tmp_path), http_client=client)

    response = service.generate(_input_payload(), _config())

    assert response.status == "ready"
    assert client.post.call_args.kwargs["headers"]["User-Agent"] == "StockMaster/1.0"


def test_provider_request_accepts_reasoning_content_when_content_is_empty(tmp_path: Path) -> None:
    client = _Client([_ReasoningOnlyResponse(json.dumps(_result_payload(), ensure_ascii=False))])
    service = MarketSentimentAnalysisService(MarketSentimentAnalysisStore(tmp_path), http_client=client)

    response = service.generate(_input_payload(), _config())

    assert response.status == "ready"


def test_provider_request_accepts_text_content_blocks(tmp_path: Path) -> None:
    client = _Client([_ContentBlocksResponse(json.dumps(_result_payload(), ensure_ascii=False))])
    service = MarketSentimentAnalysisService(MarketSentimentAnalysisStore(tmp_path), http_client=client)

    response = service.generate(_input_payload(), _config())

    assert response.status == "ready"
    assert client.post.call_count == 1


def test_provider_request_maps_compact_result_keys(tmp_path: Path) -> None:
    client = _Client([_Response(json.dumps(_compact_result_payload(), ensure_ascii=False))])
    service = MarketSentimentAnalysisService(MarketSentimentAnalysisStore(tmp_path), http_client=client)

    response = service.generate(_input_payload(), _config())

    assert response.status == "ready"
    assert response.result is not None
    assert response.result.market_conclusion == _result_payload()["market_conclusion"]


@pytest.mark.parametrize("protected_field", ["score", "level", "weights", "trade_permission"])
def test_result_forbids_fields_that_could_override_deterministic_statistics(
    protected_field: str,
) -> None:
    payload = _result_payload()
    payload[protected_field] = "override"

    with pytest.raises(ValidationError):
        SentimentAnalysisResult.model_validate(payload)


def test_result_requires_numeric_driver_and_watch_evidence() -> None:
    payload = _result_payload()
    payload["key_drivers"] = ["市场较强", "结构分化"]

    with pytest.raises(ValidationError):
        SentimentAnalysisResult.model_validate(payload)


@pytest.mark.parametrize(
    "status,result,extra",
    [
        ("ready", None, {}),
        ("failed", _result_payload(), {}),
        ("pending", None, {"input_hash": None}),
        ("ready", _result_payload(), {"extra": True}),
    ],
)
def test_analysis_response_enforces_lifecycle_contract(
    status: str,
    result: object,
    extra: dict[str, object],
) -> None:
    payload: dict[str, object] = {
        "trade_date": "2026-07-22",
        "status": status,
        "input_hash": "a" * 64,
        "attempts": 1,
        "result": result,
        **extra,
    }

    with pytest.raises(ValidationError):
        SentimentPercentileAnalysisResponse.model_validate(payload)


@pytest.mark.parametrize("attempts", [-1, 4])
def test_analysis_response_bounds_attempts(attempts: int) -> None:
    with pytest.raises(ValidationError):
        SentimentPercentileAnalysisResponse.model_validate(
            {
                "trade_date": "2026-07-22",
                "status": "pending",
                "input_hash": "a" * 64,
                "attempts": attempts,
            }
        )


def test_analysis_response_forbids_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        SentimentPercentileAnalysisResponse.model_validate(
            {
                "trade_date": "2026-07-22",
                "status": "not_generated",
                "unknown": True,
            }
        )


def test_service_reuses_matching_ready_provider_model_and_hash(tmp_path: Path) -> None:
    client = _Client([_Response(json.dumps(_result_payload(), ensure_ascii=False))])
    service = MarketSentimentAnalysisService(MarketSentimentAnalysisStore(tmp_path), http_client=client)
    input_payload = _input_payload()

    response = service.generate(input_payload, _config())
    cached = service.generate(input_payload, _config())

    assert response.status == "ready"
    assert response.result is not None
    assert response.result.risk_posture == "defensive"
    assert client.post.call_count == 1
    assert cached.input_hash == response.input_hash
    assert client.post.call_count == 1
    request = client.post.call_args.kwargs["json"]
    assert request["temperature"] == 0.0
    assert request["max_tokens"] == 300
    system_prompt = request["messages"][0]["content"]
    assert "JSON" in system_prompt
    user_prompt = request["messages"][1]["content"]
    assert "短键" in user_prompt
    assert '"data"' in user_prompt


def test_llm_prompt_redacts_decision_permission_and_risk_level(tmp_path: Path) -> None:
    client = _Client([_Response(json.dumps(_result_payload(), ensure_ascii=False))])
    service = MarketSentimentAnalysisService(MarketSentimentAnalysisStore(tmp_path), http_client=client)

    response = service.generate(_input_payload(), _config())

    assert response.status == "ready"
    user_prompt = json.loads(client.post.call_args.kwargs["json"]["messages"][1]["content"])
    assert user_prompt["data"]["decision"] == {
        "source_date": "2026-07-22",
        "status": "available",
        "market_state": "修复",
    }


def test_streaming_chat_payload_stops_after_complete_content_json() -> None:
    content = json.dumps(_result_payload(), ensure_ascii=False)
    lines = [
        'data: {"choices":[{"delta":{"reasoning_content":"ignored"}}]}',
        f'data: {{"choices":[{{"delta":{{"content":{json.dumps(content[:80])}}}}}]}}',
        f'data: {{"choices":[{{"delta":{{"content":{json.dumps(content[80:])}}}}}]}}',
        "data: [DONE]",
    ]
    client = _StreamClient(lines)

    payload = _streaming_chat_payload(
        client,
        "https://ai.example/v1/chat/completions",
        headers={},
        request_json={"stream": True},
    )

    assert payload["choices"][0]["message"]["content"] == content
    assert client.stream.call_count == 1


def test_llm_request_uses_the_compact_result_contract(tmp_path: Path) -> None:
    client = _Client([_Response(json.dumps(_result_payload(), ensure_ascii=False))])
    service = MarketSentimentAnalysisService(MarketSentimentAnalysisStore(tmp_path), http_client=client)

    response = service.generate(_input_payload(), _config())

    assert response.status == "ready"
    user_prompt = client.post.call_args.kwargs["json"]["messages"][1]["content"]
    for compact_key in ("c、d、v、h、p、w、n", "短键"):
        assert compact_key in user_prompt
    for posture in ("attack", "balanced", "defensive", "wait"):
        assert posture in user_prompt
    assert "上涨家数和下跌家数" in user_prompt
    assert "禁止写任何指数或板块的涨幅" in user_prompt


def test_changed_input_or_model_generates_again(tmp_path: Path) -> None:
    client = _Client(
        [
            _Response(json.dumps(_result_payload())),
            _Response(json.dumps(_result_payload())),
            _Response(json.dumps(_result_payload())),
        ]
    )
    service = MarketSentimentAnalysisService(MarketSentimentAnalysisStore(tmp_path), http_client=client)
    input_payload = _input_payload()

    service.generate(input_payload, _config())
    service.generate({**input_payload, "score_change_1d": 3.0}, _config())
    service.generate(input_payload, _config(model="next-model"))

    assert client.post.call_count == 3


def test_pending_record_does_not_permanently_block_catchup_generation() -> None:
    payload = _input_payload()
    record = SentimentPercentileAnalysisResponse(
        trade_date="2026-07-22",
        status="pending",
        provider="openai_compatible",
        llm_model="test-model",
        input_hash=hash_sentiment_analysis_input(payload),
    )

    assert sentiment_analysis_record_is_reusable(record, payload, _config()) is False


def test_service_persists_pending_before_request_and_limits_main_sectors(tmp_path: Path) -> None:
    store = MarketSentimentAnalysisStore(tmp_path)
    client = _PendingInspectingClient(store)
    service = MarketSentimentAnalysisService(store, http_client=client)
    sector = _decision().main_sectors[0]
    decision = _decision().model_copy(update={"main_sectors": [sector] * 6})
    payload = build_sentiment_analysis_input(
        _point(),
        [_point()],
        _summary(),
        decision,
        _validation(),
    )

    response = service.generate(payload, _config())

    assert response.status == "ready"
    assert client.pending_status == "pending"
    assert len(payload["main_sectors"]["items"]) == 5
    assert all(
        set(item) == {
            "name",
            "strength_score",
            "limit_up_count",
            "break_board_count",
            "max_consecutive_boards",
        }
        for item in payload["main_sectors"]["items"]
    )


def test_provider_timeout_is_persisted_without_repeating_the_request(tmp_path: Path) -> None:
    client = _TimeoutClient()
    service = MarketSentimentAnalysisService(MarketSentimentAnalysisStore(tmp_path), http_client=client)

    response = service.generate(_input_payload(), _config())

    assert response.status == "failed"
    assert response.attempts == 1
    assert response.error == "TimeoutError: AI provider request timed out"
    assert client.post.call_count == 1


@pytest.mark.parametrize(
    "content",
    [
        "not-json",
        json.dumps({**_result_payload(), "risk_posture": "unknown"}),
        json.dumps({key: value for key, value in _result_payload().items() if key != "risk_note"}),
    ],
)
def test_malformed_or_invalid_llm_output_retries_exactly_three_times(
    tmp_path: Path,
    content: str,
) -> None:
    client = _Client([_Response(content), _Response(content), _Response(content)])
    service = MarketSentimentAnalysisService(MarketSentimentAnalysisStore(tmp_path), http_client=client)

    response = service.generate(_input_payload(), _config())

    assert response.status == "failed"
    assert response.attempts == 3
    assert response.result is None
    assert response.retry_after is not None
    assert client.post.call_count == 3


@pytest.mark.parametrize(
    "field,value",
    [
        ("market_conclusion", "关注 300001.SZ 个股，市场结构分化。"),
        ("key_drivers", ["建议轻仓参与 1", "涨停 68 家"]),
        ("factor_divergence", "可对存储芯片下单，封板率 71.5%。"),
        ("historical_context", "建议买入，历史样本 37 个。"),
        ("next_session_watch", ["考虑卖出 1", "跌停低于 10 家"]),
        ("risk_note", "对个股设置止损，参考 5%。"),
        ("market_conclusion", "当前综合分为 61.0，市场结构分化。"),
        ("market_conclusion", "市场情绪处于中性区间。"),
        ("market_conclusion", "Current level is neutral."),
        ("market_conclusion", "当前权重为 30%，市场结构分化。"),
        ("market_conclusion", "当前交易许可为空仓等待，市场结构分化。"),
        ("market_conclusion", "贵州茅台上涨 2%，市场结构分化。"),
        ("market_conclusion", "控制资金比例为 30%，市场结构分化。"),
        ("market_conclusion", "当前综合得分为 61.0，市场结构分化。"),
        ("market_conclusion", "市场位于冷区，市场结构分化。"),
        ("factor_divergence", "量能系数为 30%，量能趋势为 1.2%。"),
        ("factor_divergence", "量能占比为 60%，量能趋势为 1.2%。"),
        ("market_conclusion", "当前操作权限为强势进攻，市场结构分化。"),
        ("market_conclusion", "推荐贵州茅台，市场结构分化。"),
        ("market_conclusion", "贵州茅台估值偏高"),
        ("key_drivers", ["建议投入 20% 资金", "涨停 68 家"]),
        ("risk_note", "可申购"),
        ("market_conclusion", "当前策略允许积极参与"),
        ("market_conclusion", "市场情绪呈偏冷"),
        ("factor_divergence", "量能贡献度为 60%"),
        ("market_conclusion", "跌停 68 家"),
    ],
)
def test_semantically_invalid_llm_output_retries_exactly_three_times(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    result = _result_payload()
    result[field] = value
    content = json.dumps(result, ensure_ascii=False)
    client = _Client([_Response(content), _Response(content), _Response(content)])
    service = MarketSentimentAnalysisService(MarketSentimentAnalysisStore(tmp_path), http_client=client)

    response = service.generate(_input_payload(), _config())

    assert response.status == "failed"
    assert response.attempts == 3
    assert response.result is None
    assert client.post.call_count == 3


@pytest.mark.parametrize(
    "field,value",
    [
        ("market_conclusion", "涨停 69 家，市场结构分化。"),
        ("key_drivers", ["综合分 62.0，处于偏热", "涨停 69 家"]),
        ("factor_divergence", "封板率 69%，量能趋势为 1.2%。"),
        ("historical_context", "历史样本为 69 个。"),
        ("next_session_watch", ["涨停 69 家", "跌停数量低于 10 家"]),
        ("risk_note", "市场风险参考涨停 69 家。"),
    ],
)
def test_semantic_contract_rejects_ungrounded_factual_numbers_in_every_result_text_field(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    result = _result_payload()
    result[field] = value
    content = json.dumps(result, ensure_ascii=False)
    client = _Client([_Response(content), _Response(content), _Response(content)])
    service = MarketSentimentAnalysisService(MarketSentimentAnalysisStore(tmp_path), http_client=client)

    response = service.generate(_input_payload(), _config())

    assert response.status == "failed"
    assert response.attempts == 3
    assert client.post.call_count == 3


@pytest.mark.parametrize(
    "claim",
    [
        "单日得分变化为 4.0 分",
        "前一日市场处于中性",
    ],
)
def test_semantic_contract_rejects_prior_claims_without_history(
    tmp_path: Path,
    claim: str,
) -> None:
    payload = build_sentiment_analysis_input(
        _point(),
        [_point()],
        _summary(),
        _decision(),
        _validation(),
    )
    result = _result_payload()
    result["historical_context"] = claim
    content = json.dumps(result, ensure_ascii=False)
    client = _Client([_Response(content), _Response(content), _Response(content)])
    service = MarketSentimentAnalysisService(MarketSentimentAnalysisStore(tmp_path), http_client=client)

    response = service.generate(payload, _config())

    assert response.status == "failed"
    assert response.attempts == 3
    assert client.post.call_count == 3


@pytest.mark.parametrize(
    "claim",
    [
        "市场情绪得分较昨日上升 4.0。",
        "5日市场情绪得分上升 13.0。",
        "市场情绪得分较昨日上升 4.0 且中证全指近5日上涨 2.5%。",
        "5日市场情绪得分上升 13.0 且中证全指近5日上涨 2.5%。",
        "决策得分变化为 8.5 且中证全指近5日上涨 2.5%。",
    ],
)
def test_semantic_contract_allows_grounded_score_change_movement(
    tmp_path: Path,
    claim: str,
) -> None:
    result = _result_payload()
    result["historical_context"] = claim
    content = json.dumps(result, ensure_ascii=False)
    client = _Client([_Response(content)])
    service = MarketSentimentAnalysisService(MarketSentimentAnalysisStore(tmp_path), http_client=client)

    response = service.generate(_input_payload(), _config())

    assert response.status == "ready"
    assert client.post.call_count == 1


def test_semantic_contract_accepts_rounded_display_values(tmp_path: Path) -> None:
    payload = _input_payload()
    payload["market"]["turnover_cny"] = 1_250_000_100_000
    payload["percentile"]["factors"]["price_position"]["raw_value"] = 64.004
    payload["percentile"]["factors"]["amplitude_5d"]["raw_value"] = 3.604
    payload["percentile"]["factors"]["volume_trend"]["raw_value"] = 1.204

    result = _result_payload()
    result["key_drivers"] = [
        "成交额12500亿元，涨停68家",
        "价格位置原始值64.00%，价格位置得分60.0",
        "5日振幅原始值3.60%，得分60.0",
    ]
    result["factor_divergence"] = "量能趋势原始值1.20%，但5日涨幅为2.5%。"
    content = json.dumps(result, ensure_ascii=False)
    client = _Client([_Response(content)])
    service = MarketSentimentAnalysisService(MarketSentimentAnalysisStore(tmp_path), http_client=client)

    response = service.generate(payload, _config())

    assert response.status == "ready"
    assert client.post.call_count == 1


def test_semantic_contract_accepts_decimal_chinese_unit_display_value(tmp_path: Path) -> None:
    payload = _input_payload()
    payload["market"]["turnover_cny"] = 1_205_000_100_000

    result = _result_payload()
    result["key_drivers"] = [
        "成交额1.205万亿元，涨停68家",
        "价格位置得分60.0，结构仍有分化",
    ]
    result["next_session_watch"][-1] = "成交额能否维持1.205万亿量级"
    content = json.dumps(result, ensure_ascii=False)
    client = _Client([_Response(content)])
    service = MarketSentimentAnalysisService(MarketSentimentAnalysisStore(tmp_path), http_client=client)

    response = service.generate(payload, _config())

    assert response.status == "ready"
    assert client.post.call_count == 1


def test_semantic_contract_rejects_invented_key_driver_threshold(tmp_path: Path) -> None:
    result = _result_payload()
    result["key_drivers"] = ["综合分 62.0，处于偏热", "若涨停家数高于 69 家"]
    content = json.dumps(result, ensure_ascii=False)
    client = _Client([_Response(content), _Response(content), _Response(content)])
    service = MarketSentimentAnalysisService(MarketSentimentAnalysisStore(tmp_path), http_client=client)

    response = service.generate(_input_payload(), _config())

    assert response.status == "failed"
    assert response.attempts == 3
    assert client.post.call_count == 3


def test_semantic_contract_validates_conditional_consequence_numbers(tmp_path: Path) -> None:
    result = _result_payload()
    result["next_session_watch"] = [
        "若封板率低于 60% 则成交额为 69 亿元",
        "跌停数量低于 10 家",
    ]
    content = json.dumps(result, ensure_ascii=False)
    client = _Client([_Response(content), _Response(content), _Response(content)])
    service = MarketSentimentAnalysisService(MarketSentimentAnalysisStore(tmp_path), http_client=client)

    response = service.generate(_input_payload(), _config())

    assert response.status == "failed"
    assert response.attempts == 3
    assert client.post.call_count == 3


def test_semantic_contract_does_not_apply_watch_threshold_to_an_unrelated_number(
    tmp_path: Path,
) -> None:
    result = _result_payload()
    result["next_session_watch"] = [
        "涨停 69 家且若封板率低于 60%",
        "跌停数量低于 10 家",
    ]
    content = json.dumps(result, ensure_ascii=False)
    client = _Client([_Response(content), _Response(content), _Response(content)])
    service = MarketSentimentAnalysisService(MarketSentimentAnalysisStore(tmp_path), http_client=client)

    response = service.generate(_input_payload(), _config())

    assert response.status == "failed"
    assert response.attempts == 3
    assert client.post.call_count == 3


@pytest.mark.parametrize(
    "field,value",
    [
        ("market_conclusion", "沪深300近5日上涨 2.5%"),
        ("key_drivers", ["涨停数上升至 68 家", "量能趋势 1.2%"]),
        (
            "next_session_watch",
            ["关注封板率能否维持在 60% 以上", "跌停数量低于 10 家"],
        ),
    ],
)
def test_semantic_contract_allows_reviewer_grounded_prose(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    result = _result_payload()
    result[field] = value
    content = json.dumps(result, ensure_ascii=False)
    client = _Client([_Response(content)])
    service = MarketSentimentAnalysisService(MarketSentimentAnalysisStore(tmp_path), http_client=client)

    response = service.generate(_input_payload(), _config())

    assert response.status == "ready"
    assert response.result is not None
    assert client.post.call_count == 1


def test_semantic_contract_allows_market_breadth_movement_wording(
    tmp_path: Path,
) -> None:
    result = _result_payload()
    result["market_conclusion"] = "全市场上涨家数 3012、下跌家数 1845，市场结构分化。"
    content = json.dumps(result, ensure_ascii=False)
    client = _Client([_Response(content)])
    service = MarketSentimentAnalysisService(MarketSentimentAnalysisStore(tmp_path), http_client=client)

    response = service.generate(_input_payload(), _config())

    assert response.status == "ready"
    assert client.post.call_count == 1


def test_semantic_contract_keeps_sector_context_across_metric_clauses(
    tmp_path: Path,
) -> None:
    result = _result_payload()
    result["key_drivers"] = [
        "存储芯片板块强度92，涨停11家，炸板2家，最高连板4",
        "综合分62.0，处于偏热",
    ]
    content = json.dumps(result, ensure_ascii=False)
    client = _Client([_Response(content)])
    service = MarketSentimentAnalysisService(MarketSentimentAnalysisStore(tmp_path), http_client=client)

    response = service.generate(_input_payload(), _config())

    assert response.status == "ready"
    assert client.post.call_count == 1


def test_semantic_contract_does_not_treat_sector_score_as_overall_score(
    tmp_path: Path,
) -> None:
    result = _result_payload()
    result["key_drivers"] = [
        "存储芯片强度评分92.0，涨停11家，炸板2家，最高连板4板",
        "综合评分62.0，处于偏热",
    ]
    content = json.dumps(result, ensure_ascii=False)
    client = _Client([_Response(content)])
    service = MarketSentimentAnalysisService(MarketSentimentAnalysisStore(tmp_path), http_client=client)

    response = service.generate(_input_payload(), _config())

    assert response.status == "ready"
    assert client.post.call_count == 1


def test_semantic_contract_allows_factor_percentile_movement_subject(
    tmp_path: Path,
) -> None:
    result = _result_payload()
    result["factor_divergence"] = (
        "价格位置分位60.0（原值64.0%）与5日指数涨幅分位60.0（原值2.5%）明显背离。"
    )
    content = json.dumps(result, ensure_ascii=False)
    client = _Client([_Response(content)])
    service = MarketSentimentAnalysisService(MarketSentimentAnalysisStore(tmp_path), http_client=client)

    response = service.generate(_input_payload(), _config())

    assert response.status == "ready"
    assert client.post.call_count == 1


def test_semantic_contract_rejects_unavailable_market_metric_claim(tmp_path: Path) -> None:
    payload = build_sentiment_analysis_input(
        _point(),
        [_point()],
        None,
        _decision(),
        _validation(),
    )
    result = _result_payload()
    result["market_conclusion"] = "涨停 68 家，市场结构分化。"
    result["key_drivers"] = ["综合分 62.0，处于偏热", "量能趋势为 1.2%"]
    result["factor_divergence"] = "量能趋势为 1.2%。"
    content = json.dumps(result, ensure_ascii=False)
    client = _Client([_Response(content), _Response(content), _Response(content)])
    service = MarketSentimentAnalysisService(MarketSentimentAnalysisStore(tmp_path), http_client=client)

    response = service.generate(payload, _config())

    assert response.status == "failed"
    assert response.attempts == 3
    assert client.post.call_count == 3


def test_semantic_contract_allows_grounded_aggregate_index_sector_and_threshold_prose(
    tmp_path: Path,
) -> None:
    result = _result_payload()
    result["market_conclusion"] = "当前综合得分为 62.0，前一日市场处于中性，当前市场位于热区。"
    result["factor_divergence"] = "量能系数为 20%，量能趋势为 1.2%。"
    result["historical_context"] = "中证全指近5日上涨 2.5%，存储芯片的表现受到关注。"
    content = json.dumps(result, ensure_ascii=False)
    client = _Client([_Response(content)])
    service = MarketSentimentAnalysisService(MarketSentimentAnalysisStore(tmp_path), http_client=client)

    response = service.generate(_input_payload(), _config())

    assert response.status == "ready"
    assert response.result is not None
    assert client.post.call_count == 1


@pytest.mark.parametrize(
    "field,value",
    [
        ("market_conclusion", "贵州茅台的表现受到关注，市场结构分化。"),
        ("risk_note", "建议增持。"),
    ],
)
def test_semantic_contract_rejects_security_attention_and_recommendation(
    tmp_path: Path,
    field: str,
    value: str,
) -> None:
    result = _result_payload()
    result[field] = value
    content = json.dumps(result, ensure_ascii=False)
    client = _Client([_Response(content), _Response(content), _Response(content)])
    service = MarketSentimentAnalysisService(MarketSentimentAnalysisStore(tmp_path), http_client=client)

    response = service.generate(_input_payload(), _config())

    assert response.status == "failed"
    assert response.attempts == 3
    assert client.post.call_count == 3


@pytest.mark.parametrize(
    "claim",
    [
        "今日中证全指上涨 2.5%，市场结构分化。",
        "今日中证全指上涨了 2.5%，市场结构分化。",
        "今日中证全指涨了 2.5%，市场结构分化。",
        "今日中证全指跌了 2.5%，市场结构分化。",
        "5日涨幅为 2.5% 且今日中证全指上涨 2.5%。",
        "市场情绪得分较昨日上升 4.0 且今日中证全指上涨 2.5%。",
        "5日市场情绪得分上升 13.0 且今日中证全指跌了 2.5%。",
        "决策得分变化为 8.5 且今日中证全指上涨 2.5%。",
        "今日中证全指上涨 2.5% 且指数5日表现为 2.5%。",
        "今日中证全指跌了 2.5% 且指数5日表现为 2.5%。",
        "建议持有贵州茅台，市场结构分化。",
        "贵州茅台值得买，市场结构分化。",
        "贵州茅台是首选，市场结构分化。",
        "建议配置贵州茅台，市场结构分化。",
    ],
)
def test_semantic_contract_rejects_cross_field_movement_and_named_holding_advice(
    tmp_path: Path,
    claim: str,
) -> None:
    result = _result_payload()
    result["market_conclusion"] = claim
    content = json.dumps(result, ensure_ascii=False)
    client = _Client([_Response(content)] * 3)
    service = MarketSentimentAnalysisService(MarketSentimentAnalysisStore(tmp_path), http_client=client)

    response = service.generate(_input_payload(), _config())

    assert response.status == "failed"
    assert response.attempts == 3
    assert client.post.call_count == 3


def test_semantic_contract_allows_attention_prose_for_aggregate_and_sector(
    tmp_path: Path,
) -> None:
    result = _result_payload()
    result["market_conclusion"] = "中证全指的表现受到关注，市场结构分化。"
    result["historical_context"] = "存储芯片的表现受到关注。"
    content = json.dumps(result, ensure_ascii=False)
    client = _Client([_Response(content)])
    service = MarketSentimentAnalysisService(MarketSentimentAnalysisStore(tmp_path), http_client=client)

    response = service.generate(_input_payload(), _config())

    assert response.status == "ready"
    assert response.result is not None
    assert client.post.call_count == 1


@pytest.mark.parametrize(
    "field,value",
    [
        ("market_conclusion", "市场上涨两个百分点，结构仍有分化。"),
        ("market_conclusion", "成交额增长 62.0%，市场结构分化。"),
    ],
)
def test_semantic_contract_rejects_ungrounded_chinese_or_cross_field_metric_numbers(
    tmp_path: Path,
    field: str,
    value: str,
) -> None:
    result = _result_payload()
    result[field] = value
    content = json.dumps(result, ensure_ascii=False)
    client = _Client([_Response(content), _Response(content), _Response(content)])
    service = MarketSentimentAnalysisService(MarketSentimentAnalysisStore(tmp_path), http_client=client)

    response = service.generate(_input_payload(), _config())

    assert response.status == "failed"
    assert response.attempts == 3
    assert client.post.call_count == 3


def test_semantic_contract_checks_sources_in_conditional_clauses(tmp_path: Path) -> None:
    payload = build_sentiment_analysis_input(_point(), [_point()], None, None, None)
    result = _result_payload()
    result["key_drivers"] = ["综合分 62.0，处于偏热", "量能趋势为 1.2%"]
    result["factor_divergence"] = "量能趋势为 1.2%。"
    result["historical_context"] = "历史背景暂无可用样本。"
    result["next_session_watch"] = ["若市场状态为主升且涨停家数高于 70 家", "若封板率低于 60%"]
    content = json.dumps(result, ensure_ascii=False)
    client = _Client([_Response(content), _Response(content), _Response(content)])
    service = MarketSentimentAnalysisService(MarketSentimentAnalysisStore(tmp_path), http_client=client)

    response = service.generate(payload, _config())

    assert response.status == "failed"
    assert response.attempts == 3
    assert client.post.call_count == 3


def test_semantic_contract_allows_conditional_watch_thresholds_without_market_snapshot(
    tmp_path: Path,
) -> None:
    payload = build_sentiment_analysis_input(
        _point(),
        [_point()],
        None,
        _decision(),
        _validation(),
    )
    result = _result_payload()
    result["key_drivers"] = ["综合分 62.0，处于偏热", "量能趋势为 1.2%"]
    result["factor_divergence"] = "量能趋势为 1.2%。"
    result["next_session_watch"] = ["若涨停家数高于 70 家", "若封板率低于 60%"]
    content = json.dumps(result, ensure_ascii=False)
    client = _Client([_Response(content)])
    service = MarketSentimentAnalysisService(MarketSentimentAnalysisStore(tmp_path), http_client=client)

    response = service.generate(payload, _config())

    assert response.status == "ready"
    assert response.result is not None
    assert client.post.call_count == 1


def test_semantic_contract_rejects_english_position_sizing_claim(tmp_path: Path) -> None:
    result = _result_payload()
    result["risk_note"] = "Maintain a 20% position."
    content = json.dumps(result, ensure_ascii=False)
    client = _Client([_Response(content)] * 3)
    service = MarketSentimentAnalysisService(MarketSentimentAnalysisStore(tmp_path), http_client=client)

    response = service.generate(_input_payload(), _config())

    assert response.status == "failed"
    assert response.attempts == 3
    assert client.post.call_count == 3


def test_semantic_contract_rejects_ungrounded_chinese_point_claim(tmp_path: Path) -> None:
    result = _result_payload()
    result["market_conclusion"] = "市场上涨两点，结构仍有分化。"
    result["historical_context"] = "前一点的市场背景无需另行量化。"
    content = json.dumps(result, ensure_ascii=False)
    client = _Client([_Response(content)] * 3)
    service = MarketSentimentAnalysisService(MarketSentimentAnalysisStore(tmp_path), http_client=client)

    response = service.generate(_input_payload(), _config())

    assert response.status == "failed"
    assert response.attempts == 3
    assert client.post.call_count == 3


def test_semantic_contract_rejects_unavailable_decision_state_transitions(
    tmp_path: Path,
) -> None:
    for index, state_verb in enumerate(("转入", "转为", "进入")):
        payload = build_sentiment_analysis_input(_point(), [_point()], _summary(), None, _validation())
        result = _result_payload()
        result["next_session_watch"] = [
            f"若市场情绪{state_verb}主升且涨停家数高于 70 家",
            "若封板率低于 60%",
        ]
        content = json.dumps(result, ensure_ascii=False)
        client = _Client([_Response(content)] * 3)
        service = MarketSentimentAnalysisService(
            MarketSentimentAnalysisStore(tmp_path / str(index)),
            http_client=client,
        )

        response = service.generate(payload, _config())

        assert response.status == "failed", state_verb
        assert response.attempts == 3
        assert client.post.call_count == 3


def test_semantic_contract_binds_sector_strength_to_canonical_value(tmp_path: Path) -> None:
    result = _result_payload()
    result["market_conclusion"] = "存储芯片板块强度为 62.0，结构仍有分化。"
    wrong_content = json.dumps(result, ensure_ascii=False)
    correct_result = _result_payload()
    correct_result["market_conclusion"] = "存储芯片板块强度为 92.0，结构仍有分化。"
    correct_content = json.dumps(correct_result, ensure_ascii=False)
    client = _Client([_Response(wrong_content)] * 3 + [_Response(correct_content)])
    service = MarketSentimentAnalysisService(MarketSentimentAnalysisStore(tmp_path), http_client=client)

    rejected = service.generate(_input_payload(), _config(), force=True)
    accepted = service.generate(_input_payload(), _config(), force=True)

    assert rejected.status == "failed"
    assert rejected.attempts == 3
    assert accepted.status == "ready"
    assert accepted.result is not None
    assert client.post.call_count == 4


def test_matching_failed_request_waits_for_retry_cooldown(tmp_path: Path) -> None:
    client = _Client([RuntimeError("network unavailable")] * 3)
    service = MarketSentimentAnalysisService(MarketSentimentAnalysisStore(tmp_path), http_client=client)

    failed = service.generate(_input_payload(), _config())
    cached = service.generate(_input_payload(), _config())

    assert failed.status == "failed"
    assert cached == failed
    assert cached.retry_after is not None
    assert client.post.call_count == 3


@pytest.mark.parametrize(
    "config",
    [_config(enabled=False), _config(api_key="")],
)
def test_unconfigured_ai_returns_without_network_io(tmp_path: Path, config: EffectiveAiAnalysisSettings) -> None:
    client = _Client([])
    service = MarketSentimentAnalysisService(MarketSentimentAnalysisStore(tmp_path), http_client=client)

    response = service.generate(_input_payload(), config)

    assert response.status == "unconfigured"
    assert response.attempts == 0
    assert client.post.call_count == 0


def test_failure_is_persisted_atomically_without_secret_leakage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "secret-do-not-store"
    client = _Client([RuntimeError(f"provider rejected {secret}")] * 3)
    store = MarketSentimentAnalysisStore(tmp_path)
    service = MarketSentimentAnalysisService(store, http_client=client)
    replaced_from: list[Path] = []
    original_replace = Path.replace

    def record_replace(path: Path, target: Path) -> Path:
        replaced_from.append(path)
        return original_replace(path, target)

    monkeypatch.setattr(Path, "replace", record_replace)
    response = service.generate(_input_payload(), _config(api_key=secret))
    stored = store.load("2026-07-22")

    assert response.status == "failed"
    assert stored == response
    assert secret not in response.error
    assert secret not in store.record_path("2026-07-22").read_text(encoding="utf-8")
    assert [path.name for path in replaced_from] == ["2026-07-22.json.tmp", "2026-07-22.json.tmp"]


def test_store_load_treats_malformed_record_as_cache_miss(tmp_path: Path) -> None:
    store = MarketSentimentAnalysisStore(tmp_path)
    path = store.record_path("2026-07-22")
    path.parent.mkdir(parents=True)
    path.write_text("not-json", encoding="utf-8")

    assert store.load("2026-07-22") is None


def test_store_load_treats_wrong_version_or_trade_date_as_cache_miss(tmp_path: Path) -> None:
    store = MarketSentimentAnalysisStore(tmp_path)
    path = store.record_path("2026-07-22")
    path.parent.mkdir(parents=True)
    record = SentimentPercentileAnalysisResponse(
        trade_date="2026-07-21",
        status="ready",
        model_version="market-sentiment-percentile-v0",
        provider="openai_compatible",
        llm_model="test-model",
        input_hash="a" * 64,
        result=SentimentAnalysisResult.model_validate(_result_payload()),
    )
    path.write_text(record.model_dump_json(), encoding="utf-8")

    assert store.load("2026-07-22") is None


def test_store_load_propagates_filesystem_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = MarketSentimentAnalysisStore(tmp_path)
    path = store.record_path("2026-07-22")
    path.parent.mkdir(parents=True)
    path.write_text("{}", encoding="utf-8")

    def fail_read_text(*_args: object, **_kwargs: object) -> str:
        raise PermissionError("read denied")

    monkeypatch.setattr(Path, "read_text", fail_read_text)

    with pytest.raises(PermissionError, match="read denied"):
        store.load("2026-07-22")
