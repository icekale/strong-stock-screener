from __future__ import annotations

from app.models import ChanlunAnalysisResponse, ChanlunPaperOrder, ChanlunPeriod
from app.services.chanlun.paper import ChanlunPaperOrderStore


class ChanlunPaperOrderService:
    def __init__(
        self,
        *,
        analysis_service: object,
        quote_provider: object | None = None,
        store: ChanlunPaperOrderStore,
        initial_cash: float = 100_000,
    ) -> None:
        self.analysis_service = analysis_service
        self.quote_provider = quote_provider
        self.store = store
        self.initial_cash = initial_cash

    def create_draft(
        self,
        symbol: str,
        *,
        quantity: int,
        lookback: int,
    ) -> ChanlunPaperOrder:
        analyses = {
            period: self.analysis_service.analysis(
                symbol,
                period=period,
                lookback=lookback,
                include_observing=False,
            )
            for period in ("1d", "60m", "30m", "5m")
        }
        reasons, rejection_reasons = _draft_reasons(analyses)
        five_minute = analyses["5m"]
        reference_price = five_minute.bars[-1].close if five_minute.bars else 0.01
        if reference_price <= 0:
            reference_price = 0.01
        return self.store.create_draft(
            symbol=five_minute.symbol,
            quantity=quantity,
            reference_price=reference_price,
            reasons=reasons or rejection_reasons,
            signal_snapshot=_signal_snapshot(analyses),
            rule_version=five_minute.rule_version,
            status="rejected" if rejection_reasons else "awaiting_confirmation",
            rejection_reason="；".join(rejection_reasons) if rejection_reasons else None,
        )

    def approve(self, order_id: str) -> ChanlunPaperOrder:
        return self.store.approve(order_id, initial_cash=self.initial_cash)

    def cancel(self, order_id: str) -> ChanlunPaperOrder:
        return self.store.cancel(order_id)

    def fill(self, order_id: str) -> ChanlunPaperOrder:
        order = self.store.get(order_id)
        if order.status != "simulated_open":
            raise ValueError("只有模拟挂单可以更新成交")
        if self.quote_provider is None:
            raise ValueError("TickFlow 实时行情未配置")
        quotes = self.quote_provider.get_quotes([order.symbol])
        quote = next((item for item in quotes if item.symbol == order.symbol), None)
        if (
            quote is None
            or getattr(quote, "last_price", None) is None
            or quote.last_price <= 0
            or not getattr(quote, "quote_time", None)
        ):
            raise ValueError("TickFlow 未返回有效实时行情")
        return self.store.fill(
            order_id,
            latest_price=quote.last_price,
            quote_time=quote.quote_time,
            initial_cash=self.initial_cash,
        )

    def account(self):
        account = self.store.account(initial_cash=self.initial_cash)
        if self.quote_provider is None or not account.positions:
            return account
        try:
            quotes = self.quote_provider.get_quotes([item.symbol for item in account.positions])
        except Exception:
            return account
        latest_prices = {
            item.symbol: item.last_price
            for item in quotes
            if (
                getattr(item, "last_price", None) is not None
                and item.last_price > 0
                and getattr(item, "quote_time", None)
            )
        }
        quote_times = {
            item.symbol: item.quote_time
            for item in quotes
            if item.symbol in latest_prices and getattr(item, "quote_time", None)
        }
        return self.store.account(
            initial_cash=self.initial_cash,
            latest_prices=latest_prices,
            latest_quote_times=quote_times,
        )


def _draft_reasons(
    analyses: dict[ChanlunPeriod, ChanlunAnalysisResponse],
) -> tuple[list[str], list[str]]:
    reasons: list[str] = []
    rejection_reasons: list[str] = []
    if any(analysis.availability != "ready" for analysis in analyses.values()):
        rejection_reasons.append("多周期结构数据未全部就绪")

    daily = analyses["1d"]
    daily_signal = _latest_confirmed_signal(daily)
    daily_divergence = _latest_confirmed_divergence_type(daily)
    if daily_signal and daily_signal.type.endswith("sell"):
        rejection_reasons.append("日线存在确认卖出结构")
    if daily_divergence == "top":
        rejection_reasons.append("日线存在确认顶背驰风险")

    higher = [analyses["60m"], analyses["30m"]]
    higher_buy = next((analysis for analysis in higher if _is_latest_confirmed_buy(analysis)), None)
    if higher_buy is None:
        rejection_reasons.append("60分钟与30分钟均无确认买点")
    else:
        reasons.append(f"{_period_label(higher_buy.period)}确认买点")

    if not _is_latest_confirmed_buy(analyses["5m"]):
        rejection_reasons.append("5分钟无确认买点")
    else:
        reasons.append("5分钟确认买点")
    return reasons, rejection_reasons


def _latest_confirmed_signal(analysis: ChanlunAnalysisResponse):
    return next(
        (signal for signal in reversed(analysis.signals) if signal.status in {"confirmed", "final"}),
        None,
    )


def _latest_confirmed_divergence_type(analysis: ChanlunAnalysisResponse) -> str | None:
    divergence = _latest_confirmed_divergence(analysis)
    return divergence.type if divergence else None


def _latest_confirmed_divergence(analysis: ChanlunAnalysisResponse):
    return next(
        (item for item in reversed(analysis.divergences) if item.status in {"confirmed", "final"}),
        None,
    )


def _signal_snapshot(
    analyses: dict[ChanlunPeriod, ChanlunAnalysisResponse],
) -> dict[str, object]:
    return {
        period: {
            "availability": analysis.availability,
            "signal": (
                signal.model_dump(mode="json")
                if (signal := _latest_confirmed_signal(analysis))
                else None
            ),
            "divergence": (
                divergence.model_dump(mode="json")
                if (divergence := _latest_confirmed_divergence(analysis))
                else None
            ),
        }
        for period, analysis in analyses.items()
    }


def _is_latest_confirmed_buy(analysis: ChanlunAnalysisResponse) -> bool:
    signal = _latest_confirmed_signal(analysis)
    return signal is not None and signal.type.endswith("buy")


def _period_label(period: ChanlunPeriod) -> str:
    return {"1d": "日线", "60m": "60分钟", "30m": "30分钟", "5m": "5分钟"}[period]
