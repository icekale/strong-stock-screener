# CZSC Scoreable Window Design

## Goal

Make rc8 batch scoring and validation operate only on candidates with enough frozen minute history, while retaining the five-year daily dataset and baseline report.

## Data Boundary

The frozen manifest remains the source of truth. Minute partitions are grouped by symbol. A candidate is scoreable when its decision date is no earlier than 120 calendar days after that symbol's first minute bar and no later than its final minute bar. The warm-up covers the existing 240-bar 60-minute window conservatively.

## Scoring

The `score` command selects pending keys only from the scoreable set, newest date first. Existing cache records outside the scoreable set remain untouched but do not affect queue completion or coverage. Output distinguishes dataset candidates, scoreable candidates, completed attempts, and non-null scores.

## Validation

Cached-score validation filters candidates to the scoreable set before portfolio and fold calculations. Coverage is non-null cached scores divided by scoreable candidates. Partial coverage always adds the `score_cache_coverage` gate and forces `keep_shadow`. Reports expose the scoreable date range and all four counts.

## Safety And Testing

No network calls are added. Partition-derived boundaries are deterministic and dataset-bound. Tests cover per-symbol warm-up, missing minute history, queue filtering, validation metadata, and partial-promotion gating. Existing five-year baseline artifacts are not modified or deleted.
