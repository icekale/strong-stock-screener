from __future__ import annotations

import json
import pickle
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol

import httpx

from app.models import (
    AuctionModelBacktestSummary,
    AuctionModelPredictionItem,
    AuctionModelTop3Response,
    KlineBar,
    StrongStockCandidate,
    StrongStockSourceStatus,
)

FEATURE_VERSION = "morning_auction_features_v1"
GUARD_RULE = "10:00收益<0则退出，否则持有到T+1收盘"
MIN_FLOAT_MARKET_CAP = 2_000_000_000
MIN_AVG_AMOUNT_3D = 100_000_000


class AuctionModelDataError(RuntimeError):
    pass


class AuctionModelResultStore:
    def __init__(self, data_dir: Path) -> None:
        self.root_dir = data_dir / "auction_model"
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def load_top3(self, trade_date: str) -> AuctionModelTop3Response | None:
        path = self._top3_path(trade_date)
        if not path.exists():
            return None
        payload = _read_json(path)
        return AuctionModelTop3Response.model_validate(payload).model_copy(
            update={"cache_status": "cached"}
        )

    def save_top3(self, result: AuctionModelTop3Response) -> None:
        path = self._top3_path(result.trade_date)
        path.write_text(
            json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def _top3_path(self, trade_date: str) -> Path:
        date_key = _normalize_date_key(trade_date)
        return self.root_dir / f"top3_{date_key}.json"


@dataclass(frozen=True)
class DailyBar:
    trade_date: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: float
    turnover_rate: float | None = None


class AuctionModelSource(Protocol):
    source_name: str

    def prefetch_daily_window(self, *, feature_end_date: str, lookback: int) -> None:
        ...

    def candidate_universe(self, trade_date: str) -> list[dict[str, object]]:
        ...

    def daily_bars(self, symbol: str, *, end_date: str, lookback: int) -> list[DailyBar]:
        ...


class CandidateProvider(Protocol):
    def get_candidates(self, trade_date: str) -> list[StrongStockCandidate]:
        ...


class KlineProvider(Protocol):
    def get_klines(self, symbol: str, count: int = 220) -> list[KlineBar]:
        ...


class FreeStockDbClient:
    def __init__(self, *, base_url: str, timeout_seconds: float = 10.0) -> None:
        self._base_url = base_url.rstrip("/") + "/"
        self._timeout_seconds = timeout_seconds

    def vals(self, *, table: str, k1: str, k2: str) -> list[Any]:
        params = {"cmd": "vals", "t": table, "k1": k1, "k2": k2}
        try:
            with httpx.Client(timeout=self._timeout_seconds) as client:
                response = client.get(self._base_url, params=params)
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPError as exc:
            raise AuctionModelDataError(f"free-stockdb 请求失败：{exc}") from exc
        except ValueError as exc:
            raise AuctionModelDataError("free-stockdb 返回了无效 JSON") from exc
        if not isinstance(payload, list):
            raise AuctionModelDataError("free-stockdb 返回结构异常：预期 list")
        return payload


class FreeStockDbAuctionModelSource:
    source_name = "free-stockdb"

    def __init__(self, *, base_url: str, timeout_seconds: float = 180.0) -> None:
        self._client = FreeStockDbClient(base_url=base_url, timeout_seconds=timeout_seconds)
        self._prefetched_rows_by_date: dict[str, list[dict[str, object]]] | None = None
        self._prefetched_bars_by_code: dict[str, list[DailyBar]] | None = None

    def prefetch_daily_window(self, *, feature_end_date: str, lookback: int) -> None:
        if lookback <= 0:
            raise ValueError("lookback must be positive")
        end_key = _normalize_date_key(feature_end_date)
        start_key = _start_key_for_lookback(end_key, lookback)
        rows = self._client.vals(table="日k", k1="all:", k2=f"fwd:{start_key},{end_key}")

        rows_by_date: dict[str, list[dict[str, object]]] = {}
        bars_by_code: dict[str, list[DailyBar]] = {}
        for row in rows:
            if not isinstance(row, dict) or "code" not in row or "date" not in row:
                continue
            date_key = str(row["date"])[:8]
            code = _raw_code(str(row["code"]))
            rows_by_date.setdefault(date_key, []).append(row)
            bars_by_code.setdefault(code, []).append(_daily_bar_from_row(row))
        for bars in bars_by_code.values():
            bars.sort(key=lambda bar: bar.trade_date)
        self._prefetched_rows_by_date = rows_by_date
        self._prefetched_bars_by_code = bars_by_code

    def candidate_universe(self, trade_date: str) -> list[dict[str, object]]:
        date_key = _normalize_date_key(trade_date)
        if self._prefetched_rows_by_date is None:
            rows = self._client.vals(table="日k", k1="all:", k2=f"key:{date_key}")
        else:
            rows = self._prefetched_rows_by_date.get(date_key, [])
        candidates: list[dict[str, object]] = []
        for row in rows:
            if not isinstance(row, dict) or "code" not in row:
                continue
            candidates.append(
                {
                    "symbol": _symbol_with_suffix(str(row["code"])),
                    "name": str(row.get("name", "")),
                    "is_st": bool(row.get("is_st", False)),
                    "is_suspended": False,
                    "listed_days": 9999,
                    "market_cap_float": _float_or_none(row.get("float_mv")),
                }
            )
        return candidates

    def daily_bars(self, symbol: str, *, end_date: str, lookback: int) -> list[DailyBar]:
        if lookback <= 0:
            raise ValueError("lookback must be positive")
        end_key = _normalize_date_key(end_date)
        code = _raw_code(symbol)
        cached = self._prefetched_bars_by_code.get(code) if self._prefetched_bars_by_code is not None else None
        if cached is not None:
            end_display = _display_date(end_key)
            bars = [bar for bar in cached if bar.trade_date <= end_display]
            return bars[-lookback:]

        start_key = _start_key_for_lookback(end_key, lookback)
        rows = self._client.vals(table="日k", k1=f"key:{code}", k2=f"fwd:{start_key},{end_key}")
        bars = [_daily_bar_from_row(row) for row in rows if isinstance(row, dict)]
        bars.sort(key=lambda bar: bar.trade_date)
        return bars[-lookback:]


class ProviderAuctionModelSource:
    source_name = "K线推理源"

    def __init__(
        self,
        *,
        candidate_provider: CandidateProvider,
        kline_provider: KlineProvider,
    ) -> None:
        self._candidate_provider = candidate_provider
        self._kline_provider = kline_provider
        self._amount_estimated_symbols: set[str] = set()

    def prefetch_daily_window(self, *, feature_end_date: str, lookback: int) -> None:
        _ = (feature_end_date, lookback)

    def candidate_universe(self, trade_date: str) -> list[dict[str, object]]:
        try:
            candidates = self._candidate_provider.get_candidates(trade_date)
        except Exception:
            return []
        return [_candidate_row_from_provider(candidate) for candidate in candidates]

    def daily_bars(self, symbol: str, *, end_date: str, lookback: int) -> list[DailyBar]:
        try:
            raw_bars = self._kline_provider.get_klines(symbol, count=max(lookback, 2))
        except Exception:
            return []
        end_display = _display_date(_normalize_date_key(end_date))
        bars: list[DailyBar] = []
        amount_estimated = False
        for raw_bar in raw_bars:
            bar_date = _display_date(_normalize_date_key(raw_bar.date))
            if bar_date > end_display:
                continue
            amount = _kline_amount(raw_bar)
            if amount is None:
                amount = raw_bar.volume * raw_bar.close
                amount_estimated = True
            bars.append(
                DailyBar(
                    trade_date=bar_date,
                    open=raw_bar.open,
                    high=raw_bar.high,
                    low=raw_bar.low,
                    close=raw_bar.close,
                    volume=raw_bar.volume,
                    amount=amount,
                    turnover_rate=_float_or_none(getattr(raw_bar, "turnover_rate", None)),
                )
            )
        if amount_estimated:
            self._amount_estimated_symbols.add(symbol)
        bars.sort(key=lambda bar: bar.trade_date)
        return bars[-lookback:]

    def data_quality_flags(self, symbol: str) -> list[str]:
        flags = ["no_auction_snapshot", "uses_provider_daily_bar"]
        if symbol in self._amount_estimated_symbols:
            flags.append("daily_amount_estimated")
        return flags


class AuctionModelService:
    def __init__(
        self,
        *,
        source: AuctionModelSource,
        model_path: Path,
        metadata_path: Path,
        performance_path: Path | None,
        lookback: int = 120,
        top_n: int = 3,
        max_items: int = 50,
    ) -> None:
        self._source = source
        self._model_path = model_path
        self._metadata_path = metadata_path
        self._performance_path = performance_path
        self._lookback = lookback
        self._top_n = top_n
        self._max_items = max_items

    def predict_top3(self, trade_date: str) -> AuctionModelTop3Response:
        rows, feature_end_date = build_live_prediction_rows(
            self._source,
            trade_date=trade_date,
            lookback=self._lookback,
        )
        scored_rows = score_rows_with_model(
            rows,
            model_path=self._model_path,
            metadata_path=self._metadata_path,
        )
        metadata = _read_json(self._metadata_path)
        items = prediction_items_from_scored_rows(
            scored_rows,
            top_n=self._top_n,
            max_items=self._max_items,
        )
        return AuctionModelTop3Response(
            trade_date=trade_date,
            feature_end_date=feature_end_date,
            model_version=str(metadata.get("model_version") or self._model_path.name),
            feature_version=str(metadata.get("feature_version") or FEATURE_VERSION),
            guard_rule=GUARD_RULE,
            backtest=load_backtest_summary(self._performance_path),
            items=items,
            source_status=[
                StrongStockSourceStatus(
                    source=getattr(self._source, "source_name", "K线源"),
                    status="success",
                    detail=f"使用 {feature_end_date} 及以前日K构建特征，生成 {len(rows)} 个候选特征行",
                ),
                StrongStockSourceStatus(
                    source="早盘竞价模型",
                    status="success",
                    detail=f"模型 {self._model_path.name}，Top{self._top_n} 试运行",
                ),
                StrongStockSourceStatus(
                    source="09:25竞价快照",
                    status="stale",
                    detail="free-stockdb 暂无历史09:25快照；当前信号使用上一交易日日K，实盘需结合真实竞价确认",
                ),
            ],
        )


def build_live_prediction_rows(
    source: AuctionModelSource,
    *,
    trade_date: str,
    lookback: int,
    max_calendar_backtrack: int = 14,
) -> tuple[list[dict[str, object]], str]:
    feature_end_date = _previous_feature_date(
        source,
        trade_date=trade_date,
        max_calendar_backtrack=max_calendar_backtrack,
    )
    source.prefetch_daily_window(feature_end_date=feature_end_date, lookback=lookback)
    candidates = source.candidate_universe(feature_end_date)

    rows: list[dict[str, object]] = []
    for candidate in candidates:
        symbol = str(candidate["symbol"])
        name = str(candidate.get("name", ""))
        bars = source.daily_bars(symbol, end_date=feature_end_date, lookback=lookback)
        if len(bars) < 2:
            continue
        if any(bar.close <= 0 or bar.volume <= 0 or bar.amount <= 0 for bar in bars[-2:]):
            continue
        risk_flags = _candidate_risk_flags(
            symbol=symbol,
            name=name,
            listed_days=int(candidate.get("listed_days", 9999)),
            is_st=bool(candidate.get("is_st", False)),
            is_suspended=bool(candidate.get("is_suspended", False)),
            daily_bars=bars,
        )
        if risk_flags:
            continue
        features = build_feature_row(
            market_cap_float=_float_or_none(candidate.get("market_cap_float")),
            daily_bars=bars,
        )
        rows.append(
            {
                "trade_date": trade_date,
                "feature_end_date": feature_end_date,
                "symbol": symbol,
                "name": name,
                "features": features,
                "prev_close_price": bars[-1].close,
                "market_cap_float": _float_or_none(candidate.get("market_cap_float")),
                "avg_amount_3d": _average_amount(bars, 3),
                "risk_flags": risk_flags,
                "data_quality": _source_data_quality_flags(source, symbol),
            }
        )
    return rows, feature_end_date


def prediction_items_from_scored_rows(
    rows: Sequence[dict[str, object]],
    *,
    top_n: int,
    max_items: int,
) -> list[AuctionModelPredictionItem]:
    ranked = sorted(rows, key=lambda row: float(row.get("prob_3pct") or 0.0), reverse=True)
    items: list[AuctionModelPredictionItem] = []
    selected_count = 0
    for rank, row in enumerate(ranked[:max_items], start=1):
        prob_3pct = float(row.get("prob_3pct") or 0.0)
        risk_flags = [str(flag) for flag in row.get("risk_flags", [])]
        risk_flags.extend(flag for flag in _liquidity_risk_flags(row) if flag not in risk_flags)
        if risk_flags:
            bucket = "avoid"
        elif selected_count < top_n:
            bucket = "selected"
            selected_count += 1
        elif prob_3pct >= 0.65:
            bucket = "attack"
        elif prob_3pct >= 0.35:
            bucket = "watch"
        else:
            bucket = "avoid"
        items.append(
            AuctionModelPredictionItem(
                symbol=str(row.get("symbol", "")),
                name=str(row.get("name", "")),
                prob_3pct=prob_3pct,
                bucket=bucket,
                rank=rank,
                prev_close_price=_float_or_none(row.get("prev_close_price")),
                market_cap_float=_float_or_none(row.get("market_cap_float"))
                or _float_or_none(_features(row).get("market_cap_float")),
                avg_amount_3d=_float_or_none(row.get("avg_amount_3d")),
                feature_end_date=str(row.get("feature_end_date") or ""),
                guard_rule=GUARD_RULE if bucket == "selected" else None,
                strategy_note="Top3试运行候选" if bucket == "selected" else "候选观察",
                trend_reasons=_trend_reasons(row),
                risk_flags=risk_flags,
                data_quality=[str(flag) for flag in row.get("data_quality", [])],
            )
        )
    return items


def _liquidity_risk_flags(row: dict[str, object]) -> list[str]:
    flags: list[str] = []
    market_cap_float = _float_or_none(row.get("market_cap_float"))
    if market_cap_float is None:
        market_cap_float = _float_or_none(_features(row).get("market_cap_float"))
    if market_cap_float is not None and market_cap_float < MIN_FLOAT_MARKET_CAP:
        flags.append("流通市值低于20亿")
    avg_amount_3d = _float_or_none(row.get("avg_amount_3d"))
    if avg_amount_3d is not None and avg_amount_3d < MIN_AVG_AMOUNT_3D:
        flags.append("近3日日均成交额低于1亿")
    return flags


def score_rows_with_model(
    rows: Sequence[dict[str, object]],
    *,
    model_path: Path,
    metadata_path: Path,
) -> list[dict[str, object]]:
    if not rows:
        return []
    metadata = _read_json(metadata_path)
    feature_names = [str(name) for name in metadata.get("feature_names", [])]
    if not feature_names:
        raise AuctionModelDataError("模型元数据缺少 feature_names")
    try:
        with model_path.open("rb") as handle:
            model = pickle.load(handle)
    except (ImportError, ModuleNotFoundError, OSError) as exc:
        raise AuctionModelDataError(f"模型加载失败，请确认 lightgbm/libomp 已安装：{exc}") from exc

    matrix = build_feature_matrix(rows, feature_names)
    try:
        import pandas as pd

        matrix_input = pd.DataFrame(matrix, columns=feature_names)
    except ImportError:
        matrix_input = matrix
    probabilities = model.predict_proba(matrix_input)
    scored: list[dict[str, object]] = []
    for row, probability in zip(rows, probabilities, strict=True):
        scored.append({**row, "prob_3pct": float(probability[1])})
    return scored


def build_feature_matrix(
    rows: Sequence[dict[str, object]],
    feature_names: Sequence[str],
) -> list[list[float]]:
    return [
        [_feature_value(_features(row).get(feature_name)) for feature_name in feature_names]
        for row in rows
    ]


def build_feature_row(
    *,
    market_cap_float: float | None,
    daily_bars: list[DailyBar],
) -> dict[str, float | int | None]:
    latest = daily_bars[-1] if daily_bars else None
    previous = daily_bars[-2] if len(daily_bars) >= 2 else None
    close_values = [bar.close for bar in daily_bars]
    volume_values = [bar.volume for bar in daily_bars]
    amount_values = [bar.amount for bar in daily_bars]

    row: dict[str, float | int | None] = {
        "market_cap_float": _round_or_none(market_cap_float),
        "prev_return": _pct_change(latest.close, previous.close) if latest and previous else None,
        "prev_turnover": latest.turnover_rate if latest else None,
        "return_3d": _window_return(close_values, 3),
        "return_5d": _window_return(close_values, 5),
        "volume_ratio_3d": _last_vs_average(volume_values, 3),
        "amount_ratio_3d": _last_vs_average(amount_values, 3),
        "close_vs_ma5": _close_vs_ma(close_values, 5),
        "close_vs_ma10": _close_vs_ma(close_values, 10),
        "close_vs_ma20": _close_vs_ma(close_values, 20),
        "new_high_60d": _new_high(close_values, 60),
        "sector_strength": None,
        "capital_strength": None,
        "auction_data_available": 0,
        "auction_return": None,
        "auction_volume_ratio": None,
        "auction_amount_ratio": None,
        "bid_ask_imbalance": None,
        "unmatched_buy_ratio": None,
    }
    row["risk_score"] = _risk_score(row)
    return row


def load_backtest_summary(path: Path | None) -> AuctionModelBacktestSummary | None:
    if path is None or not path.exists():
        return None
    payload = _read_json(path)
    metrics = payload.get("strict_metrics") or payload.get("base_metrics")
    if metrics is None and isinstance(payload.get("backtests"), dict):
        metrics = payload["backtests"].get("top_3")
    if not isinstance(metrics, dict):
        return None
    capital_return_pct = _capital_return_pct(payload)
    return AuctionModelBacktestSummary(
        period=[str(item) for item in payload.get("period", [])],
        sample_count=int(metrics.get("selected_count") or 0),
        win_rate=_float_or_none(metrics.get("win_rate")),
        avg_win=_float_or_none(metrics.get("avg_win")),
        avg_loss=_float_or_none(metrics.get("avg_loss")),
        payoff_ratio=_float_or_none(metrics.get("payoff_ratio")),
        profit_factor=_float_or_none(metrics.get("profit_factor")),
        expectancy=_float_or_none(metrics.get("expectancy")),
        average_return=_float_or_none(metrics.get("average_return")),
        breakeven_win_rate=_float_or_none(metrics.get("breakeven_win_rate")),
        capital_return_pct=capital_return_pct,
    )


def _previous_feature_date(
    source: AuctionModelSource,
    *,
    trade_date: str,
    max_calendar_backtrack: int,
) -> str:
    target = date.fromisoformat(trade_date)
    for days_back in range(1, max_calendar_backtrack + 1):
        candidate_date = (target - timedelta(days=days_back)).isoformat()
        if source.candidate_universe(candidate_date):
            return candidate_date
    raise AuctionModelDataError(f"{trade_date} 前 {max_calendar_backtrack} 天内没有可用日K候选池")


def _candidate_row_from_provider(candidate: StrongStockCandidate) -> dict[str, object]:
    name = candidate.name or ""
    return {
        "symbol": candidate.symbol,
        "name": name,
        "is_st": "ST" in name.upper(),
        "is_suspended": False,
        "listed_days": 9999,
        "market_cap_float": candidate.circulating_market_cap_cny or candidate.total_market_cap_cny,
    }


def _kline_amount(bar: KlineBar) -> float | None:
    amount = _float_or_none(getattr(bar, "amount", None))
    if amount is None or amount <= 0:
        return None
    return amount


def _source_data_quality_flags(source: AuctionModelSource, symbol: str) -> list[str]:
    flags = getattr(source, "data_quality_flags", None)
    if callable(flags):
        return [str(flag) for flag in flags(symbol)]
    return ["no_auction_snapshot", "uses_previous_daily_bar"]


def _candidate_risk_flags(
    *,
    symbol: str,
    name: str,
    listed_days: int,
    is_st: bool,
    is_suspended: bool,
    daily_bars: list[DailyBar],
) -> list[str]:
    risk_flags: list[str] = []
    if not _is_common_a_share_symbol(symbol) or _is_excluded_security_name(name):
        risk_flags.append("非普通A股")
    if is_st or "ST" in name.upper():
        risk_flags.append("ST股票")
    if listed_days < 100:
        risk_flags.append("上市不足100天")
    if is_suspended:
        risk_flags.append("停牌")
    if not daily_bars:
        risk_flags.append("日K缺失")
    else:
        latest = daily_bars[-1]
        if latest.close <= 0 or latest.amount <= 0:
            risk_flags.append("日K成交异常")
    return risk_flags


def _capital_return_pct(payload: dict[str, object]) -> float | None:
    strict_curves = payload.get("strict_capital_curves")
    if isinstance(strict_curves, dict):
        single = strict_curves.get("single_account_non_overlapping")
        if isinstance(single, dict):
            return _float_or_none(single.get("return_pct"))
    capital_curves = payload.get("capital_curves")
    if isinstance(capital_curves, dict):
        t1_close = capital_curves.get("return_t1_close")
        if isinstance(t1_close, dict):
            single = t1_close.get("single_account_non_overlapping")
            if isinstance(single, dict):
                return _float_or_none(single.get("return_pct"))
    return None


def _features(row: dict[str, object]) -> dict[str, object]:
    features = row.get("features")
    if isinstance(features, dict):
        return features
    return {}


def _feature_value(value: object) -> float:
    if value is None:
        return 0.0
    return float(value)


def _trend_reasons(row: dict[str, object]) -> list[str]:
    features = row.get("features")
    if not isinstance(features, dict):
        return []
    reasons: list[str] = []
    return_5d = features.get("return_5d")
    if isinstance(return_5d, int | float):
        reasons.append(f"5日涨幅{float(return_5d):.2f}%")
    amount_ratio_3d = features.get("amount_ratio_3d")
    if isinstance(amount_ratio_3d, int | float):
        reasons.append(f"3日成交额比{float(amount_ratio_3d):.2f}")
    return reasons


def _risk_score(row: dict[str, float | int | None]) -> float:
    score = 0.0
    prev_return = row.get("prev_return")
    if isinstance(prev_return, int | float) and prev_return <= -3:
        score += 10
    return score


def _pct_change(value: float | None, base: float | None) -> float | None:
    if value is None or base is None or base == 0:
        return None
    return round((value / base - 1) * 100, 4)


def _window_return(values: list[float], window: int) -> float | None:
    if len(values) < window or values[-window] == 0:
        return None
    return round((values[-1] / values[-window] - 1) * 100, 4)


def _last_vs_average(values: list[float], window: int) -> float | None:
    if len(values) < window:
        return None
    base_values = values[-window:-1]
    if not base_values:
        return None
    average = sum(base_values) / len(base_values)
    if average == 0:
        return None
    return round(values[-1] / average, 6)


def _average_amount(bars: list[DailyBar], window: int) -> float | None:
    if len(bars) < window:
        return None
    return round(sum(bar.amount for bar in bars[-window:]) / window, 2)


def _close_vs_ma(values: list[float], window: int) -> float | None:
    if len(values) < window:
        return 0.0
    average = sum(values[-window:]) / window
    if average == 0:
        return None
    return round((values[-1] / average - 1) * 100, 4)


def _new_high(values: list[float], window: int) -> int:
    if not values:
        return 0
    recent = values[-window:]
    return int(values[-1] >= max(recent))


def _daily_bar_from_row(row: dict[str, object]) -> DailyBar:
    return DailyBar(
        trade_date=_display_date(row["date"]),
        open=float(row["open"]),
        high=float(row["high"]),
        low=float(row["low"]),
        close=float(row["close"]),
        volume=float(row["volume"]),
        amount=float(row["amount"]),
        turnover_rate=_float_or_none(row.get("turnover")),
    )


def _normalize_date_key(value: str | date) -> str:
    if isinstance(value, date):
        return value.strftime("%Y%m%d")
    text = str(value).strip()
    if len(text) == 8 and text.isdigit():
        return text
    if len(text) == 10:
        return date.fromisoformat(text).strftime("%Y%m%d")
    raise ValueError("date must be YYYY-MM-DD or YYYYMMDD")


def _display_date(value: object) -> str:
    text = str(value)[:8]
    parsed = datetime.strptime(text, "%Y%m%d").date()
    return parsed.isoformat()


def _start_key_for_lookback(end_key: str, lookback: int) -> str:
    end = datetime.strptime(end_key, "%Y%m%d").date()
    calendar_days = max(lookback * 3 + 10, lookback + 10)
    return (end - timedelta(days=calendar_days)).strftime("%Y%m%d")


def _raw_code(symbol: str) -> str:
    text = str(symbol).strip().upper()
    if "." in text:
        text = text.split(".", 1)[0]
    if len(text) > 6 and text[:2] in {"SH", "SZ", "BJ"}:
        text = text[2:]
    return text


def _symbol_with_suffix(code: str) -> str:
    raw = _raw_code(code)
    if raw.startswith(("920", "8", "4")):
        suffix = "BJ"
    elif raw.startswith(("6", "9")):
        suffix = "SH"
    else:
        suffix = "SZ"
    return f"{raw}.{suffix}"


def _is_common_a_share_symbol(symbol: str) -> bool:
    code, market = _split_symbol(symbol)
    prefixes_by_market = {
        "SH": ("600", "601", "603", "605", "688"),
        "SZ": ("000", "001", "002", "003", "300", "301"),
    }
    prefixes = prefixes_by_market.get(market)
    return bool(prefixes and len(code) == 6 and code.startswith(prefixes))


def _split_symbol(symbol: str) -> tuple[str, str]:
    normalized = symbol.strip().upper()
    if "." in normalized:
        code, market = normalized.rsplit(".", maxsplit=1)
        return code, market
    return normalized, ""


def _is_excluded_security_name(name: str) -> bool:
    upper_name = name.upper()
    excluded_tokens = ("ETF", "LOF", "基金", "债", "REIT", "退")
    return upper_name.startswith(("C", "N")) or any(token in upper_name for token in excluded_tokens)


def _float_or_none(value: object) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def _round_or_none(value: float | None) -> float | None:
    return None if value is None else round(float(value), 6)


def _read_json(path: Path) -> dict[str, object]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise AuctionModelDataError(f"{path} 不是 JSON object")
    return payload
