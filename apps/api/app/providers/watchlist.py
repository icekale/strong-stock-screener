from __future__ import annotations

from pydantic import BaseModel, Field

from app.providers.thsdk_candidates import normalize_symbol


class WatchlistItem(BaseModel):
    symbol: str
    name: str | None = None
    industry: str | None = None
    group: str | None = None
    tags: list[str] = Field(default_factory=list)
    note: str | None = None


class WatchlistSnapshot(BaseModel):
    items: list[WatchlistItem]


def parse_watchlist_text(content: str) -> list[WatchlistItem]:
    items: list[WatchlistItem] = []
    seen: set[str] = set()
    current_group: str | None = None
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            current_group = line[1:-1].strip() or None
            continue
        parts = line.split()
        if len(parts) == 1 and "," in parts[0]:
            parts = parts[0].split(",")
        symbol = normalize_symbol(parts[0])
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        name, industry, group, tags, note = _parse_metadata(parts[1:], current_group)
        items.append(WatchlistItem(symbol=symbol, name=name, industry=industry, group=group, tags=tags, note=note))
    return items


def upsert_watchlist_item(content: str, item: WatchlistItem) -> str:
    normalized = item.model_copy(
        update={
            "symbol": normalize_symbol(item.symbol),
            "group": item.group.strip() if item.group else "自选",
            "tags": _dedupe(item.tags),
            "note": item.note.strip() if item.note else None,
        }
    )
    if not normalized.symbol:
        return format_watchlist_items(parse_watchlist_text(content))

    items = parse_watchlist_text(content)
    replaced = False
    output: list[WatchlistItem] = []
    for existing in items:
        if existing.symbol == normalized.symbol:
            output.append(normalized)
            replaced = True
        else:
            output.append(existing)
    if not replaced:
        output.append(normalized)
    return format_watchlist_items(output)


def format_watchlist_items(items: list[WatchlistItem]) -> str:
    grouped: dict[str, list[WatchlistItem]] = {}
    group_order: list[str] = []
    for item in items:
        group = item.group or "自选"
        if group not in grouped:
            grouped[group] = []
            group_order.append(group)
        grouped[group].append(item)

    lines: list[str] = []
    for group in group_order:
        if lines:
            lines.append("")
        lines.append(f"[{group}]")
        for item in sorted(grouped[group], key=lambda value: value.symbol):
            lines.append(_format_watchlist_line(item))
    return "\n".join(lines).strip()


def _parse_metadata(
    parts: list[str],
    current_group: str | None,
) -> tuple[str | None, str | None, str | None, list[str], str | None]:
    name: str | None = None
    industry: str | None = None
    group = current_group
    tags: list[str] = []
    note: str | None = None
    for part in parts:
        if part.startswith("#") and len(part) > 1:
            tags.append(part[1:])
        elif part.startswith("@") and len(part) > 1:
            group = part[1:]
        elif part.startswith("标签="):
            tags.extend(_split_tags(part.removeprefix("标签=")))
        elif part.startswith("tags="):
            tags.extend(_split_tags(part.removeprefix("tags=")))
        elif part.startswith("行业="):
            industry = part.removeprefix("行业=").strip() or None
        elif part.startswith("industry="):
            industry = part.removeprefix("industry=").strip() or None
        elif part.startswith("备注="):
            note = part.removeprefix("备注=").strip() or None
        elif part.startswith("note="):
            note = part.removeprefix("note=").strip() or None
        elif name is None:
            name = part
    return name, industry, group, _dedupe(tags), note


def _format_watchlist_line(item: WatchlistItem) -> str:
    parts = [item.symbol]
    if item.name:
        parts.append(item.name)
    parts.extend(f"#{tag}" for tag in item.tags)
    if item.industry:
        parts.append(f"行业={item.industry}")
    if item.note:
        parts.append(f"备注={item.note}")
    return " ".join(parts)


def _split_tags(value: str) -> list[str]:
    return [tag for chunk in value.split(",") for tag in chunk.split("，") if tag]


def _dedupe(values: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = value.strip()
        if text and text not in seen:
            seen.add(text)
            output.append(text)
    return output
