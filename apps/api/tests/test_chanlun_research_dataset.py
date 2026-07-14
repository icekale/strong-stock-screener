from __future__ import annotations

from datetime import date, timedelta

from app.services.chanlun.research_dataset import reconstruct_candidates


def test_candidate_reconstruction_uses_only_prior_20_sessions() -> None:
    rows: list[dict[str, object]] = []
    for index in range(20):
        trade_date = date(2026, 6, 15) + timedelta(days=index)
        rows.append(
            {
                "date": trade_date.strftime("%Y%m%d"),
                "code": "600000",
                "name": "测试股份",
                "prev_close": 10,
                "close": 11.0 if index >= 18 else 10.0,
                "float_mv": 5_000_000_000,
                "total_mv": 8_000_000_000,
                "industry": "计算机",
            }
        )
    rows.extend(
        [
            {
                "date": "20260710",
                "code": "600001",
                "name": "ST风险股份",
                "prev_close": 10,
                "close": 11,
            },
            {
                "date": "20260711",
                "code": "600002",
                "name": "未来股份",
                "prev_close": 10,
                "close": 11,
            },
        ]
    )

    candidates = reconstruct_candidates(rows, trade_date="2026-07-10")

    assert all(item.last_limit_up_date <= "2026-07-10" for item in candidates)
    assert all("ST" not in item.candidate.name.upper() for item in candidates)
    assert candidates[0].limit_up_hits_20d >= candidates[-1].limit_up_hits_20d
    assert [item.candidate.symbol for item in candidates] == ["600000.SH"]
