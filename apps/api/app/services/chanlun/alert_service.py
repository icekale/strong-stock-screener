from __future__ import annotations

from app.models import ChanlunAlertListResponse, ChanlunAlertRefreshResponse, ChanlunPeriod
from app.services.chanlun.alerts import ChanlunAlertStore


class ChanlunAlertService:
    def __init__(self, *, analysis_service: object, store: ChanlunAlertStore) -> None:
        self.analysis_service = analysis_service
        self.store = store

    def refresh(
        self,
        symbol: str,
        *,
        period: ChanlunPeriod,
        lookback: int,
    ) -> ChanlunAlertRefreshResponse:
        analysis = self.analysis_service.analysis(
            symbol,
            period=period,
            lookback=lookback,
            include_observing=False,
        )
        if analysis.availability not in {"ready", "stale"}:
            return ChanlunAlertRefreshResponse(
                symbol=analysis.symbol,
                period=period,
                source_status=analysis.source_status,
            )
        observation = self.store.observe(analysis.symbol, period, analysis.signals)
        return ChanlunAlertRefreshResponse(
            symbol=analysis.symbol,
            period=period,
            baselined=observation.baselined,
            created=observation.created,
            source_status=analysis.source_status,
        )

    def list(self, *, symbol: str | None = None, limit: int = 100) -> ChanlunAlertListResponse:
        return ChanlunAlertListResponse(items=self.store.list(symbol=symbol, limit=limit))
