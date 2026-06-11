from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.config import get_settings
from app.models import StrongStockDataUnavailable, StrongStockSourceStatus
from app.providers.baidu_kline import BaiduKlineProvider
from app.providers.thsdk_candidates import ThsdkCandidateProvider
from app.providers.tickflow import TickFlowQuoteProvider
from app.providers.watchlist import WatchlistSnapshot
from app.services.runs import RunStore
from app.services.screener import StrongStockScreener


class ScreenRunRequest(BaseModel):
    trade_date: str
    limit: int = Field(default=30, ge=1, le=100)
    scan_limit: int = Field(default=40, ge=1, le=300)


def _cors_allow_origins() -> list[str]:
    settings = get_settings()
    return [origin.strip() for origin in settings.cors_allow_origins.split(",") if origin.strip()]


app = FastAPI(title="强势股选股 API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_allow_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/data-sources/status")
def data_source_status() -> dict[str, object]:
    candidate_provider = _candidate_provider()
    kline_provider = _kline_provider()
    quote_provider = _quote_provider()
    candidate_status = candidate_provider.status() if hasattr(candidate_provider, "status") else None
    kline_status = kline_provider.status() if hasattr(kline_provider, "status") else None
    quote_status = quote_provider.status() if hasattr(quote_provider, "status") else None
    return {
        "items": [
            (
                candidate_status
                or StrongStockSourceStatus(
                    source=candidate_provider.source_name,
                    status="success",
                    detail="候选池源已配置",
                )
            ).model_dump(mode="json"),
            (
                kline_status
                or StrongStockSourceStatus(
                    source=kline_provider.source_name,
                    status="success",
                    detail="K线源已配置",
                )
            ).model_dump(mode="json"),
            (
                quote_status
                or StrongStockSourceStatus(
                    source=getattr(quote_provider, "source_name", "quote_provider"),
                    status="disabled",
                    detail="报价源未配置",
                )
            ).model_dump(mode="json"),
        ]
    }


@app.post("/api/screen/runs")
def create_screen_run(request: ScreenRunRequest) -> dict[str, object]:
    screener = StrongStockScreener(
        candidate_provider=_candidate_provider(),
        kline_provider=_kline_provider(),
    )
    try:
        result = screener.screen(
            trade_date=request.trade_date,
            limit=request.limit,
            scan_limit=request.scan_limit,
            watchlist_snapshot=_watchlist_snapshot(),
        )
    except StrongStockDataUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    _run_store().save(result)
    return result.model_dump(mode="json")


@app.get("/api/screen/runs/latest")
def get_latest_screen_run() -> dict[str, object]:
    result = _run_store().load_latest()
    if result is None:
        raise HTTPException(status_code=404, detail="no screen run")
    return result.model_dump(mode="json")


def _candidate_provider() -> object:
    injected = getattr(app.state, "candidate_provider", None)
    if injected is not None:
        return injected
    return ThsdkCandidateProvider.from_installed_package()


def _kline_provider() -> object:
    injected = getattr(app.state, "kline_provider", None)
    if injected is not None:
        return injected
    settings = get_settings()
    return BaiduKlineProvider(timeout_seconds=settings.provider_timeout_seconds)


def _quote_provider() -> object:
    injected = getattr(app.state, "quote_provider", None)
    if injected is not None:
        return injected
    settings = get_settings()
    return TickFlowQuoteProvider(
        api_key=settings.tickflow_api_key,
        base_url=settings.tickflow_base_url,
        timeout_seconds=settings.provider_timeout_seconds,
    )


def _watchlist_snapshot() -> WatchlistSnapshot | None:
    return getattr(app.state, "watchlist_snapshot", None)


def _run_store() -> RunStore:
    runs_dir = getattr(app.state, "runs_dir", None)
    if runs_dir is not None:
        return RunStore(Path(runs_dir))
    return RunStore(get_settings().runs_dir)
