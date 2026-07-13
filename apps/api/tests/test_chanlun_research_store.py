from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from app.models import (
    CzscResearchSnapshot,
    CzscSignalEvidence,
    CzscSignalEvidenceSummary,
    CzscV2CandidateScore,
)
from app.services.chanlun import research_store as research_store_module
from app.services.chanlun.research_store import ChanlunResearchStore


PERIOD_BOUNDARIES = {
    "1d": "2026-07-10T15:00:00+08:00",
    "60m": "2026-07-10T14:00:00+08:00",
    "30m": "2026-07-10T14:30:00+08:00",
    "5m": "2026-07-10T14:55:00+08:00",
}
SHANGHAI = ZoneInfo("Asia/Shanghai")


def _evidence(
    input_snapshot_id: str,
    *,
    event_id: str = "buy3.structure.5m:2026-07-10T14:55:00+08:00:三买",
    occurred_at: str = "2026-07-10T14:55:00+08:00",
    last_closed_bar_at: str | None = None,
    engine_version: str = "1.0.0rc8",
    catalog_version: str = "czsc-v2-catalog-1",
    rule_version: str = "czsc-score-v2-rule-1",
) -> CzscSignalEvidence:
    return CzscSignalEvidence(
        id=event_id,
        catalog_id="buy3.structure",
        family="third_buy",
        role="primary",
        direction="bullish",
        period="5m",
        occurred_at=occurred_at,
        last_closed_bar_at=last_closed_bar_at or occurred_at,
        signal_name="cxt_third_buy_V230228",
        params={"di": 1},
        raw_key="5分钟_D1_三买辅助V230228",
        raw_value="三买_6笔_任意_0",
        reason="5分钟结构出现三买",
        input_snapshot_id=input_snapshot_id,
        engine_version=engine_version,
        catalog_version=catalog_version,
        rule_version=rule_version,
    )


def _snapshot(
    input_snapshot_id: str,
    *,
    symbol: str = "300308.SZ",
    calculated_at: str = "2026-07-10T15:00:00+08:00",
    engine_version: str = "1.0.0rc8",
    catalog_version: str = "czsc-v2-catalog-1",
    rule_version: str = "czsc-score-v2-rule-1",
    events: list[CzscSignalEvidence] | None = None,
) -> CzscResearchSnapshot:
    snapshot_events = events
    if snapshot_events is None:
        snapshot_events = [
            _evidence(
                input_snapshot_id,
                engine_version=engine_version,
                catalog_version=catalog_version,
                rule_version=rule_version,
            )
        ]
    return CzscResearchSnapshot(
        status="ready",
        symbol=symbol,
        current_states=snapshot_events[-1:],
        events=snapshot_events,
        last_closed_by_period=PERIOD_BOUNDARIES,
        input_snapshot_id=input_snapshot_id,
        score=25,
        eligible=True,
        engine_version=engine_version,
        catalog_version=catalog_version,
        rule_version=rule_version,
        calculated_at=calculated_at,
    )


def _candidate(
    symbol: str,
    baseline_rank: int,
    *,
    status: str = "ready",
    score: int | None = 80,
    shadow_rank: int | None = None,
) -> CzscV2CandidateScore:
    return CzscV2CandidateScore(
        symbol=symbol,
        status=status,
        score=score,
        shadow_rank=shadow_rank,
        eligible=status == "ready" and score is not None,
        baseline_rank=baseline_rank,
        evidence=[
            CzscSignalEvidenceSummary(
                id=f"summary-{symbol}",
                catalog_id="buy3.structure",
                family="third_buy",
                role="primary",
                direction="bullish",
                period="5m",
                occurred_at="2026-07-10T14:55:00+08:00",
                reason="5分钟结构出现三买",
            )
        ],
        input_snapshot_id=f"sha256:{symbol}",
    )


def test_store_saves_snapshot_idempotently_and_deduplicates_events(tmp_path: Path) -> None:
    store = ChanlunResearchStore(tmp_path / "nested" / "research.sqlite3")
    snapshot = _snapshot("sha256:a")

    store.save_snapshot(snapshot)
    store.save_snapshot(snapshot)

    assert store.load_snapshot("sha256:a") == snapshot
    assert store.count_events() == len(snapshot.events)


@pytest.mark.parametrize(
    "changed_field",
    [
        "symbol",
        "status",
        "engine_version",
        "catalog_version",
        "rule_version",
        "calculated_at",
        "payload_only",
    ],
)
def test_snapshot_id_rejects_any_conflicting_snapshot_and_rolls_back(
    tmp_path: Path,
    changed_field: str,
) -> None:
    store = ChanlunResearchStore(tmp_path / "research.sqlite3")
    original = _snapshot("sha256:a")
    store.save_snapshot(original)

    if changed_field == "symbol":
        conflicting = original.model_copy(update={"symbol": "600000.SH"})
    elif changed_field == "status":
        conflicting = CzscResearchSnapshot(
            status="unavailable",
            symbol=original.symbol,
            input_snapshot_id=original.input_snapshot_id,
            engine_version=original.engine_version,
            calculated_at=original.calculated_at,
        )
    elif changed_field == "engine_version":
        conflicting = _snapshot(
            "sha256:a",
            engine_version="1.0.1",
            events=[_evidence("sha256:a", engine_version="1.0.1")],
        )
    elif changed_field == "catalog_version":
        conflicting = _snapshot(
            "sha256:a",
            catalog_version="catalog-v2",
            events=[_evidence("sha256:a", catalog_version="catalog-v2")],
        )
    elif changed_field == "rule_version":
        conflicting = _snapshot(
            "sha256:a",
            rule_version="rule-v2",
            events=[_evidence("sha256:a", rule_version="rule-v2")],
        )
    elif changed_field == "calculated_at":
        conflicting = original.model_copy(update={"calculated_at": "2026-07-10T15:01:00+08:00"})
    else:
        conflicting = original.model_copy(update={"adjustment_mode": "qfq"})

    with pytest.raises(ValueError, match="immutable"):
        store.save_snapshot(conflicting)

    assert store.load_snapshot("sha256:a") == original
    assert store.count_events() == len(original.events)


def test_snapshot_id_requires_byte_identical_canonical_json(tmp_path: Path) -> None:
    store = ChanlunResearchStore(tmp_path / "research.sqlite3")
    snapshot = _snapshot("sha256:a")
    store.save_snapshot(snapshot)
    noncanonical_json = json.dumps(
        snapshot.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    )
    with store._connect() as connection:
        connection.execute(
            "UPDATE research_snapshots SET payload_json = ? WHERE input_snapshot_id = ?",
            (noncanonical_json, snapshot.input_snapshot_id),
        )

    with pytest.raises(ValueError, match="immutable"):
        store.save_snapshot(snapshot)

    with store._connect() as connection:
        stored_json = connection.execute(
            "SELECT payload_json FROM research_snapshots WHERE input_snapshot_id = ?",
            (snapshot.input_snapshot_id,),
        ).fetchone()[0]
    assert stored_json == noncanonical_json


def test_snapshot_id_rejects_indexed_identity_mismatch_without_repair(tmp_path: Path) -> None:
    store = ChanlunResearchStore(tmp_path / "research.sqlite3")
    snapshot = _snapshot("sha256:a")
    store.save_snapshot(snapshot)
    with store._connect() as connection:
        connection.execute(
            "UPDATE research_snapshots SET status = 'stale' WHERE input_snapshot_id = ?",
            (snapshot.input_snapshot_id,),
        )

    with pytest.raises(ValueError, match="immutable"):
        store.save_snapshot(snapshot)

    with store._connect() as connection:
        stored_status = connection.execute(
            "SELECT status FROM research_snapshots WHERE input_snapshot_id = ?",
            (snapshot.input_snapshot_id,),
        ).fetchone()[0]
    assert stored_status == "stale"


def test_duplicate_event_id_preserves_first_observed_provenance_after_prune(
    tmp_path: Path,
) -> None:
    store = ChanlunResearchStore(tmp_path / "research.sqlite3")
    first_event = _evidence(
        "sha256:first",
        event_id="stable-event",
        occurred_at="2024-01-01T14:55:00+08:00",
    )
    first_snapshot = _snapshot(
        "sha256:first",
        calculated_at="2024-01-01T15:00:00+08:00",
        events=[first_event],
    )
    later_event = _evidence(
        "sha256:later",
        event_id="stable-event",
        occurred_at="2024-01-01T14:55:00+08:00",
        last_closed_bar_at="2024-01-01T15:00:00+08:00",
    )
    later_snapshot = _snapshot(
        "sha256:later",
        symbol="600000.SH",
        calculated_at="2024-01-02T15:00:00+08:00",
        events=[later_event],
    )
    version_pointer = _snapshot(
        "sha256:pointer",
        symbol="600000.SH",
        calculated_at="2024-01-03T15:00:00+08:00",
        events=[],
    )
    store.save_snapshot(first_snapshot)
    store.save_snapshot(later_snapshot)
    store.save_snapshot(version_pointer)

    store.prune(
        now=datetime(2026, 7, 13, tzinfo=SHANGHAI),
        snapshot_days=180,
        evidence_days=180,
    )

    assert store.load_snapshot("sha256:first") == first_snapshot
    assert store.load_snapshot("sha256:later") is None
    assert store.load_snapshot("sha256:pointer") == version_pointer
    assert store.count_events() == 1
    with store._connect() as connection:
        row = connection.execute(
            "SELECT * FROM signal_evidence WHERE id = 'stable-event'"
        ).fetchone()
    assert row is not None
    assert row["input_snapshot_id"] == "sha256:first"
    assert row["engine_version"] == "1.0.0rc8"
    assert row["catalog_version"] == "czsc-v2-catalog-1"
    assert row["rule_version"] == "czsc-score-v2-rule-1"
    assert json.loads(row["payload_json"]) == first_event.model_dump(mode="json")


@pytest.mark.parametrize(
    "semantic_change",
    [
        {"occurred_at": "2024-01-01T14:50:00+08:00"},
        {"catalog_id": "buy2.overlap"},
        {"family": "second_buy"},
        {"role": "confirmation"},
        {"direction": "bearish"},
        {"period": "30m"},
        {"higher_period": "60m"},
        {"lower_period": "30m"},
        {"signal_name": "cxt_second_bs_V240524"},
        {"params": {"di": 2}},
        {"raw_key": "changed-key"},
        {"raw_value": "changed-value"},
        {"reason": "changed reason"},
        {"engine_version": "1.0.1"},
        {"catalog_version": "catalog-v2"},
        {"rule_version": "rule-v2"},
    ],
    ids=[
        "occurred-at",
        "catalog-id",
        "family",
        "role",
        "direction",
        "period",
        "higher-period",
        "lower-period",
        "signal-name",
        "params",
        "raw-key",
        "raw-value",
        "reason",
        "engine-version",
        "catalog-version",
        "rule-version",
    ],
)
def test_duplicate_event_id_rejects_semantic_collisions_atomically(
    tmp_path: Path,
    semantic_change: dict[str, object],
) -> None:
    store = ChanlunResearchStore(tmp_path / "research.sqlite3")
    first_event = _evidence(
        "sha256:first",
        event_id="stable-event",
        occurred_at="2024-01-01T14:55:00+08:00",
    )
    store.save_snapshot(
        _snapshot(
            "sha256:first",
            calculated_at="2024-01-01T15:00:00+08:00",
            events=[first_event],
        )
    )
    collision_payload = first_event.model_dump(mode="json")
    collision_payload.update(semantic_change)
    collision_payload["input_snapshot_id"] = "sha256:later"
    collision_payload["last_closed_bar_at"] = "2024-01-01T15:00:00+08:00"
    collision = CzscSignalEvidence.model_validate(collision_payload)
    later_snapshot = _snapshot(
        "sha256:later",
        symbol="600000.SH",
        calculated_at="2024-01-02T15:00:00+08:00",
        engine_version=collision.engine_version,
        catalog_version=collision.catalog_version,
        rule_version=collision.rule_version,
        events=[collision],
    )

    with pytest.raises(ValueError, match="event ID collision"):
        store.save_snapshot(later_snapshot)

    assert store.load_snapshot("sha256:later") is None
    assert store.count_events() == 1
    with store._connect() as connection:
        payload_json = connection.execute(
            "SELECT payload_json FROM signal_evidence WHERE id = 'stable-event'"
        ).fetchone()[0]
    assert json.loads(payload_json) == first_event.model_dump(mode="json")


def test_duplicate_event_id_rejects_malformed_existing_evidence_atomically(
    tmp_path: Path,
) -> None:
    store = ChanlunResearchStore(tmp_path / "research.sqlite3")
    first_event = _evidence("sha256:first", event_id="stable-event")
    store.save_snapshot(_snapshot("sha256:first", events=[first_event]))
    with store._connect() as connection:
        connection.execute(
            "UPDATE signal_evidence SET payload_json = '{bad' WHERE id = 'stable-event'"
        )
    later_event = _evidence(
        "sha256:later",
        event_id="stable-event",
        last_closed_bar_at="2026-07-10T15:00:00+08:00",
    )

    with pytest.raises(ValueError, match="stored evidence"):
        store.save_snapshot(
            _snapshot(
                "sha256:later",
                symbol="600000.SH",
                events=[later_event],
            )
        )

    assert store.load_snapshot("sha256:later") is None
    assert store.count_events() == 1


def test_duplicate_event_id_rejects_corrupt_existing_provenance_atomically(
    tmp_path: Path,
) -> None:
    store = ChanlunResearchStore(tmp_path / "research.sqlite3")
    first_event = _evidence("sha256:first", event_id="stable-event")
    store.save_snapshot(_snapshot("sha256:first", events=[first_event]))
    with store._connect() as connection:
        connection.execute(
            "UPDATE signal_evidence SET input_snapshot_id = 'sha256:tampered' "
            "WHERE id = 'stable-event'"
        )
    later_event = _evidence(
        "sha256:later",
        event_id="stable-event",
        last_closed_bar_at="2026-07-10T15:00:00+08:00",
    )

    with pytest.raises(ValueError, match="stored evidence"):
        store.save_snapshot(
            _snapshot(
                "sha256:later",
                symbol="600000.SH",
                events=[later_event],
            )
        )

    assert store.load_snapshot("sha256:later") is None
    assert store.count_events() == 1


def test_store_never_returns_snapshot_for_a_different_input_hash(tmp_path: Path) -> None:
    store = ChanlunResearchStore(tmp_path / "research.sqlite3")
    store.save_snapshot(_snapshot("sha256:a"))

    assert store.load_snapshot("sha256:b") is None


def test_latest_snapshot_uses_time_then_hash_without_mixing_versions(tmp_path: Path) -> None:
    store = ChanlunResearchStore(tmp_path / "research.sqlite3")
    store.save_snapshot(
        _snapshot(
            "sha256:a",
            calculated_at="2026-07-10T07:00:00+00:00",
            events=[_evidence("sha256:a", event_id="event-a")],
        )
    )
    expected = _snapshot(
        "sha256:z",
        calculated_at="2026-07-10T15:00:00+08:00",
        engine_version="1.0.1",
        catalog_version="catalog-v2",
        rule_version="rule-v2",
        events=[
            _evidence(
                "sha256:z",
                event_id="event-z",
                engine_version="1.0.1",
                catalog_version="catalog-v2",
                rule_version="rule-v2",
            )
        ],
    )
    store.save_snapshot(expected)
    store.save_snapshot(
        _snapshot(
            "sha256:other",
            symbol="600000.SH",
            calculated_at="2026-07-11T15:00:00+08:00",
            events=[_evidence("sha256:other", event_id="event-other")],
        )
    )

    assert store.latest_snapshot("300308.SZ") == expected


def test_latest_snapshot_breaks_equal_time_ties_by_input_hash(tmp_path: Path) -> None:
    store = ChanlunResearchStore(tmp_path / "research.sqlite3")
    lower = _snapshot(
        "sha256:a",
        events=[_evidence("sha256:a", event_id="event-a")],
    )
    higher = _snapshot(
        "sha256:b",
        events=[_evidence("sha256:b", event_id="event-b")],
    )
    store.save_snapshot(higher)
    store.save_snapshot(lower)

    assert store.latest_snapshot("300308.SZ") == higher
    assert store.latest_snapshot("000001.SZ") is None


@pytest.mark.parametrize(
    "corruption",
    ["malformed-json", "pydantic-invalid", "index-payload-mismatch"],
)
def test_latest_snapshot_skips_corrupt_newer_rows(
    tmp_path: Path,
    corruption: str,
) -> None:
    store = ChanlunResearchStore(tmp_path / "research.sqlite3")
    fallback = _snapshot(
        "sha256:fallback",
        calculated_at="2026-07-10T14:59:00+08:00",
        events=[_evidence("sha256:fallback", event_id="event-fallback")],
    )
    newer = _snapshot(
        "sha256:newer",
        calculated_at="2026-07-10T15:00:00+08:00",
        events=[_evidence("sha256:newer", event_id="event-newer")],
    )
    store.save_snapshot(fallback)
    store.save_snapshot(newer)
    if corruption == "malformed-json":
        corrupt_json = "{bad"
    elif corruption == "pydantic-invalid":
        corrupt_json = "{}"
    else:
        corrupt_json = json.dumps(
            fallback.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    with store._connect() as connection:
        connection.execute(
            "UPDATE research_snapshots SET payload_json = ? WHERE input_snapshot_id = ?",
            (corrupt_json, newer.input_snapshot_id),
        )

    assert store.latest_snapshot("300308.SZ") == fallback


def test_store_uses_wal_busy_timeout_row_factory_and_canonical_json(tmp_path: Path) -> None:
    path = tmp_path / "research.sqlite3"
    store = ChanlunResearchStore(path)
    snapshot = _snapshot("sha256:a")
    store.save_snapshot(snapshot)

    with store._connect() as connection:
        assert connection.row_factory is sqlite3.Row
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert connection.execute("PRAGMA busy_timeout").fetchone()[0] == 30_000
        payload_json = connection.execute(
            "SELECT payload_json FROM research_snapshots WHERE input_snapshot_id = ?",
            (snapshot.input_snapshot_id,),
        ).fetchone()[0]

    assert payload_json == json.dumps(
        snapshot.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    assert "三买" in payload_json
    assert "\\u4e09" not in payload_json


def test_snapshot_transaction_rolls_back_when_event_serialization_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = ChanlunResearchStore(tmp_path / "research.sqlite3")
    snapshot = _snapshot("sha256:a")
    original_dump_json = research_store_module._dump_json

    def fail_for_event(model):
        if isinstance(model, CzscSignalEvidence):
            raise TypeError("event serialization failed")
        return original_dump_json(model)

    monkeypatch.setattr(research_store_module, "_dump_json", fail_for_event)

    with pytest.raises(TypeError, match="event serialization failed"):
        store.save_snapshot(snapshot)

    assert store.load_snapshot(snapshot.input_snapshot_id) is None
    assert store.count_events() == 0


def test_snapshot_rejects_event_from_a_different_input_hash_atomically(tmp_path: Path) -> None:
    store = ChanlunResearchStore(tmp_path / "research.sqlite3")
    snapshot = _snapshot(
        "sha256:a",
        events=[_evidence("sha256:other", event_id="event-other")],
    )

    with pytest.raises(ValueError, match="input snapshot"):
        store.save_snapshot(snapshot)

    assert store.load_snapshot("sha256:a") is None
    assert store.count_events() == 0


def test_store_schema_contains_exactly_the_four_research_tables(tmp_path: Path) -> None:
    store = ChanlunResearchStore(tmp_path / "research.sqlite3")

    with store._connect() as connection:
        tables = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            )
        }

    assert tables == {
        "research_snapshots",
        "signal_evidence",
        "shadow_batches",
        "shadow_scores",
    }


@pytest.mark.parametrize(
    ("batch_id", "symbols", "message"),
    [
        ("", ["600000.SH"], "batch ID"),
        ("   ", ["600000.SH"], "batch ID"),
        ("batch-1", [], "at least one"),
        ("batch-1", ["600000.SH", "600000.SH"], "duplicate"),
        ("batch-1", ["600000.SH", ""], "symbol"),
    ],
)
def test_create_batch_rejects_empty_ids_and_invalid_baselines(
    tmp_path: Path,
    batch_id: str,
    symbols: list[str],
    message: str,
) -> None:
    store = ChanlunResearchStore(tmp_path / "research.sqlite3")

    with pytest.raises(ValueError, match=message):
        store.create_batch(batch_id, "2026-07-10", symbols)


def test_create_batch_is_idempotent_but_keeps_the_baseline_immutable(tmp_path: Path) -> None:
    store = ChanlunResearchStore(tmp_path / "research.sqlite3")
    symbols = ["600001.SH", "600000.SH"]

    store.create_batch("batch-1", "2026-07-10", symbols)
    store.create_batch("batch-1", "2026-07-10", symbols)

    result = store.load_batch("batch-1")
    assert result is not None
    assert result.batch_id == result.job_id == "batch-1"
    assert result.status == "pending"
    assert result.trade_date == "2026-07-10"
    assert result.pool_size == 2
    assert result.completed_count == 0
    assert result.items == []

    with pytest.raises(ValueError, match="immutable"):
        store.create_batch("batch-1", "2026-07-10", list(reversed(symbols)))


def test_save_batch_score_requires_batch_symbol_and_immutable_rank(tmp_path: Path) -> None:
    store = ChanlunResearchStore(tmp_path / "research.sqlite3")
    store.create_batch("batch-1", "2026-07-10", ["600000.SH"])

    with pytest.raises(ValueError, match="batch"):
        store.save_batch_score("missing", _candidate("600000.SH", 1))
    with pytest.raises(ValueError, match="baseline"):
        store.save_batch_score("batch-1", _candidate("600001.SH", 1))
    with pytest.raises(ValueError, match="baseline rank"):
        store.save_batch_score("batch-1", _candidate("600000.SH", 2))

    assert store.load_batch("missing") is None


def test_batch_score_upsert_is_idempotent_and_loads_in_baseline_order(tmp_path: Path) -> None:
    store = ChanlunResearchStore(tmp_path / "research.sqlite3")
    store.create_batch("batch-1", "2026-07-10", ["600001.SH", "600000.SH"])

    store.save_batch_score("batch-1", _candidate("600000.SH", 2, score=70, shadow_rank=2))
    store.save_batch_score("batch-1", _candidate("600001.SH", 1, score=90, shadow_rank=1))
    store.save_batch_score("batch-1", _candidate("600000.SH", 2, score=75, shadow_rank=2))

    result = store.load_batch("batch-1")
    assert result is not None
    assert result.completed_count == 2
    assert [item.symbol for item in result.items] == ["600001.SH", "600000.SH"]
    assert [item.baseline_rank for item in result.items] == [1, 2]
    assert [item.score for item in result.items] == [90, 75]


@pytest.mark.parametrize("terminal_status", ["ready", "partial", "unavailable"])
def test_terminal_batch_rejects_score_updates_and_preserves_result(
    tmp_path: Path,
    terminal_status: str,
) -> None:
    store = ChanlunResearchStore(tmp_path / "research.sqlite3")
    symbols = ["600000.SH", "600001.SH"] if terminal_status == "partial" else ["600000.SH"]
    store.create_batch("batch-1", "2026-07-10", symbols)
    initial = (
        _candidate("600000.SH", 1)
        if terminal_status != "unavailable"
        else _candidate("600000.SH", 1, status="unavailable", score=None)
    )
    store.save_batch_score("batch-1", initial)
    store.finish_batch("batch-1", terminal_status)
    before = store.load_batch("batch-1")

    replacement = (
        _candidate("600000.SH", 1, score=75)
        if terminal_status != "unavailable"
        else _candidate("600000.SH", 1, status="unavailable", score=None)
    )
    with pytest.raises(ValueError, match="pending"):
        store.save_batch_score("batch-1", replacement)

    assert store.load_batch("batch-1") == before


@pytest.mark.parametrize("terminal_status", ["partial", "unavailable"])
def test_terminal_batch_rejects_new_score_rows_and_preserves_result(
    tmp_path: Path,
    terminal_status: str,
) -> None:
    store = ChanlunResearchStore(tmp_path / "research.sqlite3")
    store.create_batch("batch-1", "2026-07-10", ["600000.SH", "600001.SH"])
    if terminal_status == "partial":
        store.save_batch_score("batch-1", _candidate("600000.SH", 1))
    store.finish_batch("batch-1", terminal_status)
    before = store.load_batch("batch-1")

    new_score = (
        _candidate("600001.SH", 2)
        if terminal_status == "partial"
        else _candidate("600001.SH", 2, status="unavailable", score=None)
    )
    with pytest.raises(ValueError, match="pending"):
        store.save_batch_score("batch-1", new_score)

    assert store.load_batch("batch-1") == before


def test_finish_batch_requires_complete_scoreable_rows_before_ready(tmp_path: Path) -> None:
    store = ChanlunResearchStore(tmp_path / "research.sqlite3")
    store.create_batch("batch-1", "2026-07-10", ["600000.SH", "600001.SH"])
    store.save_batch_score("batch-1", _candidate("600000.SH", 1))

    with pytest.raises(ValueError, match="every baseline symbol"):
        store.finish_batch("batch-1", "ready")

    store.save_batch_score(
        "batch-1",
        _candidate("600001.SH", 2, status="unavailable", score=None),
    )
    with pytest.raises(ValueError, match="every baseline symbol"):
        store.finish_batch("batch-1", "ready")

    store.save_batch_score("batch-1", _candidate("600001.SH", 2))
    store.finish_batch("batch-1", "ready")
    store.finish_batch("batch-1", "ready")

    result = store.load_batch("batch-1")
    assert result is not None
    assert result.status == "ready"
    assert result.completed_count == result.pool_size == 2


@pytest.mark.parametrize(
    ("terminal_status", "candidate_status", "candidate_score", "message"),
    [
        ("partial", None, None, "at least one processed"),
        ("partial", "unavailable", None, "ready score"),
        ("partial", "ready", 80, "complete all-ready"),
        ("unavailable", "ready", 80, "cannot contain a ready score"),
    ],
)
def test_finish_batch_rejects_invalid_terminal_status_content(
    tmp_path: Path,
    terminal_status: str,
    candidate_status: str | None,
    candidate_score: int | None,
    message: str,
) -> None:
    store = ChanlunResearchStore(tmp_path / "research.sqlite3")
    store.create_batch("batch-1", "2026-07-10", ["600000.SH"])
    if candidate_status is not None:
        store.save_batch_score(
            "batch-1",
            _candidate(
                "600000.SH",
                1,
                status=candidate_status,
                score=candidate_score,
            ),
        )

    with pytest.raises(ValueError, match=message):
        store.finish_batch("batch-1", terminal_status)

    result = store.load_batch("batch-1")
    assert result is not None and result.status == "pending"


def test_finish_batch_accepts_partial_complete_mixed_results(tmp_path: Path) -> None:
    store = ChanlunResearchStore(tmp_path / "research.sqlite3")
    store.create_batch("batch-1", "2026-07-10", ["600000.SH", "600001.SH"])
    store.save_batch_score("batch-1", _candidate("600000.SH", 1))
    store.save_batch_score(
        "batch-1",
        _candidate("600001.SH", 2, status="unavailable", score=None),
    )

    store.finish_batch("batch-1", "partial")

    result = store.load_batch("batch-1")
    assert result is not None and result.status == "partial"
    assert result.completed_count == result.pool_size == 2


def test_finish_batch_accepts_unavailable_with_only_non_score_results(tmp_path: Path) -> None:
    store = ChanlunResearchStore(tmp_path / "research.sqlite3")
    store.create_batch("batch-1", "2026-07-10", ["600000.SH", "600001.SH"])
    store.save_batch_score(
        "batch-1",
        _candidate("600000.SH", 1, status="unavailable", score=None),
    )
    store.save_batch_score(
        "batch-1",
        _candidate("600001.SH", 2, status="stale", score=None),
    )

    store.finish_batch("batch-1", "unavailable")

    result = store.load_batch("batch-1")
    assert result is not None and result.status == "unavailable"
    assert result.completed_count == 2


def test_finish_batch_preserves_partial_and_unavailable_terminal_states(tmp_path: Path) -> None:
    store = ChanlunResearchStore(tmp_path / "research.sqlite3")
    store.create_batch("partial", "2026-07-10", ["600000.SH", "600001.SH"])
    store.save_batch_score("partial", _candidate("600000.SH", 1))
    store.finish_batch("partial", "partial")
    store.finish_batch("partial", "partial")
    store.create_batch("unavailable", "2026-07-10", ["600002.SH"])
    store.finish_batch("unavailable", "unavailable")
    store.finish_batch("unavailable", "unavailable")

    partial = store.load_batch("partial")
    unavailable = store.load_batch("unavailable")
    assert partial is not None and partial.status == "partial"
    assert partial.completed_count == 1
    assert unavailable is not None and unavailable.status == "unavailable"
    assert unavailable.completed_count == 0

    with pytest.raises(ValueError, match="transition"):
        store.finish_batch("partial", "unavailable")
    with pytest.raises(ValueError, match="terminal"):
        store.finish_batch("unavailable", "pending")
    with pytest.raises(ValueError, match="batch"):
        store.finish_batch("missing", "partial")


def test_load_batch_does_not_fabricate_validity_for_corrupt_ready_state(tmp_path: Path) -> None:
    store = ChanlunResearchStore(tmp_path / "research.sqlite3")
    store.create_batch("batch-1", "2026-07-10", ["600000.SH"])
    with store._connect() as connection:
        connection.execute("UPDATE shadow_batches SET status = 'ready' WHERE batch_id = 'batch-1'")

    with pytest.raises(ValueError, match="ready batch"):
        store.load_batch("batch-1")


def test_load_batch_rejects_ready_state_with_non_ready_candidate(tmp_path: Path) -> None:
    store = ChanlunResearchStore(tmp_path / "research.sqlite3")
    store.create_batch("batch-1", "2026-07-10", ["600000.SH"])
    store.save_batch_score(
        "batch-1",
        _candidate("600000.SH", 1, status="unavailable", score=None),
    )
    with store._connect() as connection:
        connection.execute("UPDATE shadow_batches SET status = 'ready' WHERE batch_id = 'batch-1'")

    with pytest.raises(ValueError, match="ready batch"):
        store.load_batch("batch-1")


@pytest.mark.parametrize(
    ("stored_status", "candidate_status", "candidate_score", "message"),
    [
        ("partial", None, None, "at least one processed"),
        ("partial", "unavailable", None, "ready score"),
        ("partial", "ready", 80, "complete all-ready"),
        ("unavailable", "ready", 80, "cannot contain a ready score"),
    ],
)
def test_load_batch_rejects_invalid_persisted_terminal_status_content(
    tmp_path: Path,
    stored_status: str,
    candidate_status: str | None,
    candidate_score: int | None,
    message: str,
) -> None:
    store = ChanlunResearchStore(tmp_path / "research.sqlite3")
    store.create_batch("batch-1", "2026-07-10", ["600000.SH"])
    if candidate_status is not None:
        store.save_batch_score(
            "batch-1",
            _candidate(
                "600000.SH",
                1,
                status=candidate_status,
                score=candidate_score,
            ),
        )
    with store._connect() as connection:
        connection.execute(
            "UPDATE shadow_batches SET status = ? WHERE batch_id = 'batch-1'",
            (stored_status,),
        )

    with pytest.raises(ValueError, match=message):
        store.load_batch("batch-1")


@pytest.mark.parametrize(
    ("snapshot_days", "evidence_days"),
    [(0, 1), (-1, 1), (1, 0), (1, -1)],
)
def test_prune_requires_positive_retention_windows(
    tmp_path: Path,
    snapshot_days: int,
    evidence_days: int,
) -> None:
    store = ChanlunResearchStore(tmp_path / "research.sqlite3")

    with pytest.raises(ValueError, match="positive"):
        store.prune(
            now=datetime(2026, 7, 13, tzinfo=SHANGHAI),
            snapshot_days=snapshot_days,
            evidence_days=evidence_days,
        )


def test_prune_requires_timezone_aware_now(tmp_path: Path) -> None:
    store = ChanlunResearchStore(tmp_path / "research.sqlite3")

    with pytest.raises(ValueError, match="timezone-aware"):
        store.prune(
            now=datetime(2026, 7, 13),
            snapshot_days=180,
            evidence_days=730,
        )


def test_prune_removes_old_snapshots_but_keeps_latest_for_each_version(
    tmp_path: Path,
) -> None:
    store = ChanlunResearchStore(tmp_path / "research.sqlite3")
    old = _snapshot(
        "sha256:old",
        calculated_at="2024-01-01T15:00:00+08:00",
        events=[
            _evidence(
                "sha256:old",
                event_id="event-old",
                occurred_at="2024-01-01T14:55:00+08:00",
            )
        ],
    )
    latest = _snapshot(
        "sha256:latest",
        calculated_at="2024-01-02T15:00:00+08:00",
        events=[
            _evidence(
                "sha256:latest",
                event_id="event-latest",
                occurred_at="2024-01-02T14:55:00+08:00",
            )
        ],
    )
    other_version = _snapshot(
        "sha256:other-version",
        calculated_at="2023-01-01T15:00:00+08:00",
        engine_version="1.0.1",
        events=[
            _evidence(
                "sha256:other-version",
                event_id="event-other-version",
                occurred_at="2023-01-01T14:55:00+08:00",
                engine_version="1.0.1",
            )
        ],
    )
    store.save_snapshot(old)
    store.save_snapshot(latest)
    store.save_snapshot(other_version)

    store.prune(
        now=datetime(2026, 7, 13, tzinfo=SHANGHAI),
        snapshot_days=180,
        evidence_days=180,
    )

    assert store.load_snapshot("sha256:old") is None
    assert store.load_snapshot("sha256:latest") == latest
    assert store.load_snapshot("sha256:other-version") == other_version
    with store._connect() as connection:
        evidence_ids = {row["id"] for row in connection.execute("SELECT id FROM signal_evidence")}
    assert evidence_ids == {"event-latest", "event-other-version"}


def test_prune_removes_expired_evidence_no_longer_referenced_by_snapshot(
    tmp_path: Path,
) -> None:
    store = ChanlunResearchStore(tmp_path / "research.sqlite3")
    event = _evidence(
        "sha256:old",
        event_id="event-orphaned",
        occurred_at="2024-01-01T14:55:00+08:00",
    )
    store.save_snapshot(
        _snapshot(
            "sha256:old",
            calculated_at="2024-01-01T15:00:00+08:00",
            events=[event],
        )
    )
    store.save_snapshot(
        _snapshot(
            "sha256:pointer",
            calculated_at="2024-01-02T15:00:00+08:00",
            events=[],
        )
    )

    store.prune(
        now=datetime(2026, 7, 13, tzinfo=SHANGHAI),
        snapshot_days=180,
        evidence_days=180,
    )

    assert store.load_snapshot("sha256:old") is None
    assert store.load_snapshot("sha256:pointer") is not None
    assert store.count_events() == 0


@pytest.mark.parametrize(
    "corruption",
    ["malformed-json", "pydantic-invalid", "index-payload-mismatch"],
)
def test_prune_deletes_corrupt_newer_row_and_keeps_latest_valid_pointer(
    tmp_path: Path,
    corruption: str,
) -> None:
    store = ChanlunResearchStore(tmp_path / "research.sqlite3")
    fallback_event = _evidence(
        "sha256:fallback",
        event_id="event-fallback",
        occurred_at="2024-01-01T14:55:00+08:00",
    )
    fallback = _snapshot(
        "sha256:fallback",
        calculated_at="2024-01-01T15:00:00+08:00",
        events=[fallback_event],
    )
    corrupt_event = _evidence(
        "sha256:corrupt",
        event_id="event-corrupt",
        occurred_at="2024-01-02T14:55:00+08:00",
    )
    corrupt = _snapshot(
        "sha256:corrupt",
        calculated_at="2026-07-12T15:00:00+08:00",
        events=[corrupt_event],
    )
    store.save_snapshot(fallback)
    store.save_snapshot(corrupt)
    if corruption == "malformed-json":
        corrupt_json = "{bad"
    elif corruption == "pydantic-invalid":
        corrupt_json = "{}"
    else:
        corrupt_json = json.dumps(
            fallback.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    with store._connect() as connection:
        connection.execute(
            "UPDATE research_snapshots SET payload_json = ? WHERE input_snapshot_id = ?",
            (corrupt_json, corrupt.input_snapshot_id),
        )

    store.prune(
        now=datetime(2026, 7, 13, tzinfo=SHANGHAI),
        snapshot_days=180,
        evidence_days=180,
    )

    assert store.load_snapshot("sha256:fallback") == fallback
    with store._connect() as connection:
        snapshot_ids = {
            row["input_snapshot_id"]
            for row in connection.execute("SELECT input_snapshot_id FROM research_snapshots")
        }
        evidence_ids = {row["id"] for row in connection.execute("SELECT id FROM signal_evidence")}
    assert snapshot_ids == {"sha256:fallback"}
    assert evidence_ids == {"event-fallback"}


def test_prune_preserves_expired_evidence_referenced_by_recent_valid_snapshot_without_json1(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = ChanlunResearchStore(tmp_path / "research.sqlite3")
    referenced_event = _evidence(
        "sha256:recent",
        event_id="event-referenced",
        occurred_at="2024-01-01T14:55:00+08:00",
    )
    recent = _snapshot(
        "sha256:recent",
        calculated_at="2026-07-01T15:00:00+08:00",
        events=[referenced_event],
    )
    pointer = _snapshot(
        "sha256:pointer",
        calculated_at="2026-07-02T15:00:00+08:00",
        events=[],
    )
    store.save_snapshot(recent)
    store.save_snapshot(pointer)
    statements: list[str] = []
    original_connect = sqlite3.connect

    def traced_connect(*args, **kwargs):
        connection = original_connect(*args, **kwargs)
        connection.set_trace_callback(statements.append)
        return connection

    monkeypatch.setattr(sqlite3, "connect", traced_connect)

    store.prune(
        now=datetime(2026, 7, 13, tzinfo=SHANGHAI),
        snapshot_days=30,
        evidence_days=1,
    )

    assert store.load_snapshot("sha256:recent") == recent
    assert store.load_snapshot("sha256:pointer") == pointer
    assert store.count_events() == 1
    assert all("json_each" not in statement.lower() for statement in statements)
    assert all("json_extract" not in statement.lower() for statement in statements)


def test_prune_uses_shanghai_cutoff_and_cascades_old_shadow_scores(tmp_path: Path) -> None:
    store = ChanlunResearchStore(tmp_path / "research.sqlite3")
    store.create_batch("expired", "2026-07-11", ["600000.SH"])
    store.save_batch_score("expired", _candidate("600000.SH", 1))
    store.finish_batch("expired", "ready")
    store.create_batch("retained", "2026-07-12", ["600001.SH"])
    store.save_batch_score("retained", _candidate("600001.SH", 1))

    store.prune(
        now=datetime(2026, 7, 12, 16, tzinfo=timezone.utc),
        snapshot_days=1,
        evidence_days=1,
    )

    assert store.load_batch("expired") is None
    assert store.load_batch("retained") is not None
    with store._connect() as connection:
        score_batches = {
            row["batch_id"] for row in connection.execute("SELECT batch_id FROM shadow_scores")
        }
    assert score_batches == {"retained"}
