from __future__ import annotations

import argparse
import errno
import hashlib
import http.client
import json
import os
import re
import shutil
import stat
import sys
import tempfile
import urllib.error
import urllib.request
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol, TypedDict, cast


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
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SEMANTIC_VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
RFC3339_RE = re.compile(
    r"\A[0-9]{4}-[0-9]{2}-[0-9]{2}T"
    r"[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?"
    r"(?:Z|[+-][0-9]{2}:[0-9]{2})\Z"
)
REPOSITORY_IDENTITY = f"{OWNER}/{REPOSITORY}"
DEFAULT_DESTINATION = (
    Path(__file__).resolve().parents[1] / "third_party" / "a-stock-data"
)
JSON_MAX_BYTES = 1_000_000
GITHUB_ACCEPT = "application/vnd.github+json"
USER_AGENT = "StockMaster/a-stock-data-sync"
TRACKED_TERMS = (
    "腾讯",
    "Tencent",
    "mootdx",
    "通达信",
    "Eastmoney",
    "东财",
    "行业",
    "备用源",
    "降级",
)
_METADATA_FIELDS = {"schema_version", "upstream", "artifacts"}
_UPSTREAM_FIELDS = {
    "owner",
    "repository",
    "branch",
    "commit",
    "version",
    "committed_at",
    "synced_at",
    "commit_url",
}
_ARTIFACT_FIELDS = {"raw_url", "size", "sha256"}
_DIRECTORY_OPEN_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
_FILE_OPEN_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
_READ_CHUNK_BYTES = 64 * 1024
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


class _SnapshotMissingError(SyncError):
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


class UpstreamClient(Protocol):
    def repository_identity(self) -> str: ...

    def resolve_commit(self) -> tuple[str, str]: ...

    def download_file(self, commit: str, name: str, max_bytes: int) -> bytes: ...


@dataclass(frozen=True)
class SyncResult:
    changed: bool
    previous_commit: str | None
    current_commit: str
    previous_version: str | None
    current_version: str
    section_diff: dict[str, list[str]]
    summary: str


@dataclass(frozen=True)
class _ExistingSnapshot:
    commit: str
    version: str
    skill: str
    metadata: SyncMetadata


@dataclass
class _SnapshotTransactionState:
    backup: Path | None = None
    previous_backed_up: bool = False
    candidate_installed: bool = False
    preserve_candidate: bool = False


def _json_nesting_exceeds_limit(value: object, limit: int = 100) -> bool:
    pending = [(value, 1)]
    while pending:
        current, depth = pending.pop()
        if depth > limit:
            return True
        if isinstance(current, dict):
            pending.extend((item, depth + 1) for item in current.values())
        elif isinstance(current, list):
            pending.extend((item, depth + 1) for item in current)
    return False


class GitHubClient:
    def __init__(self, token: str | None = None, timeout: float = 20) -> None:
        self._token = token
        self._timeout = timeout

    def repository_identity(self) -> str:
        payload = self._read_json_object(
            f"https://api.github.com/repos/{REPOSITORY_IDENTITY}",
            "repository metadata",
        )
        full_name = payload.get("full_name")
        if not isinstance(full_name, str):
            raise ArtifactValidationError(
                "GitHub repository response is missing full_name"
            )
        return full_name

    def resolve_commit(self) -> tuple[str, str]:
        payload = self._read_json_object(
            f"https://api.github.com/repos/{REPOSITORY_IDENTITY}/commits/{BRANCH}",
            "main commit metadata",
        )
        sha = payload.get("sha")
        commit = payload.get("commit")
        if not isinstance(sha, str) or not isinstance(commit, Mapping):
            raise ArtifactValidationError("GitHub commit response has an invalid schema")
        committer = commit.get("committer")
        if not isinstance(committer, Mapping):
            raise ArtifactValidationError("GitHub commit response has an invalid schema")
        committed_at = committer.get("date")
        if not isinstance(committed_at, str):
            raise ArtifactValidationError("GitHub commit response has an invalid schema")
        return sha, committed_at

    def download_file(self, commit: str, name: str, max_bytes: int) -> bytes:
        url = (
            f"https://raw.githubusercontent.com/{REPOSITORY_IDENTITY}/"
            f"{commit}/{name}"
        )
        return self._read(url, max_bytes, name)

    def _read_json_object(self, url: str, description: str) -> dict[str, object]:
        content = self._read(url, JSON_MAX_BYTES, "JSON response")
        try:
            payload = json.loads(content)
        except (json.JSONDecodeError, RecursionError, UnicodeDecodeError) as error:
            raise ArtifactValidationError(
                f"GitHub {description} contains malformed JSON"
            ) from error
        if _json_nesting_exceeds_limit(payload):
            raise ArtifactValidationError(
                f"GitHub {description} contains malformed JSON"
            )
        if not isinstance(payload, dict):
            raise ArtifactValidationError(
                f"GitHub {description} must be a JSON object"
            )
        return payload

    def _read(self, url: str, max_bytes: int, description: str) -> bytes:
        headers = {"Accept": GITHUB_ACCEPT, "User-Agent": USER_AGENT}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                response_headers = getattr(response, "headers", None)
                content_length_header = (
                    response_headers.get("Content-Length")
                    if response_headers is not None
                    else None
                )
                content_length: int | None = None
                if content_length_header is not None:
                    try:
                        content_length = int(content_length_header)
                    except (TypeError, ValueError):
                        raise SyncError(
                            f"GitHub response from {url} has invalid Content-Length"
                        ) from None
                    if content_length < 0:
                        raise SyncError(
                            f"GitHub response from {url} has invalid Content-Length"
                        )
                    if content_length > max_bytes:
                        raise ArtifactValidationError(
                            f"{description} exceeds its size limit at {url}"
                        )
                content = response.read(max_bytes + 1)
        except (
            http.client.HTTPException,
            urllib.error.HTTPError,
            urllib.error.URLError,
            OSError,
        ):
            raise SyncError(
                f"GitHub request failed for {url} while reading {description}"
            ) from None
        if len(content) > max_bytes:
            raise ArtifactValidationError(f"{description} exceeds its size limit")
        if content_length is not None and len(content) < content_length:
            raise SyncError(f"GitHub response from {url} was truncated")
        if content_length is not None and len(content) > content_length:
            raise SyncError(f"GitHub response from {url} has invalid framing")
        return content


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


def _parse_rfc3339(
    value: object,
    description: str,
    error_type: type[SyncError],
) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise error_type(f"{description} must be nonempty")
    if RFC3339_RE.fullmatch(value) is None:
        raise error_type(f"{description} is invalid")
    iso_value = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(iso_value)
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise error_type(f"{description} must include a timezone")
    except (OverflowError, ValueError) as error:
        raise error_type(f"{description} is invalid") from error
    return parsed


def _parse_metadata(content: bytes) -> SyncMetadata:
    metadata_name = "metadata.json"
    try:
        payload = json.loads(content)
    except (json.JSONDecodeError, RecursionError, UnicodeDecodeError) as error:
        raise SyncError(f"{metadata_name} contains malformed JSON") from error

    if _json_nesting_exceeds_limit(payload):
        raise SyncError(f"{metadata_name} contains malformed JSON")
    if not isinstance(payload, dict) or set(payload) != _METADATA_FIELDS:
        raise SyncError(f"{metadata_name} has invalid top-level fields")
    if type(payload.get("schema_version")) is not int or payload["schema_version"] != 1:
        raise SyncError(f"{metadata_name} field schema_version must equal 1")

    upstream = payload.get("upstream")
    artifacts = payload.get("artifacts")
    if not isinstance(upstream, dict) or not isinstance(artifacts, dict):
        raise SyncError(f"{metadata_name} fields upstream and artifacts are invalid")
    if set(upstream) != _UPSTREAM_FIELDS:
        raise SyncError(f"{metadata_name} upstream fields are invalid")
    if set(artifacts) != set(REQUIRED_FILES):
        raise SyncError(
            f"{metadata_name} field artifacts must contain exactly: "
            f"{', '.join(REQUIRED_FILES)}"
        )

    for field in _UPSTREAM_FIELDS:
        if not isinstance(upstream.get(field), str):
            raise SyncError(f"{metadata_name} field upstream.{field} must be a string")
    if upstream["owner"] != OWNER:
        raise SyncError(f"{metadata_name} field upstream.owner is invalid")
    if upstream["repository"] != REPOSITORY:
        raise SyncError(f"{metadata_name} field upstream.repository is invalid")
    if upstream["branch"] != BRANCH:
        raise SyncError(f"{metadata_name} field upstream.branch is invalid")

    commit = upstream["commit"]
    version = upstream["version"]
    if SHA_RE.fullmatch(commit) is None:
        raise SyncError(f"{metadata_name} field upstream.commit is invalid")
    if SEMANTIC_VERSION_RE.fullmatch(version) is None:
        raise SyncError(f"{metadata_name} field upstream.version is invalid")
    _parse_rfc3339(
        upstream["committed_at"],
        f"{metadata_name} field upstream.committed_at",
        SyncError,
    )
    _parse_rfc3339(
        upstream["synced_at"],
        f"{metadata_name} field upstream.synced_at",
        SyncError,
    )
    expected_commit_url = f"https://github.com/{REPOSITORY_IDENTITY}/commit/{commit}"
    if upstream["commit_url"] != expected_commit_url:
        raise SyncError(f"{metadata_name} field upstream.commit_url is invalid")

    for name in REQUIRED_FILES:
        artifact = artifacts[name]
        if not isinstance(artifact, dict):
            raise SyncError(f"{metadata_name} artifact {name} must be an object")
        if set(artifact) != _ARTIFACT_FIELDS:
            raise SyncError(f"{metadata_name} artifact {name} fields are invalid")
        raw_url = artifact.get("raw_url")
        size = artifact.get("size")
        sha256 = artifact.get("sha256")
        if not isinstance(raw_url, str):
            raise SyncError(f"{metadata_name} artifact {name} raw_url is invalid")
        if type(size) is not int or size < 0:
            raise SyncError(f"{metadata_name} artifact {name} size is invalid")
        if not isinstance(sha256, str) or SHA256_RE.fullmatch(sha256) is None:
            raise SyncError(f"{metadata_name} artifact {name} sha256 is invalid")

    return cast(SyncMetadata, payload)


def _open_snapshot_directory(destination: Path) -> int:
    try:
        return os.open(destination, _DIRECTORY_OPEN_FLAGS)
    except FileNotFoundError:
        raise _SnapshotMissingError(
            f"snapshot destination does not exist: {destination}"
        ) from None
    except OSError as error:
        if error.errno in (errno.ELOOP, errno.ENOTDIR):
            raise ArtifactValidationError(
                f"snapshot destination is not a non-symlink directory: {destination}"
            ) from None
        raise SyncError(f"could not open snapshot destination: {destination}") from None


def _read_bounded_entry(
    directory_fd: int,
    name: str,
    max_bytes: int,
) -> bytes:
    try:
        entry_fd = os.open(name, _FILE_OPEN_FLAGS, dir_fd=directory_fd)
    except OSError as error:
        if error.errno == errno.ELOOP:
            raise ArtifactValidationError(f"snapshot entry {name} is a symlink") from None
        if error.errno in (errno.ENOENT, errno.ENOTDIR, getattr(errno, "ESTALE", -1)):
            raise ArtifactValidationError(
                f"snapshot entry {name} changed while being verified"
            ) from None
        raise ArtifactValidationError(f"could not open snapshot entry {name}") from None

    try:
        try:
            entry_stat = os.fstat(entry_fd)
        except OSError:
            raise ArtifactValidationError(f"could not inspect snapshot entry {name}") from None
        if not stat.S_ISREG(entry_stat.st_mode):
            raise ArtifactValidationError(f"snapshot entry {name} is not a regular file")

        chunks: list[bytes] = []
        total = 0
        while True:
            read_size = min(_READ_CHUNK_BYTES, max_bytes - total + 1)
            try:
                chunk = os.read(entry_fd, read_size)
            except OSError:
                raise ArtifactValidationError(
                    f"could not read snapshot entry {name}"
                ) from None
            if not chunk:
                return b"".join(chunks)
            chunks.append(chunk)
            total += len(chunk)
            if total > max_bytes:
                raise ArtifactValidationError(f"{name} exceeds its size limit")
    finally:
        os.close(entry_fd)


def _read_verified_snapshot(
    destination: Path,
) -> tuple[SyncMetadata, dict[str, bytes]]:
    directory_fd = _open_snapshot_directory(destination)
    try:
        try:
            entry_names = os.listdir(directory_fd)
        except OSError:
            raise ArtifactValidationError(
                f"could not enumerate snapshot destination: {destination}"
            ) from None

        expected_names = {"metadata.json", *REQUIRED_FILES}
        unexpected_names = sorted(set(entry_names) - expected_names)
        if unexpected_names:
            raise ArtifactValidationError(
                f"unexpected snapshot entries: {', '.join(unexpected_names)}"
            )
        missing_names = sorted(expected_names - set(entry_names))
        if missing_names:
            raise ArtifactValidationError(
                f"missing snapshot entries: {', '.join(missing_names)}"
            )

        metadata_bytes = _read_bounded_entry(
            directory_fd,
            "metadata.json",
            JSON_MAX_BYTES,
        )
        artifacts = {
            name: _read_bounded_entry(directory_fd, name, MAX_FILE_BYTES[name])
            for name in REQUIRED_FILES
        }
    finally:
        os.close(directory_fd)

    metadata = _parse_metadata(metadata_bytes)
    version = validate_artifacts(artifacts)
    if version != metadata["upstream"]["version"]:
        raise ArtifactValidationError(
            "metadata version does not match SKILL.md frontmatter version"
        )

    commit = metadata["upstream"]["commit"]
    for name in REQUIRED_FILES:
        content = artifacts[name]
        artifact_metadata = metadata["artifacts"][name]
        expected_raw_url = (
            f"https://raw.githubusercontent.com/{REPOSITORY_IDENTITY}/"
            f"{commit}/{name}"
        )
        if artifact_metadata["raw_url"] != expected_raw_url:
            raise ArtifactValidationError(f"{name} raw_url is not pinned to {commit}")
        if artifact_metadata["size"] != len(content):
            raise ArtifactValidationError(f"{name} size does not match local bytes")
        if artifact_metadata["sha256"] != hashlib.sha256(content).hexdigest():
            raise ArtifactValidationError(f"{name} SHA256 does not match local bytes")

    return metadata, artifacts


def _load_existing_snapshot(destination: Path) -> _ExistingSnapshot | None:
    try:
        metadata, artifacts = _read_verified_snapshot(destination)
    except _SnapshotMissingError:
        return None
    return _ExistingSnapshot(
        commit=metadata["upstream"]["commit"],
        version=metadata["upstream"]["version"],
        skill=artifacts["SKILL.md"].decode("utf-8"),
        metadata=metadata,
    )


def verify_snapshot(destination: Path) -> SyncMetadata:
    metadata, _artifacts = _read_verified_snapshot(destination)
    return metadata


def _normalize_committed_at(value: object) -> str:
    committed_at = _parse_rfc3339(
        value,
        "resolved commit timestamp",
        ArtifactValidationError,
    )
    try:
        normalized = committed_at.astimezone(timezone.utc).isoformat()
    except (OverflowError, ValueError) as error:
        raise ArtifactValidationError("resolved commit timestamp is invalid") from error
    return normalized.replace("+00:00", "Z")


def _format_synced_at(now: Callable[[], datetime]) -> str:
    current = now()
    if current.tzinfo is None or current.utcoffset() is None:
        raise SyncError("sync clock must return a timezone-aware datetime")
    return current.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _markdown_code_span(value: str) -> str:
    longest_run = max((len(run) for run in re.findall(r"`+", value)), default=0)
    delimiter = "`" * (longest_run + 1)
    return f"{delimiter} {value} {delimiter}"


def _format_section_list(names: list[str]) -> str:
    if not names:
        return "None"
    return ", ".join(_markdown_code_span(name) for name in sorted(names))


def _tracked_section_terms(
    section_diff: Mapping[str, list[str]],
    previous_sections: Mapping[str, str],
    current_sections: Mapping[str, str],
) -> list[tuple[str, list[str]]]:
    affected_sections = sorted(
        {
            name
            for change_type in ("added", "changed", "removed")
            for name in section_diff[change_type]
        }
    )
    matches: list[tuple[str, list[str]]] = []
    for name in affected_sections:
        content = previous_sections.get(name, "") + current_sections.get(name, "")
        terms = [term for term in TRACKED_TERMS if term in content]
        if terms:
            matches.append((name, terms))
    return matches


def _build_summary(
    *,
    previous_commit: str | None,
    current_commit: str,
    previous_version: str | None,
    current_version: str,
    section_diff: dict[str, list[str]],
    metadata: SyncMetadata,
    previous_sections: Mapping[str, str],
    current_sections: Mapping[str, str],
) -> str:
    first_sync = previous_commit is None
    previous_commit_text = (
        "none (first sync)" if first_sync else f"`{previous_commit}`"
    )
    previous_version_text = (
        "none (first sync)" if previous_version is None else f"`{previous_version}`"
    )
    commit_url = metadata["upstream"]["commit_url"]
    lines = [
        "# Upstream a-stock-data",
        "",
        f"- Upstream: `{REPOSITORY_IDENTITY}`",
        f"- Previous commit: {previous_commit_text}",
        f"- Current commit: `{current_commit}`",
        f"- Commit URL: {commit_url}",
        f"- Previous version: {previous_version_text}",
        f"- Current version: `{current_version}`",
    ]
    if previous_commit is not None:
        lines.append(
            "- Compare URL: "
            f"https://github.com/{REPOSITORY_IDENTITY}/compare/"
            f"{previous_commit}...{current_commit}"
        )

    lines.extend(
        (
            "",
            "## Sections",
            "",
            f"- Added: {_format_section_list(section_diff['added'])}",
            f"- Changed: {_format_section_list(section_diff['changed'])}",
            f"- Removed: {_format_section_list(section_diff['removed'])}",
        )
    )
    tracked_matches = _tracked_section_terms(
        section_diff,
        previous_sections,
        current_sections,
    )
    if tracked_matches:
        match_text = "; ".join(
            f"{_markdown_code_span(name)} "
            f"({', '.join(f'`{term}`' for term in terms)})"
            for name, terms in tracked_matches
        )
        lines.extend(
            (
                "",
                "> [!WARNING]",
                "> Tracked provider or source terms occur in affected sections: "
                f"{match_text}.",
            )
        )

    lines.extend(("", "## Artifacts", "", "| File | Size (bytes) | SHA256 |"))
    lines.append("| --- | ---: | --- |")
    for name, artifact in sorted(metadata["artifacts"].items()):
        lines.append(
            f"| `{name}` | {artifact['size']} | `{artifact['sha256']}` |"
        )
    lines.extend(
        (
            "",
            "## Safety",
            "",
            "Upstream Markdown is not executed. Application runtime providers are unchanged "
            "by this sync.",
        )
    )
    return "\n".join(lines) + "\n"


def _replace_path(source: Path, destination: Path) -> None:
    source.replace(destination)


def _remove_directory(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)


def _write_snapshot(
    destination: Path,
    artifacts: Mapping[str, bytes],
    metadata: SyncMetadata,
) -> None:
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        candidate = Path(
            tempfile.mkdtemp(
                prefix=f".{destination.name}.tmp-",
                dir=destination.parent,
            )
        )
    except OSError as error:
        raise SyncError("failed to prepare snapshot transaction") from error

    state = _SnapshotTransactionState()
    try:
        try:
            for name in REQUIRED_FILES:
                (candidate / name).write_bytes(artifacts[name])
            metadata_bytes = (
                json.dumps(metadata, sort_keys=True, indent=2) + "\n"
            ).encode()
            (candidate / "metadata.json").write_bytes(metadata_bytes)
        except (KeyError, OSError) as error:
            raise SyncError("failed to prepare snapshot transaction") from error

        if destination.exists():
            state.backup = destination.parent / (
                f".{destination.name}.backup-{uuid.uuid4().hex}"
            )
            try:
                _replace_path(destination, state.backup)
            except OSError as error:
                raise SyncError("failed to move previous snapshot to backup") from error
            state.previous_backed_up = True

        try:
            _replace_path(candidate, destination)
        except OSError as error:
            if state.previous_backed_up and state.backup is not None:
                restore_error: OSError | None = None
                for _attempt in range(2):
                    try:
                        _replace_path(state.backup, destination)
                    except OSError as current_restore_error:
                        restore_error = current_restore_error
                        if destination.exists():
                            break
                    else:
                        state.previous_backed_up = False
                        break
                if state.previous_backed_up:
                    state.preserve_candidate = True
                    raise SyncError(
                        "failed to replace snapshot and restore previous snapshot; "
                        "recovery artifacts preserved"
                    ) from restore_error
            raise SyncError("failed to replace snapshot") from error
        state.candidate_installed = True

        if state.candidate_installed and state.backup is not None:
            try:
                _remove_directory(state.backup)
            except OSError:
                pass
            else:
                state.backup = None
                state.previous_backed_up = False
    finally:
        if candidate.exists() and not state.preserve_candidate:
            try:
                _remove_directory(candidate)
            except OSError:
                pass


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def sync_snapshot(
    client: UpstreamClient,
    destination: Path,
    now: Callable[[], datetime] = _utc_now,
) -> SyncResult:
    identity = client.repository_identity()
    if identity != REPOSITORY_IDENTITY:
        raise SyncError(f"unexpected upstream repository: {identity!r}")

    existing = _load_existing_snapshot(destination)
    commit, committed_at = client.resolve_commit()
    if not isinstance(commit, str) or SHA_RE.fullmatch(commit) is None:
        raise ArtifactValidationError(
            "resolved commit SHA must be 40 lowercase hexadecimal characters"
        )
    normalized_committed_at = _normalize_committed_at(committed_at)

    previous_commit = existing.commit if existing is not None else None
    previous_version = existing.version if existing is not None else None
    if existing is not None and previous_commit == commit:
        section_diff = {"added": [], "changed": [], "removed": []}
        current_sections = parse_markdown_sections(existing.skill)
        summary = _build_summary(
            previous_commit=previous_commit,
            current_commit=commit,
            previous_version=previous_version,
            current_version=existing.version,
            section_diff=section_diff,
            metadata=existing.metadata,
            previous_sections=current_sections,
            current_sections=current_sections,
        )
        return SyncResult(
            changed=False,
            previous_commit=previous_commit,
            current_commit=commit,
            previous_version=previous_version,
            current_version=existing.version,
            section_diff=section_diff,
            summary=summary,
        )

    artifacts: dict[str, bytes] = {}
    for name in REQUIRED_FILES:
        content = client.download_file(commit, name, MAX_FILE_BYTES[name])
        if not isinstance(content, bytes):
            raise ArtifactValidationError(f"{name} download did not return bytes")
        artifacts[name] = content

    current_version = validate_artifacts(artifacts)
    previous_sections = (
        parse_markdown_sections(existing.skill) if existing is not None else {}
    )
    current_sections = parse_markdown_sections(artifacts["SKILL.md"].decode("utf-8"))
    section_diff = compare_sections(previous_sections, current_sections)
    metadata = build_metadata(
        commit=commit,
        committed_at=normalized_committed_at,
        synced_at=_format_synced_at(now),
        version=current_version,
        artifacts=artifacts,
    )
    summary = _build_summary(
        previous_commit=previous_commit,
        current_commit=commit,
        previous_version=previous_version,
        current_version=current_version,
        section_diff=section_diff,
        metadata=metadata,
        previous_sections=previous_sections,
        current_sections=current_sections,
    )
    _write_snapshot(destination, artifacts, metadata)
    return SyncResult(
        changed=True,
        previous_commit=previous_commit,
        current_commit=commit,
        previous_version=previous_version,
        current_version=current_version,
        section_diff=section_diff,
        summary=summary,
    )


def _write_summary(path: Path, summary: str) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(summary, encoding="utf-8", newline="\n")
    except OSError as error:
        raise SyncError(f"failed to write summary: {path}") from error


def main(
    argv: list[str] | None = None,
    client_factory: Callable[[str | None], UpstreamClient] = GitHubClient,
) -> int:
    parser = argparse.ArgumentParser(
        description="Synchronize the a-stock-data snapshot",
        allow_abbrev=False,
    )
    parser.add_argument("--destination", type=Path, default=DEFAULT_DESTINATION)
    parser.add_argument("--summary-path", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    token: str | None = None
    try:
        if args.check:
            metadata = verify_snapshot(args.destination)
            upstream = metadata["upstream"]
            print(
                f"verified a-stock-data {upstream['version']} at "
                f"{upstream['commit']}"
            )
            return 0

        token = os.environ.get("GITHUB_TOKEN")
        result = sync_snapshot(client_factory(token), args.destination)
        if result.changed:
            previous = result.previous_commit or "none"
            print(f"updated {previous} -> {result.current_commit}")
            snapshot_status = "snapshot was updated"
        else:
            print(f"unchanged {result.current_commit}")
            snapshot_status = "snapshot is unchanged"
        if args.summary_path is not None:
            try:
                _write_summary(args.summary_path, result.summary)
            except SyncError as error:
                message = (
                    f"{snapshot_status} at {result.current_commit}, but summary "
                    f"writing failed: {error}"
                )
                if token:
                    message = message.replace(token, "[redacted]")
                print(f"error: {message}", file=sys.stderr)
                return 1
        return 0
    except SyncError as error:
        message = str(error)
        if token:
            message = message.replace(token, "[redacted]")
        print(f"error: {message}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
