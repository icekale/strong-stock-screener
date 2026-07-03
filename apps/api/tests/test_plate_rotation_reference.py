from __future__ import annotations

from app.services.plate_rotation_reference import PlateRotationReferenceProvider, parse_plate_rotation_rows


def test_parse_plate_rotation_rows_extracts_kaipan_theme_scores() -> None:
    payload = {
        "html": """
        <span class='rank'>1</span>
        <td class='plate plate801159' code='801159' name='机器人' style=''>
          <span>机器人</span><br><span style='color:red;'>35630</span>
        </td>
        <span class='rank'>2</span>
        <td class='plate plate801314' code='801314' name='ST板块' style=''>
          <span>ST板块</span><br><span style='color:red;'>12964</span>
        </td>
        <span class='rank'>3</span>
        <td class='plate plate801843' code='801843' name='商业航天' style=''>
          <span>商业航天</span><br><span style='color:red;'>8046</span>
        </td>
        """
    }

    rows = parse_plate_rotation_rows(payload, source="kaipan")

    assert [(item.rank, item.code, item.name, item.score) for item in rows] == [
        (1, "801159", "机器人", 35630.0),
        (2, "801314", "ST板块", 12964.0),
        (3, "801843", "商业航天", 8046.0),
    ]
    assert rows[0].value_type == "score"


def test_plate_reference_provider_returns_valid_status_when_no_theme_rows() -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, str]:
            return {"html": ""}

    class FakeClient:
        def post(self, *args: object, **kwargs: object) -> FakeResponse:
            return FakeResponse()

    provider = PlateRotationReferenceProvider(http_client=FakeClient())

    result = provider.get_today_themes(limit=5)

    assert result.themes == []
    assert result.source_status[0].status == "stale"
