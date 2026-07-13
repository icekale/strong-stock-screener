from __future__ import annotations

import hashlib
import json
from concurrent.futures import Future, TimeoutError as FutureTimeoutError
from datetime import datetime, time
from threading import RLock
from typing import Literal
from zoneinfo import ZoneInfo

from app.config import Settings, get_settings
from app.models import (
    CZSC_CATALOG_VERSION,
    CZSC_SCORE_RULE_VERSION,
    ChanlunPeriod,
    CzscResearchSnapshot,
    CzscResearchStatus,
    CzscSignalEvidence,
    StrongStockSourceStatus,
)
from app.services.chanlun.research_catalog import (
    ResearchCatalog,
    load_research_catalog,
    map_raw_state,
)
from app.services.chanlun.research_protocol import (
    APPROVED_PERIODS,
    CZSC_RC8_ENGINE_VERSION,
    CzscRc8RawSignal,
    CzscRc8Request,
    CzscRc8Response,
    build_research_request,
)
from app.services.chanlun.research_scoring import score_czsc_v2
from app.services.chanlun.service import ClosedWorkspaceInputs
from app.services.chanlun.symbols import normalize_chanlun_symbol


SHANGHAI = ZoneInfo("Asia/Shanghai")
_MIN_LOOKBACK = 20
_MAX_LOOKBACK = 260


class CzscResearchService:
    def __init__(
        self,
        *,
        store: object,
        client: object | None,
        input_provider: object,
        catalog: ResearchCatalog | None = None,
        settings: Settings | None = None,
    ) -> None:
        configured = settings or get_settings()
        self.store = store
        self.client = client
        self.input_provider = input_provider
        self.catalog = catalog or load_research_catalog()
        self.enabled = configured.chanlun_rc8_enabled
        self.interactive_wait_seconds = configured.chanlun_rc8_interactive_wait_seconds
        self._inflight: dict[str, Future[CzscResearchSnapshot]] = {}
        self._lock = RLock()

    def get(
        self,
        symbol: str,
        lookback: int,
        priority: int = 0,
        wait_seconds: float | None = None,
    ) -> CzscResearchSnapshot:
        if not _MIN_LOOKBACK <= lookback <= _MAX_LOOKBACK:
            raise ValueError(f"lookback for 1d must be between {_MIN_LOOKBACK} and {_MAX_LOOKBACK}")
        normalized_symbol = normalize_chanlun_symbol(symbol) or symbol.strip().upper()
        if not self.enabled:
            return _unavailable_snapshot(
                symbol=normalized_symbol,
                input_snapshot_id=_fallback_input_id(normalized_symbol, lookback),
                detail="CZSC rc8 研究引擎已禁用",
            )
        if self.client is None:
            return _unavailable_snapshot(
                symbol=normalized_symbol,
                input_snapshot_id=_fallback_input_id(normalized_symbol, lookback),
                detail="CZSC rc8 Python 或 worker 不可用",
            )
        try:
            inputs = self.input_provider.closed_workspace_inputs(
                normalized_symbol,
                lookback=lookback,
            )
        except Exception as exc:
            return _unavailable_snapshot(
                symbol=normalized_symbol,
                input_snapshot_id=_fallback_input_id(normalized_symbol, lookback),
                detail=_sanitized_failure_detail("闭合K线输入不可用", exc),
            )

        request: CzscRc8Request | None = None
        request_error: Exception | None = None
        try:
            request = _build_request(inputs)
        except Exception as exc:
            request_error = exc
        input_snapshot_id = (
            request.input_snapshot_id if request is not None else _closed_input_id(inputs, lookback)
        )
        boundaries = (
            dict(request.last_closed_by_period)
            if request is not None
            else dict(inputs.last_closed_by_period)
        )
        source_status = _flatten_source_status(inputs)

        blocked_status = _blocked_input_status(inputs)
        if blocked_status is not None:
            return _snapshot_for_status(
                status=blocked_status,
                inputs=inputs,
                input_snapshot_id=input_snapshot_id,
                boundaries=boundaries,
                source_status=source_status,
                detail=_blocked_status_detail(blocked_status),
            )
        if request is None:
            return _snapshot_for_status(
                status="unavailable",
                inputs=inputs,
                input_snapshot_id=input_snapshot_id,
                boundaries=boundaries,
                source_status=source_status,
                detail=_sanitized_failure_detail("研究请求校验失败", request_error),
            )
        try:
            cached = self.store.load_snapshot(request.input_snapshot_id)
        except Exception as exc:
            return _snapshot_for_status(
                status="unavailable",
                inputs=inputs,
                input_snapshot_id=input_snapshot_id,
                boundaries=boundaries,
                source_status=source_status,
                detail=_sanitized_failure_detail("研究快照读取失败", exc),
            )
        if _cached_snapshot_matches(cached, request):
            return cached

        shared, created = self._shared_future(request.input_snapshot_id)
        if created:
            try:
                cached = self.store.load_snapshot(request.input_snapshot_id)
            except Exception as exc:
                unavailable = _snapshot_for_status(
                    status="unavailable",
                    inputs=inputs,
                    input_snapshot_id=input_snapshot_id,
                    boundaries=boundaries,
                    source_status=source_status,
                    detail=_sanitized_failure_detail("研究快照读取失败", exc),
                )
                self._finish_shared(request.input_snapshot_id, shared, unavailable)
            else:
                if _cached_snapshot_matches(cached, request):
                    self._finish_shared(request.input_snapshot_id, shared, cached)
                else:
                    try:
                        worker_future = self.client.submit(request, priority)
                        worker_future.add_done_callback(
                            lambda future: self._complete_worker_request(
                                request=request,
                                inputs=inputs,
                                shared=shared,
                                worker_future=future,
                            )
                        )
                    except Exception as exc:
                        unavailable = _snapshot_for_status(
                            status="unavailable",
                            inputs=inputs,
                            input_snapshot_id=input_snapshot_id,
                            boundaries=boundaries,
                            source_status=source_status,
                            detail=_sanitized_failure_detail("CZSC rc8 提交失败", exc),
                        )
                        self._finish_shared(request.input_snapshot_id, shared, unavailable)

        timeout = self.interactive_wait_seconds if wait_seconds is None else max(0, wait_seconds)
        try:
            return shared.result(timeout=timeout)
        except FutureTimeoutError:
            return _snapshot_for_status(
                status="pending",
                inputs=inputs,
                input_snapshot_id=input_snapshot_id,
                boundaries=boundaries,
                source_status=source_status,
                detail="CZSC rc8 研究计算仍在队列或执行中",
                source_state="stale",
            )
        except Exception as exc:
            return _snapshot_for_status(
                status="unavailable",
                inputs=inputs,
                input_snapshot_id=input_snapshot_id,
                boundaries=boundaries,
                source_status=source_status,
                detail=_sanitized_failure_detail("CZSC rc8 研究计算失败", exc),
            )

    def health(self) -> dict[str, object]:
        with self._lock:
            inflight_count = len(self._inflight)
        if not self.enabled:
            return {
                "status": "disabled",
                "queue_depth": 0,
                "circuit_state": "disabled",
                "engine_version": None,
                "inflight_count": inflight_count,
                "error": None,
            }
        if self.client is None:
            return {
                "status": "unavailable",
                "queue_depth": 0,
                "circuit_state": "unavailable",
                "engine_version": None,
                "inflight_count": inflight_count,
                "error": "rc8 worker unavailable",
            }
        try:
            client_health = self.client.health()
        except Exception as exc:
            return {
                "status": "unavailable",
                "queue_depth": 0,
                "circuit_state": "unavailable",
                "engine_version": None,
                "inflight_count": inflight_count,
                "error": _sanitized_error(exc),
            }
        circuit_state = str(client_health.get("circuit_state") or "unknown")
        last_error = client_health.get("last_error")
        engine_version = client_health.get("engine_version")
        version_error = None
        if engine_version is None:
            version_error = "rc8 worker engine version unverified"
        elif engine_version != CZSC_RC8_ENGINE_VERSION:
            version_error = "rc8 worker engine version mismatch"
        unavailable = (
            bool(client_health.get("closed"))
            or circuit_state == "open"
            or bool(last_error)
            or version_error is not None
        )
        return {
            "status": "unavailable" if unavailable else "ready",
            "queue_depth": int(client_health.get("queue_depth") or 0),
            "circuit_state": circuit_state,
            "engine_version": engine_version,
            "inflight_count": inflight_count,
            "error": _sanitized_error(last_error) if last_error else version_error,
        }

    def _shared_future(
        self,
        input_snapshot_id: str,
    ) -> tuple[Future[CzscResearchSnapshot], bool]:
        with self._lock:
            shared = self._inflight.get(input_snapshot_id)
            if shared is not None:
                return shared, False
            shared = Future()
            self._inflight[input_snapshot_id] = shared
            return shared, True

    def _complete_worker_request(
        self,
        *,
        request: CzscRc8Request,
        inputs: ClosedWorkspaceInputs,
        shared: Future[CzscResearchSnapshot],
        worker_future: Future[CzscRc8Response],
    ) -> None:
        try:
            response = CzscRc8Response.model_validate(worker_future.result())
            if response.request_id != request.request_id:
                raise ValueError("worker response request ID mismatch")
            if response.input_snapshot_id != request.input_snapshot_id:
                raise ValueError("worker response input snapshot ID mismatch")
            if response.catalog_version != self.catalog.version:
                raise ValueError("worker response catalog version mismatch")
            if response.status != "ready":
                raise RuntimeError(response.error or "worker returned an error")
            current_states = self._map_signals(
                response.current_states,
                request=request,
                engine_version=response.engine_version,
            )
            events = self._map_signals(
                response.events,
                request=request,
                engine_version=response.engine_version,
            )
            score = score_czsc_v2(evidence=current_states, freshness=inputs.freshness)
            if score.score is None:
                raise ValueError("fresh research input did not produce a score")
            snapshot = CzscResearchSnapshot(
                status="ready",
                symbol=request.symbol,
                current_states=current_states,
                events=events,
                last_closed_by_period=dict(request.last_closed_by_period),
                input_snapshot_id=request.input_snapshot_id,
                score=score.score,
                eligible=score.eligible,
                engine_version=response.engine_version,
                catalog_version=response.catalog_version,
                rule_version=score.rule_version,
                source_status=[
                    *_flatten_source_status(inputs),
                    StrongStockSourceStatus(
                        source="CZSC rc8研究引擎",
                        status="success",
                        detail="研究信号映射、评分并保存完成",
                    ),
                ],
                adjustment_mode=request.adjustment_mode,
            )
            self.store.save_snapshot(snapshot)
        except Exception as exc:
            snapshot = _snapshot_for_status(
                status="unavailable",
                inputs=inputs,
                input_snapshot_id=request.input_snapshot_id,
                boundaries=dict(request.last_closed_by_period),
                source_status=_flatten_source_status(inputs),
                detail=_sanitized_failure_detail("CZSC rc8 研究结果处理失败", exc),
            )
        self._finish_shared(request.input_snapshot_id, shared, snapshot)

    def _map_signals(
        self,
        raw_signals: list[CzscRc8RawSignal],
        *,
        request: CzscRc8Request,
        engine_version: str,
    ) -> list[CzscSignalEvidence]:
        mapped: list[CzscSignalEvidence] = []
        for raw in raw_signals:
            evidence = map_raw_state(
                symbol=request.symbol,
                catalog_id=raw.catalog_id,
                value_fields=raw.value_fields.model_dump(mode="python"),
                raw_key=raw.raw_key,
                raw_value=raw.raw_value,
                occurred_at=raw.occurred_at,
                last_closed_bar_at=raw.last_closed_bar_at,
                input_snapshot_id=request.input_snapshot_id,
                engine_version=engine_version,
                period=raw.period,
                higher_period=raw.higher_period,
                lower_period=raw.lower_period,
                catalog=self.catalog,
            )
            if evidence is not None:
                mapped.append(evidence)
        return mapped

    def _finish_shared(
        self,
        input_snapshot_id: str,
        shared: Future[CzscResearchSnapshot],
        snapshot: CzscResearchSnapshot,
    ) -> None:
        with self._lock:
            if self._inflight.get(input_snapshot_id) is shared:
                del self._inflight[input_snapshot_id]
        if not shared.done():
            shared.set_result(snapshot)


def _build_request(inputs: ClosedWorkspaceInputs) -> CzscRc8Request:
    return build_research_request(
        inputs.symbol,
        {period: list(inputs.periods[period]) for period in APPROVED_PERIODS},
        adjustment_mode=inputs.adjustment_mode,
        decision_at=_decision_at(inputs),
        last_closed_by_period=inputs.last_closed_by_period,
        catalog_version=CZSC_CATALOG_VERSION,
    )


def _decision_at(inputs: ClosedWorkspaceInputs) -> datetime:
    boundaries: list[datetime] = []
    for period in APPROVED_PERIODS:
        value = inputs.last_closed_by_period[period]
        if period == "1d" and len(value) == 10:
            boundaries.append(
                datetime.combine(datetime.fromisoformat(value).date(), time(15), tzinfo=SHANGHAI)
            )
        else:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            boundaries.append(
                parsed.replace(tzinfo=SHANGHAI)
                if parsed.tzinfo is None
                else parsed.astimezone(SHANGHAI)
            )
    return max(boundaries)


def _blocked_input_status(inputs: ClosedWorkspaceInputs) -> CzscResearchStatus | None:
    if inputs.adjustment_mode == "adjustment_mismatch":
        return "adjustment_mismatch"
    if any(value == "stale" for value in inputs.freshness.values()) or any(
        value == "stale" for value in inputs.availability.values()
    ):
        return "stale"
    if any(value == "unavailable" for value in inputs.availability.values()):
        return "unavailable"
    if any(value == "insufficient_bars" for value in inputs.availability.values()) or any(
        value == "insufficient" for value in inputs.freshness.values()
    ):
        return "insufficient_bars"
    return None


def _cached_snapshot_matches(
    snapshot: CzscResearchSnapshot | None,
    request: CzscRc8Request,
) -> bool:
    return bool(
        snapshot is not None
        and snapshot.input_snapshot_id == request.input_snapshot_id
        and snapshot.engine_version == CZSC_RC8_ENGINE_VERSION
        and snapshot.catalog_version == request.catalog_version
        and snapshot.rule_version == CZSC_SCORE_RULE_VERSION
    )


def _blocked_status_detail(status: CzscResearchStatus) -> str:
    return {
        "stale": "闭合K线输入已过期，未提交研究计算",
        "insufficient_bars": "闭合K线数量不足，未提交研究计算",
        "adjustment_mismatch": "四周期复权口径不一致，未提交研究计算",
        "unavailable": "闭合K线输入不可用，未提交研究计算",
    }.get(status, "研究输入不可评分")


def _snapshot_for_status(
    *,
    status: CzscResearchStatus,
    inputs: ClosedWorkspaceInputs,
    input_snapshot_id: str,
    boundaries: dict[ChanlunPeriod, str],
    source_status: list[StrongStockSourceStatus],
    detail: str,
    source_state: Literal["failed", "disabled", "stale"] = "failed",
) -> CzscResearchSnapshot:
    return CzscResearchSnapshot(
        status=status,
        symbol=inputs.symbol,
        last_closed_by_period=boundaries,
        input_snapshot_id=input_snapshot_id,
        engine_version=CZSC_RC8_ENGINE_VERSION,
        source_status=[
            *source_status,
            StrongStockSourceStatus(
                source="CZSC rc8研究引擎",
                status=source_state,
                detail=detail,
            ),
        ],
        adjustment_mode=inputs.adjustment_mode,
    )


def _unavailable_snapshot(
    *,
    symbol: str,
    input_snapshot_id: str,
    detail: str,
) -> CzscResearchSnapshot:
    return CzscResearchSnapshot(
        status="unavailable",
        symbol=symbol,
        input_snapshot_id=input_snapshot_id,
        engine_version=CZSC_RC8_ENGINE_VERSION,
        source_status=[
            StrongStockSourceStatus(
                source="CZSC rc8研究引擎",
                status="failed",
                detail=detail,
            )
        ],
    )


def _flatten_source_status(inputs: ClosedWorkspaceInputs) -> list[StrongStockSourceStatus]:
    output: list[StrongStockSourceStatus] = []
    seen: set[tuple[str, str, str]] = set()
    for period in APPROVED_PERIODS:
        for item in inputs.source_status.get(period, ()):
            identity = (item.source, item.status, item.detail)
            if identity not in seen:
                seen.add(identity)
                output.append(item)
    return output


def _closed_input_id(inputs: ClosedWorkspaceInputs, lookback: int) -> str:
    payload = {
        "symbol": inputs.symbol,
        "lookback": lookback,
        "adjustment_mode": inputs.adjustment_mode,
        "availability": inputs.availability,
        "freshness": inputs.freshness,
        "periods": {
            period: [bar.model_dump(mode="json") for bar in inputs.periods.get(period, ())]
            for period in APPROVED_PERIODS
        },
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"


def _fallback_input_id(symbol: str, lookback: int) -> str:
    value = f"{symbol}:{lookback}".encode()
    return f"sha256:{hashlib.sha256(value).hexdigest()}"


def _sanitized_failure_detail(prefix: str, error: object | None) -> str:
    return f"{prefix}: {_sanitized_error(error)}" if error is not None else prefix


def _sanitized_error(error: object) -> str:
    if isinstance(error, BaseException):
        return error.__class__.__name__
    value = str(error).splitlines()[0].strip()
    if not value or "Traceback" in value or "/" in value or "\\" in value:
        return "worker error"
    return value[:160]
