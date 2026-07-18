from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from typing import TypedDict


OWNER = "simonlin1212"
REPOSITORY = "a-stock-data"
BRANCH = "main"
REQUIRED_FILES = ("SKILL.md", "CHANGELOG.md", "LICENSE")
MAX_FILE_BYTES = {"SKILL.md": 512_000, "CHANGELOG.md": 256_000, "LICENSE": 64_000}
NAME_RE = re.compile(r"(?m)^name:[ \t]*a-stock-data[ \t]*$")
VERSION_RE = re.compile(
    r"(?m)^version:[ \t]*([0-9]+\.[0-9]+\.[0-9]+)[ \t]*$"
)
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_APACHE_LICENSE_HEADER_RE = re.compile(
    r"\A[ \t]*Apache License[ \t]*\r?\n"
    r"[ \t]*Version 2\.0, January 2004[ \t]*(?:\r?\n|\Z)"
)
_FENCE_OPEN_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
_FENCE_CLOSE_RE = re.compile(r"^ {0,3}([`~]+)[ \t]*$")


class SyncError(RuntimeError):
    pass


class ArtifactValidationError(SyncError):
    pass


class UpstreamMetadata(TypedDict):
    owner: str
    repository: str
    branch: str
    commit: str
    version: str
    committed_at: str
    synced_at: str
    commit_url: str


class ArtifactMetadata(TypedDict):
    raw_url: str
    size: int
    sha256: str


class SyncMetadata(TypedDict):
    schema_version: int
    upstream: UpstreamMetadata
    artifacts: dict[str, ArtifactMetadata]


def validate_artifacts(artifacts: Mapping[str, bytes]) -> str:
    missing = [name for name in REQUIRED_FILES if name not in artifacts]
    if missing:
        raise ArtifactValidationError(f"missing required artifacts: {', '.join(missing)}")

    decoded: dict[str, str] = {}
    for name in REQUIRED_FILES:
        content = artifacts[name]
        if not content:
            raise ArtifactValidationError(f"{name} is empty")
        if len(content) > MAX_FILE_BYTES[name]:
            raise ArtifactValidationError(f"{name} exceeds its size limit")
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ArtifactValidationError(f"{name} is not valid UTF-8") from error
        leading_text = text.lstrip("\ufeff \t\r\n").lower()
        if leading_text.startswith(("<!doctype html", "<html")):
            raise ArtifactValidationError(f"{name} contains leading HTML")
        decoded[name] = text

    skill = decoded["SKILL.md"]
    lines = skill.splitlines()
    if not lines or lines[0] != "---":
        raise ArtifactValidationError("SKILL.md is missing a semantic frontmatter version")
    try:
        frontmatter_end = lines.index("---", 1)
    except ValueError as error:
        raise ArtifactValidationError(
            "SKILL.md is missing a semantic frontmatter version"
        ) from error
    frontmatter = "\n".join(lines[1:frontmatter_end])
    if NAME_RE.search(frontmatter) is None:
        raise ArtifactValidationError("SKILL.md is missing name: a-stock-data")
    version_match = VERSION_RE.search(frontmatter)
    if version_match is None:
        raise ArtifactValidationError("SKILL.md is missing a semantic frontmatter version")
    if not any(line.startswith("# A股全栈数据工具包") for line in lines):
        raise ArtifactValidationError("SKILL.md is missing the project heading")

    if not decoded["CHANGELOG.md"].startswith("# Changelog"):
        raise ArtifactValidationError("CHANGELOG.md must start with # Changelog")

    if _APACHE_LICENSE_HEADER_RE.match(decoded["LICENSE"]) is None:
        raise ArtifactValidationError("LICENSE must contain Apache License 2.0")

    return version_match.group(1)


def parse_markdown_sections(markdown: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    heading: str | None = None
    section_lines: list[str] = []
    fence_marker: str | None = None
    fence_length = 0

    for line in markdown.splitlines(keepends=True):
        line_text = line.rstrip("\r\n")
        if fence_marker is not None:
            if heading is not None:
                section_lines.append(line)
            closing_match = _FENCE_CLOSE_RE.fullmatch(line_text)
            if closing_match is not None:
                closing_run = closing_match.group(1)
                if (
                    len(closing_run) >= fence_length
                    and all(marker == fence_marker for marker in closing_run)
                ):
                    fence_marker = None
                    fence_length = 0
            continue

        opening_match = _FENCE_OPEN_RE.match(line_text)
        if opening_match is not None:
            if heading is not None:
                section_lines.append(line)
            opening_run = opening_match.group(1)
            fence_marker = opening_run[0]
            fence_length = len(opening_run)
            continue

        if line.startswith("## "):
            if heading is not None:
                sections[heading] = "".join(section_lines)
            heading = line[3:].strip()
            section_lines = [line]
        elif heading is not None:
            section_lines.append(line)

    if heading is not None:
        sections[heading] = "".join(section_lines)
    return sections


def compare_sections(
    previous: Mapping[str, str], current: Mapping[str, str]
) -> dict[str, list[str]]:
    previous_names = set(previous)
    current_names = set(current)
    return {
        "added": sorted(current_names - previous_names),
        "changed": sorted(
            name
            for name in previous_names & current_names
            if previous[name] != current[name]
        ),
        "removed": sorted(previous_names - current_names),
    }


def build_metadata(
    *,
    commit: str,
    committed_at: str,
    synced_at: str,
    version: str,
    artifacts: Mapping[str, bytes],
) -> SyncMetadata:
    if SHA_RE.fullmatch(commit) is None:
        raise ArtifactValidationError("commit SHA must be 40 lowercase hexadecimal characters")

    return {
        "schema_version": 1,
        "upstream": {
            "owner": OWNER,
            "repository": REPOSITORY,
            "branch": BRANCH,
            "commit": commit,
            "version": version,
            "committed_at": committed_at,
            "synced_at": synced_at,
            "commit_url": f"https://github.com/{OWNER}/{REPOSITORY}/commit/{commit}",
        },
        "artifacts": {
            name: {
                "raw_url": (
                    f"https://raw.githubusercontent.com/{OWNER}/{REPOSITORY}/"
                    f"{commit}/{name}"
                ),
                "size": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
            for name, content in sorted(artifacts.items())
        },
    }
