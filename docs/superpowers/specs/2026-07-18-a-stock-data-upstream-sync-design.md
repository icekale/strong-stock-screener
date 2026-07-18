# a-stock-data Upstream Sync Design

## Context

StockMaster currently integrates market data through first-party providers such as TickFlow,
Tencent, TDX, and Eastmoney. The upstream
[`simonlin1212/a-stock-data`](https://github.com/simonlin1212/a-stock-data) project is useful as a
maintained catalog of A-share endpoints and fallback strategies, but it is not an installable
Python package. Its runtime examples live inside a large `SKILL.md` file and do not expose a stable
module API.

Automatically pulling and executing the latest Markdown code would allow an unreviewed upstream
change to affect live market data. The integration therefore uses a two-stage process: synchronize
an immutable upstream snapshot into a review PR, then promote selected changes into StockMaster
providers through a separate implementation PR.

## Goals

- Check the upstream `main` branch once per day and on manual request.
- Synchronize reviewed source artifacts only when the upstream commit changes.
- Create or update one stable synchronization PR with an auditable change summary.
- Pin every downloaded file to one resolved upstream commit.
- Validate provenance, license, completeness, size, version, and checksums before writing files.
- Keep synchronization deterministic, idempotent, and safe to rerun.
- Preserve the current runtime providers and deployment behavior.

## Non-goals

- Do not import or execute Python snippets from upstream Markdown.
- Do not automatically modify StockMaster runtime providers.
- Do not automatically merge, deploy, or rebuild Docker images.
- Do not synchronize all upstream assets or Git history.
- Do not implement a general-purpose dependency update service.

## Architecture

### Scheduled workflow

Add `.github/workflows/sync-a-stock-data.yml` with:

- A daily cron at `22:30 UTC`, corresponding to `06:30 Asia/Shanghai`.
- `workflow_dispatch` for manual runs.
- Minimal permissions: `contents: write` and `pull-requests: write`.
- A concurrency group dedicated to this upstream so two runs cannot race.
- A stable branch named `automation/a-stock-data-sync`.

The workflow runs the synchronization script, targeted tests, and repository checks. When the
snapshot changes, it commits only synchronization artifacts and creates or updates one PR. When
nothing changes, it exits successfully without creating a commit or PR.

The automation branch must not be a deployment source. Existing release behavior remains tied to
reviewed changes merged into `main`.

### Synchronization script

Add `scripts/sync_a_stock_data.py` as a standard-library Python CLI. It should keep network access
behind a small injectable client so its behavior can be tested without GitHub.

The script performs these steps:

1. Resolve the current upstream `main` commit through the GitHub API.
2. Compare it with the commit stored in the local metadata file.
3. If unchanged, report a no-op and exit successfully.
4. Download `SKILL.md`, `CHANGELOG.md`, and `LICENSE` using raw URLs pinned to the resolved commit.
5. Validate all downloaded artifacts in memory.
6. Build deterministic metadata and a Markdown change summary.
7. Write the complete snapshot through temporary files and atomic replacements.

The script must never download from a moving branch after resolving the commit. A partial network
failure or validation error must leave the previous snapshot untouched.

### Vendored snapshot

Store synchronized files under `third_party/a-stock-data/`:

- `SKILL.md`
- `CHANGELOG.md`
- `LICENSE`
- `metadata.json`

`metadata.json` records:

- Upstream owner, repository, branch, and commit.
- Parsed upstream version.
- Upstream commit timestamp and local synchronization timestamp.
- Source URL pinned to the upstream commit.
- File size and SHA256 for every synchronized artifact.

The current Git repository preserves earlier snapshots; the synchronization process does not create
parallel timestamped copies.

### Pull request report

The workflow-generated PR includes:

- Previous and current upstream versions and commits.
- Links to the upstream commit and comparison page.
- Added, removed, and changed top-level Markdown sections.
- Artifact sizes and SHA256 values.
- A warning when sections related to currently used capabilities change, such as Tencent quotes,
  mootdx K-lines, Eastmoney market data, industry mapping, or fallback sources.
- A checklist confirming that no upstream code is executed by the synchronization PR.

The report is generated from validated local artifacts. PR creation is not part of the Python
script's data transformation logic; the workflow owns Git and GitHub operations.

## Validation And Security

The script rejects an update when any of these conditions hold:

- The resolved repository identity is not `simonlin1212/a-stock-data`.
- The upstream commit is missing or malformed.
- A required file is missing, empty, unexpectedly large, or returned as an HTML error page.
- `SKILL.md` lacks its expected project heading or a parseable version marker.
- `LICENSE` does not identify Apache License 2.0.
- A downloaded byte sequence does not match the checksum recorded for the candidate snapshot.

Reasonable maximum file sizes are hard limits rather than warnings. GitHub authentication uses the
workflow's `GITHUB_TOKEN`; no third-party credentials are required. Logs must not print token values
or request headers.

The synchronization workflow only vendors source material. It does not use `exec`, dynamic imports,
subprocess execution of upstream content, or generated Python modules.

## Failure Handling

- GitHub timeout, rate limit, malformed JSON, or partial download: fail the workflow and preserve the
  previous snapshot.
- Validation failure: fail with a specific artifact and rule; do not commit.
- No upstream change: exit zero with a concise no-op message.
- Existing synchronization PR: update the same branch and PR rather than opening another one.
- Concurrent run: cancel or queue through the workflow concurrency group.
- PR creation failure after a valid commit: leave the automation branch available for the next run
  to reuse.

Failures are visible in GitHub Actions. They do not affect the FastAPI process, Vue frontend, local
data caches, Docker images, or Unraid deployment.

## Testing

Add focused tests for the synchronization module using an in-memory fake GitHub client and temporary
directories. Cover:

- An unchanged commit produces no file changes.
- A new commit writes all artifacts and complete metadata.
- Repeating the same update is idempotent.
- Every raw file URL is pinned to the same resolved commit.
- Missing files, invalid license, missing version, oversized content, and HTML error content fail.
- A failure after one or more downloads leaves the old snapshot intact.
- Metadata checksums match the exact vendored bytes.
- Section comparison produces stable, useful PR summary data.

Repository contract tests should verify that the workflow has the expected schedule, manual trigger,
minimal permissions, concurrency group, stable branch, and no deployment command.

## Acceptance Criteria

- A manual run against an unchanged upstream commit succeeds without modifying the repository.
- A simulated upstream commit change produces one complete, checksum-valid snapshot.
- A scheduled run creates or updates only `automation/a-stock-data-sync` and its single PR.
- The PR clearly identifies upstream provenance and affected sections.
- Invalid or incomplete upstream content cannot replace the previous snapshot.
- Synchronization changes do not modify `apps/api`, `apps/web-vue`, Docker, or Unraid configuration.
- Merging a snapshot PR cannot switch or reload any runtime data provider.

## Runtime Promotion Boundary

When a synchronized change should improve a StockMaster provider, that work happens in a separate
feature branch. The implementation must adapt the relevant endpoint into the existing provider
interfaces, preserve StockMaster's source-priority and fallback rules, add rate limiting where the
source requires it, and include provider contract tests. Only that reviewed feature PR may affect
runtime behavior.

