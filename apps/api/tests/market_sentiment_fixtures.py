from datetime import date, timedelta

from app.models import KlineBar


def make_test_bar(
    index: int,
    *,
    close: float | None = None,
    amount: float | None = None,
) -> KlineBar:
    price = close if close is not None else 100 + index * 0.05 + (index % 7 - 3) * 0.2
    return KlineBar(
        date=(date(2022, 1, 1) + timedelta(days=index)).isoformat(),
        open=price - 0.2,
        high=price + 1.0,
        low=price - 1.0,
        close=price,
        volume=1_000_000 + index,
        amount=amount if amount is not None else 100_000_000 + index * 100_000,
    )


def make_test_bars(count: int) -> list[KlineBar]:
    return [make_test_bar(index) for index in range(count)]
