from __future__ import annotations

from pathlib import Path

from app.models import (
    EtfHolderPosition,
    EtfRadarOverviewResponse,
    EtfSharePoint,
    HuijinEtfBaseline,
    MarginMarketPoint,
)
from app.services.capital_signal_store import CapitalSignalStore


def _huijin_baseline(
    *,
    report_period: str = "2025-12-31",
    pool_version: str = "huijin-public-v1",
) -> HuijinEtfBaseline:
    return HuijinEtfBaseline(
        baseline_id=f"{report_period}:{pool_version}:510300.SH",
        pool_version=pool_version,
        symbol="510300.SH",
        name="沪深300ETF华泰柏瑞",
        index_name="沪深300",
        role="core",
        paired_symbol="159919.SZ",
        report_period=report_period,
        baseline_total_shares=88_826_848_719,
        confirmed_huijin_shares=73_513_100_000,
        confirmed_huijin_holding_pct=82.76,
        source_kind="derived",
        source="基金持有人披露持仓与比例推导",
    )


def test_store_round_trips_margin_and_share_history(tmp_path: Path) -> None:
    store = CapitalSignalStore(tmp_path)
    margins = [
        MarginMarketPoint(
            trade_date="2026-07-17",
            market="SSE",
            financing_balance_cny=10_000,
            securities_lending_balance_cny=500,
            margin_balance_cny=10_500,
        )
    ]
    shares = [
        EtfSharePoint(
            trade_date="2026-07-17",
            symbol="510300.SH",
            name="沪深300ETF",
            total_shares=12_000_000,
            close=4.25,
        )
    ]

    store.save_margin_history(margins)
    store.save_share_history(shares)

    assert store.load_margin_history() == margins
    assert store.load_share_history() == shares
    assert not list((tmp_path / "capital-signals").glob("*.tmp"))


def test_store_returns_empty_history_for_missing_or_corrupt_files(tmp_path: Path) -> None:
    store = CapitalSignalStore(tmp_path)

    assert store.load_margin_history() == []
    assert store.load_share_history() == []

    store.root_dir.mkdir(parents=True)
    store.margin_history_path.write_text("not json", encoding="utf-8")
    store.share_history_path.write_text("{}", encoding="utf-8")

    assert store.load_margin_history() == []
    assert store.load_share_history() == []


def test_store_keeps_latest_400_margin_trade_dates(tmp_path: Path) -> None:
    store = CapitalSignalStore(tmp_path)
    rows = [
        MarginMarketPoint(
            trade_date=f"2026-{index // 31 + 1:02d}-{index % 31 + 1:02d}",
            market="SSE",
        )
        for index in range(420)
    ]

    store.save_margin_history(rows)

    saved = store.load_margin_history()
    assert len(saved) == 400
    assert saved[0] == rows[20]


def test_store_round_trips_latest_snapshot(tmp_path: Path) -> None:
    store = CapitalSignalStore(tmp_path)
    snapshot = EtfRadarOverviewResponse(
        generated_at="2026-07-19T09:31:00+08:00",
        trade_date="2026-07-19",
        as_of="2026-07-19T09:31:00+08:00",
        signal_stage="intraday",
        model_version="heuristic-v1",
    )

    store.save_snapshot(snapshot)

    assert store.load_snapshot() == snapshot


def test_store_ignores_corrupt_snapshot(tmp_path: Path) -> None:
    store = CapitalSignalStore(tmp_path)
    store.root_dir.mkdir(parents=True)
    store.snapshot_path.write_text("[]", encoding="utf-8")

    assert store.load_snapshot() is None


def test_store_round_trips_holder_reports(tmp_path: Path) -> None:
    store = CapitalSignalStore(tmp_path)
    positions = [
        EtfHolderPosition(
            symbol="510300.SH",
            name="300ETF",
            report_period="2025-12-31",
            entity_name="中央汇金投资有限责任公司",
            shares=35_654_600_000,
            holding_pct=40.14,
            change_shares=1_000_000,
            source="新浪财经基金持有人",
        )
    ]

    store.save_holder_reports(positions)

    assert store.load_holder_reports() == positions


def test_store_round_trips_huijin_baselines_without_temp_residue(tmp_path: Path) -> None:
    store = CapitalSignalStore(tmp_path)
    baselines = [_huijin_baseline()]

    store.save_huijin_baselines(baselines)

    assert store.huijin_baselines_path == (
        tmp_path / "capital-signals" / "huijin-etf-baselines.json"
    )
    assert store.load_huijin_baselines() == baselines
    assert not list(store.root_dir.glob("*.tmp"))


def test_store_huijin_baseline_save_replaces_full_versioned_snapshot(
    tmp_path: Path,
) -> None:
    store = CapitalSignalStore(tmp_path)
    old_baseline = _huijin_baseline()
    replacement = _huijin_baseline(
        report_period="2026-06-30",
        pool_version="huijin-public-v2",
    )

    store.save_huijin_baselines([old_baseline])
    store.save_huijin_baselines([old_baseline])

    assert store.load_huijin_baselines() == [old_baseline]

    store.save_huijin_baselines([replacement])

    assert store.load_huijin_baselines() == [replacement]


def test_store_returns_empty_huijin_baselines_for_missing_or_corrupt_file(
    tmp_path: Path,
) -> None:
    store = CapitalSignalStore(tmp_path)

    assert store.load_huijin_baselines() == []

    store.root_dir.mkdir(parents=True)
    store.huijin_baselines_path.write_text("not json", encoding="utf-8")

    assert store.load_huijin_baselines() == []
