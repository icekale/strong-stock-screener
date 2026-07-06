from __future__ import annotations

from pathlib import Path

from app.models import (
    AuctionModelPredictionItem,
    AuctionModelTop3Response,
    AuctionSnapshotItem,
    AuctionSnapshotResponse,
    AuctionTop3LiveConfirmationItem,
    AuctionTop3LiveConfirmationResponse,
    AuctionTop3RealtimeSnapshot,
    StrongStockSourceStatus,
)


OVERHEAT_GAP_PCT = 7.0
WEAKENING_GAP_PCT = 3.0
MIN_TURNOVER_CNY = 100_000_000
MIN_TURNOVER_RATE = 3.0
MODEL_LIQUIDITY_RISK_KEYWORDS = ("流通市值低于20亿", "近3日日均成交额低于1亿")


def confirm_auction_top3_item(
    model_item: AuctionModelPredictionItem,
    realtime_item: AuctionSnapshotItem | None,
) -> AuctionTop3LiveConfirmationItem:
    reasons: list[str] = []
    risk_flags: list[str] = []
    data_quality: list[str] = []
    confirmation = "watch"
    realtime = _realtime_snapshot(realtime_item) if realtime_item is not None else None

    if model_item.bucket == "selected":
        reasons.append("模型入选Top3")
    else:
        reasons.append("模型未入选Top3执行桶")

    if any(keyword in flag for flag in model_item.risk_flags for keyword in MODEL_LIQUIDITY_RISK_KEYWORDS):
        risk_flags.append("模型流动性风险")
        confirmation = "reject"

    if realtime_item is None:
        data_quality.append("realtime_missing")
        reasons.append("实时竞价数据缺失")
    else:
        open_gap = realtime_item.open_gap_pct
        current_pct = realtime_item.current_pct_change
        turnover_cny = realtime_item.turnover_cny or 0
        turnover_rate = realtime_item.turnover_rate or 0
        has_volume = turnover_cny >= MIN_TURNOVER_CNY or turnover_rate >= MIN_TURNOVER_RATE

        if has_volume:
            reasons.append("实时量能通过")
        else:
            reasons.append("实时量能不足")

        if open_gap is not None and open_gap >= OVERHEAT_GAP_PCT and not realtime_item.theme_resonance:
            risk_flags.append("高开过热")
            confirmation = "reject"
        if current_pct is not None and current_pct < 0:
            risk_flags.append("实时涨幅转负")
            confirmation = "reject"
        if open_gap is not None and current_pct is not None and current_pct <= open_gap - WEAKENING_GAP_PCT:
            risk_flags.append("开盘后明显走弱")
            confirmation = "reject"
        if realtime_item.theme_resonance:
            reasons.append("题材共振")

        if (
            confirmation != "reject"
            and model_item.bucket == "selected"
            and has_volume
            and current_pct is not None
            and current_pct >= 0
        ):
            confirmation = "buyable"

    return AuctionTop3LiveConfirmationItem(
        symbol=model_item.symbol,
        name=model_item.name,
        model_rank=model_item.rank,
        model_bucket=model_item.bucket,
        prob_3pct=model_item.prob_3pct,
        confirmation=confirmation,
        realtime=realtime,
        reasons=reasons,
        risk_flags=[*model_item.risk_flags, *risk_flags],
        data_quality=[*model_item.data_quality, *data_quality],
    )


def build_auction_top3_live_confirmation(
    model_run: AuctionModelTop3Response,
    snapshot: AuctionSnapshotResponse | None,
) -> AuctionTop3LiveConfirmationResponse:
    realtime_by_symbol = {item.symbol: item for item in snapshot.items} if snapshot is not None else {}
    items = [
        confirm_auction_top3_item(item, realtime_by_symbol.get(item.symbol))
        for item in model_run.items
    ]
    source_status = [
        StrongStockSourceStatus(
            source="竞价Top3实盘确认",
            status="success",
            detail=f"读取Top3缓存 {len(model_run.items)} 只，匹配实时竞价 {sum(1 for item in items if item.realtime is not None)} 只",
        )
    ]
    if snapshot is not None:
        source_status.extend(snapshot.source_status)
    return AuctionTop3LiveConfirmationResponse(
        trade_date=model_run.trade_date,
        model_run_id=model_run.run_id,
        cache_status=model_run.cache_status,
        items=items,
        source_status=source_status,
    )


def _realtime_snapshot(item: AuctionSnapshotItem) -> AuctionTop3RealtimeSnapshot:
    return AuctionTop3RealtimeSnapshot(
        last_price=item.last_price,
        current_pct_change=item.current_pct_change,
        open_gap_pct=item.open_gap_pct,
        turnover_cny=item.turnover_cny,
        turnover_rate=item.turnover_rate,
        quote_time=item.quote_time,
    )


class AuctionTop3LiveConfirmationStore:
    def __init__(self, data_dir: Path) -> None:
        self.root_dir = data_dir / "auction_top3_live_confirmations"

    def save(self, result: AuctionTop3LiveConfirmationResponse) -> AuctionTop3LiveConfirmationResponse:
        path = self.root_dir / "confirmations" / f"{result.trade_date}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
        return result
