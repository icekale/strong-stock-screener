from __future__ import annotations

import hashlib
import http.client
import json
import re
import shutil
import tempfile
import urllib.error
import urllib.request
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol, TypedDict


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
REPOSITORY_IDENTITY = f"{OWNER}/{REPOSITORY}"
JSON_MAX_BYTES = 1_000_000
GITHUB_ACCEPT = "application/vnd.github+json"
USER_AGENT = "StockMaster/a-stock-data-sync"
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


@dataclass
class _SnapshotTransactionState:
    backup: Path | None = None
    previous_backed_up: bool = False
    candidate_installed: bool = False


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


def _load_existing_snapshot(destination: Path) -> _ExistingSnapshot | None:
    if not destination.exists():
        return None
    if not destination.is_dir():
        raise SyncError(f"snapshot destination is not a directory: {destination}")

    metadata_path = destination / "metadata.json"
    try:
        payload = json.loads(metadata_path.read_bytes())
    except FileNotFoundError as error:
        raise SyncError(f"existing snapshot is missing {metadata_path.name}") from error
    except (json.JSONDecodeError, RecursionError, UnicodeDecodeError) as error:
        raise SyncError(f"existing {metadata_path.name} contains malformed JSON") from error
    except OSError as error:
        raise SyncError(f"could not read existing {metadata_path.name}") from error

    if (
        not isinstance(payload, dict)
        or type(payload.get("schema_version")) is not int
        or payload["schema_version"] != 1
    ):
        raise SyncError(f"existing {metadata_path.name} has an invalid schema")
    upstream = payload.get("upstream")
    artifacts = payload.get("artifacts")
    if not isinstance(upstream, dict) or not isinstance(artifacts, dict):
        raise SyncError(f"existing {metadata_path.name} has an invalid schema")
    if set(artifacts) != set(REQUIRED_FILES):
        raise SyncError(f"existing {metadata_path.name} has an invalid schema")
    for artifact in artifacts.values():
        if not isinstance(artifact, dict):
            raise SyncError(f"existing {metadata_path.name} has an invalid schema")
        raw_url = artifact.get("raw_url")
        size = artifact.get("size")
        sha256 = artifact.get("sha256")
        if (
            not isinstance(raw_url, str)
            or type(size) is not int
            or size < 0
            or not isinstance(sha256, str)
            or SHA256_RE.fullmatch(sha256) is None
        ):
            raise SyncError(f"existing {metadata_path.name} has an invalid schema")

    required_upstream_fields = (
        "owner",
        "repository",
        "branch",
        "commit",
        "version",
        "committed_at",
        "synced_at",
        "commit_url",
    )
    if any(not isinstance(upstream.get(field), str) for field in required_upstream_fields):
        raise SyncError(f"existing {metadata_path.name} has an invalid schema")

    commit = upstream["commit"]
    version = upstream["version"]
    if (
        upstream["owner"] != OWNER
        or upstream["repository"] != REPOSITORY
        or upstream["branch"] != BRANCH
        or SHA_RE.fullmatch(commit) is None
        or SEMANTIC_VERSION_RE.fullmatch(version) is None
    ):
        raise SyncError(f"existing {metadata_path.name} has an invalid schema")

    skill_path = destination / "SKILL.md"
    try:
        skill = skill_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise SyncError("could not read existing SKILL.md") from error
    return _ExistingSnapshot(commit=commit, version=version, skill=skill)


def _normalize_committed_at(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ArtifactValidationError("resolved commit timestamp must be nonempty")
    iso_value = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        committed_at = datetime.fromisoformat(iso_value)
    except ValueError as error:
        raise ArtifactValidationError("resolved commit timestamp is invalid") from error
    if committed_at.tzinfo is None or committed_at.utcoffset() is None:
        raise ArtifactValidationError("resolved commit timestamp must include a timezone")
    return committed_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _format_synced_at(now: Callable[[], datetime]) -> str:
    current = now()
    if current.tzinfo is None or current.utcoffset() is None:
        raise SyncError("sync clock must return a timezone-aware datetime")
    return current.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _format_section_list(names: list[str]) -> str:
    if not names:
        return "None"
    return ", ".join(f"`{name}`" for name in names)


def _build_summary(
    *,
    previous_commit: str | None,
    current_commit: str,
    previous_version: str | None,
    current_version: str,
    section_diff: dict[str, list[str]],
) -> str:
    old_commit = previous_commit or "none"
    old_version = previous_version or "none"
    return "\n".join(
        (
            "# a-stock-data snapshot sync",
            "",
            f"- Upstream: `{REPOSITORY_IDENTITY}`",
            f"- Commit: `{old_commit}` -> `{current_commit}`",
            f"- Version: `{old_version}` -> `{current_version}`",
            "",
            "## Sections",
            "",
            f"- Added: {_format_section_list(section_diff['added'])}",
            f"- Changed: {_format_section_list(section_diff['changed'])}",
            f"- Removed: {_format_section_list(section_diff['removed'])}",
            "",
        )
    )


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
                try:
                    _replace_path(state.backup, destination)
                except OSError as restore_error:
                    raise SyncError(
                        "failed to replace snapshot and restore previous snapshot"
                    ) from restore_error
                state.previous_backed_up = False
            raise SyncError("failed to replace snapshot") from error
        state.candidate_installed = True

        if state.candidate_installed and state.backup is not None:
            try:
                _remove_directory(state.backup)
            except OSError as error:
                try:
                    _replace_path(destination, candidate)
                    state.candidate_installed = False
                    _replace_path(state.backup, destination)
                    state.previous_backed_up = False
                except OSError as rollback_error:
                    if not destination.exists() and candidate.exists():
                        try:
                            _replace_path(candidate, destination)
                            state.candidate_installed = True
                        except OSError:
                            pass
                    raise SyncError(
                        "failed to remove snapshot backup and roll back"
                    ) from rollback_error
                raise SyncError(
                    "failed to remove snapshot backup; restored previous snapshot"
                ) from error
            state.backup = None
            state.previous_backed_up = False
    finally:
        if candidate.exists():
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
    if previous_commit == commit:
        section_diff = {"added": [], "changed": [], "removed": []}
        summary = _build_summary(
            previous_commit=previous_commit,
            current_commit=commit,
            previous_version=previous_version,
            current_version=previous_version,
            section_diff=section_diff,
        )
        return SyncResult(
            changed=False,
            previous_commit=previous_commit,
            current_commit=commit,
            previous_version=previous_version,
            current_version=previous_version,
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
