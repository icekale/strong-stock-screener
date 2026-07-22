from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from app.models import (
    SentimentAnalysisResult,
    SentimentDecisionResponse,
    SentimentMainSectorSignal,
    SentimentPercentileFactor,
    SentimentPercentileFactors,
    SentimentPercentilePoint,
    SentimentSummaryMetrics,
    SentimentSummaryResponse,
    ShortTermSentimentIndustryItem,
)
from app.services.market_sentiment_analysis import (
    MarketSentimentAnalysisService,
    build_sentiment_analysis_input,
    hash_sentiment_analysis_input,
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


class _Response:
    def __init__(self, content: str) -> None:
        self.content = content

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return {"choices": [{"message": {"content": self.content}}]}


class _Client:
    def __init__(self, responses: list[object]) -> None:
        self.post = Mock(side_effect=responses)


class _PendingInspectingClient:
    def __init__(self, store: MarketSentimentAnalysisStore) -> None:
        self.store = store
        self.pending_status: str | None = None
        self.post = Mock(side_effect=self._post)

    def _post(self, *_args: object, **_kwargs: object) -> _Response:
        pending = self.store.load("2026-07-22")
        self.pending_status = pending.status if pending else None
        return _Response(json.dumps(_result_payload(), ensure_ascii=False))


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
    assert request["temperature"] == 0.1
    system_prompt = request["messages"][0]["content"]
    for prohibited in ("statistic", "stocks", "position sizing", "orders", "missing values"):
        assert prohibited in system_prompt


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
