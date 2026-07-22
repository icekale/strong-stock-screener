from datetime import datetime
from pathlib import Path

import pytest

from app.models import (
    KlineBar,
    SentimentPercentileFactor,
    SentimentPercentileFactors,
    SentimentPercentilePoint,
    SentimentPercentileResponse,
    StrongStockDataUnavailable,
)
from app.services.market_sentiment_percentile_store import MarketSentimentPercentileStore
from app.services.market_sentiment_percentile_service import (
    MarketSentimentPercentileService,
    filter_completed_daily_bars,
)
from tests.market_sentiment_fixtures import make_test_bars


class FakeProvider:
    source_name = "fixture TickFlow"

    def __init__(self, bars: list[KlineBar]) -> None:
        self.bars = bars
        self.calls = 0
        self.error: Exception | None = None

    def get_klines(self, symbol: str, count: int = 220) -> list[KlineBar]:
        self.calls += 1
        if self.error is not None:
            raise self.error
        assert symbol == "000985.SH"
        return self.bars[-count:]


def service_for(tmp_path: Path, provider: FakeProvider) -> MarketSentimentPercentileService:
    return MarketSentimentPercentileService(
        provider=provider,
        store=MarketSentimentPercentileStore(tmp_path),
    )


def snapshot(
    *, model_version: str = "market-sentiment-percentile-v1"
) -> SentimentPercentileResponse:
    factor = SentimentPercentileFactor(score=50, raw_value=0, raw_unit="%")
    point = SentimentPercentilePoint(
        trade_date="2026-07-21",
        score=50,
        level="中性",
        factors=SentimentPercentileFactors(
            volume=factor,
            index_move_5d=factor,
            price_position=factor,
            amplitude_5d=factor,
            volume_trend=factor,
        ),
    )
    return SentimentPercentileResponse(
        model_version=model_version,
        weights={
            key: 0.2
            for key in ("volume", "index_move_5d", "price_position", "amplitude_5d", "volume_trend")
        },
        latest_complete_trade_date=point.trade_date,
        selected_trade_date=point.trade_date,
        selected=point,
        history=[point],
        generated_at="2026-07-22T15:20:00+08:00",
    )


def test_before_1510_excludes_current_local_date(tmp_path: Path) -> None:
    bars = make_test_bars(1020)
    bars[-1] = bars[-1].model_copy(update={"date": "2026-07-22"})
    bars[-2] = bars[-2].model_copy(update={"date": "2026-07-21"})
    provider = FakeProvider(bars)
    service = service_for(tmp_path, provider)

    result = service.get(now=datetime.fromisoformat("2026-07-22T15:09:00+08:00"))

    assert result.latest_complete_trade_date == "2026-07-21"


def test_completed_bar_filter_retains_latest_prior_bar_on_weekend() -> None:
    bars = make_test_bars(2)
    bars[-1] = bars[-1].model_copy(update={"date": "2026-07-24"})

    result = filter_completed_daily_bars(
        bars,
        now=datetime.fromisoformat("2026-07-25T10:00:00+08:00"),
    )

    assert result[-1].date == "2026-07-24"


def test_failed_refresh_returns_stale_successful_snapshot(tmp_path: Path) -> None:
    provider = FakeProvider(make_test_bars(1020))
    service = service_for(tmp_path, provider)
    cached = service.get(refresh=True)
    provider.error = RuntimeError("offline")

    stale = service.get(refresh=True)

    assert stale.cache_status == "stale"
    assert stale.history == cached.history
    assert "offline" not in stale.notes


def test_as_of_only_slices_existing_history(tmp_path: Path) -> None:
    result = service_for(tmp_path, FakeProvider(make_test_bars(1020))).get(as_of="2024-09-01")

    assert all(point.trade_date <= "2024-09-01" for point in result.history)
    assert result.selected == result.history[-1]


def test_as_of_before_cached_range_returns_explicit_empty_selection(tmp_path: Path) -> None:
    result = service_for(tmp_path, FakeProvider(make_test_bars(1020))).get(as_of="2022-01-02")

    assert result.history == []
    assert result.selected is None
    assert result.selected_trade_date is None


def test_same_day_cache_hit_does_not_call_provider_twice(tmp_path: Path) -> None:
    provider = FakeProvider(make_test_bars(1020))
    service = service_for(tmp_path, provider)
    now = datetime.fromisoformat("2026-07-22T16:00:00+08:00")

    service.get(refresh=True, now=now)
    service.get(now=now)

    assert provider.calls == 1


def test_corrupt_or_wrong_version_snapshot_is_ignored(tmp_path: Path) -> None:
    store = MarketSentimentPercentileStore(tmp_path)
    store.root_dir.mkdir(parents=True)
    store.latest_path.write_text("{bad json", encoding="utf-8")

    assert store.load() is None

    store.latest_path.write_text(
        snapshot(model_version="market-sentiment-percentile-v0").model_dump_json(),
        encoding="utf-8",
    )

    assert store.load() is None


def test_store_replaces_snapshot_from_json_tmp_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = MarketSentimentPercentileStore(tmp_path)
    replaced_from: list[Path] = []
    original_replace = Path.replace

    def record_replace(path: Path, target: Path) -> Path:
        replaced_from.append(path)
        return original_replace(path, target)

    monkeypatch.setattr(Path, "replace", record_replace)

    store.save(snapshot())

    assert replaced_from[0].suffix == ".tmp"
    assert replaced_from[0].name.endswith(".json.tmp")


def test_insufficient_history_raises_data_unavailable(tmp_path: Path) -> None:
    service = service_for(tmp_path, FakeProvider(make_test_bars(518)))

    with pytest.raises(StrongStockDataUnavailable):
        service.get(refresh=True)


def test_refresh_failure_does_not_expose_source_exception_details(tmp_path: Path) -> None:
    fake_key = "fake-api-key-123"
    provider = FakeProvider(make_test_bars(1020))
    service = service_for(tmp_path, provider)
    service.get(refresh=True)
    provider.error = RuntimeError(f"offline with api key {fake_key}")

    stale = service.get(refresh=True)

    assert fake_key not in " ".join(stale.notes)
    assert fake_key not in " ".join(status.detail for status in stale.source_status)


def test_returned_cached_response_is_a_deep_copy(tmp_path: Path) -> None:
    provider = FakeProvider(make_test_bars(1020))
    service = service_for(tmp_path, provider)
    now = datetime.fromisoformat("2026-07-22T16:00:00+08:00")
    first = service.get(refresh=True, now=now)
    first.history.clear()

    cached = service.get(now=now)

    assert cached.history
