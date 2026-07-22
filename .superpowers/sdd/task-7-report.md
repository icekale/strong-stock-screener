# Task 7 Report: Vue Types, API Client, And Chart Option

## Commit

- SHA: `2e93bc66bebf15876d8ee054d7e8115e6bcf4341`
- Message: `feat: add sentiment percentile frontend client`

## Changed Files

- `apps/web-vue/src/service/types.ts`
- `apps/web-vue/src/service/product-api.ts`
- `apps/web-vue/src/service/api.test.ts`
- `apps/web-vue/src/utils/charts/sentimentPercentileChart.ts`
- `apps/web-vue/src/utils/charts/sentimentPercentileChart.test.ts`

## TDD Evidence

### RED

Required command:

```bash
cd apps/web-vue && pnpm test:unit -- src/service/api.test.ts src/utils/charts/sentimentPercentileChart.test.ts
```

Observed output: pnpm exited with `ERR_PNPM_IGNORED_BUILDS` while its Codex runtime preflight attempted `pnpm install`; Vitest did not start. The worktree `.npmrc` intentionally has unresolved `allowBuilds` entries, so this was an environment/package-manager preflight failure rather than a test result.

Equivalent command against the now-installed local test runner:

```bash
cd apps/web-vue && ./node_modules/.bin/vitest run src/service/api.test.ts src/utils/charts/sentimentPercentileChart.test.ts
```

Observed RED output: `2 failed`; `getMarketSentimentPercentile is not a function`, and `Cannot find module './sentimentPercentileChart'`.

### GREEN

```bash
cd apps/web-vue && ./node_modules/.bin/vitest run src/service/api.test.ts src/utils/charts/sentimentPercentileChart.test.ts
```

Output:

```text
Test Files  2 passed (2)
Tests  16 passed (16)
```

### Typecheck

Required command:

```bash
cd apps/web-vue && pnpm typecheck
```

Observed output: the same `ERR_PNPM_IGNORED_BUILDS` preflight failure occurred before `vue-tsc` ran.

Equivalent local command:

```bash
cd apps/web-vue && ./node_modules/.bin/vue-tsc --noEmit --skipLibCheck
```

Output: exit code `0` with no diagnostics.

### Additional Checks

```bash
cd apps/web-vue && ./node_modules/.bin/eslint src/utils/charts/sentimentPercentileChart.ts src/utils/charts/sentimentPercentileChart.test.ts
git diff --check
git diff --cached --check
```

Output: all passed with exit code `0`.

## Design Notes

- Frontend contracts preserve the backend Pydantic field names, including all five factors and the exact five-state analysis lifecycle union.
- API methods use existing `apiFetch` and response-error conventions. Query construction uses `URLSearchParams` for `as_of`, `refresh`, `trade_date`, and `force`.
- The chart builder is pure and DOM-independent. It uses concrete colors matching the workbench token defaults, a fixed 0 to 100 scale, threshold areas and lines, per-point extreme/latest symbols, and a complete factor/raw-value HTML tooltip.
- Normal motion is capped at 160ms; reduced motion disables animation.

## Concerns

- The supplied `pnpm` commands cannot execute project scripts in this environment because the Codex pnpm 11 dependency-status preflight rejects unresolved `allowBuilds`; direct locally installed runner commands were used to execute the same test and typecheck programs.
- Linting the pre-existing large `product-api.ts` file reports unrelated formatting and import-sort diagnostics outside this task's added code. The two new chart files pass ESLint cleanly.
- This report is intentionally uncommitted, per the task instructions.

## Fix Review

### Commit

- SHA: `531e58d7f44a62355e86b43bf4146a871928211a`
- Message: `fix: resolve sentiment chart canvas colors`

### Changed Files

- `apps/web-vue/src/service/api.test.ts`
- `apps/web-vue/src/utils/charts/sentimentPercentileChart.ts`
- `apps/web-vue/src/utils/charts/sentimentPercentileChart.test.ts`

### RED

```bash
cd apps/web-vue && ./node_modules/.bin/vitest run src/service/api.test.ts src/utils/charts/sentimentPercentileChart.test.ts
```

Output before the production fix:

```text
Test Files  1 failed | 1 passed (2)
Tests  3 failed | 15 passed (18)
```

The failures showed unresolved `var(...)` strings for the ice-point color, the non-extreme latest-point color, and the serialized ECharts option.

### GREEN

```bash
cd apps/web-vue && ./node_modules/.bin/vitest run src/service/api.test.ts src/utils/charts/sentimentPercentileChart.test.ts
```

Output:

```text
Test Files  2 passed (2)
Tests  18 passed (18)
```

### Typecheck

```bash
cd apps/web-vue && ./node_modules/.bin/vue-tsc --noEmit --skipLibCheck
```

Output: exit code `0` with no diagnostics.

### Focused Lint

```bash
cd apps/web-vue && ./node_modules/.bin/eslint --quiet src/service/api.test.ts src/utils/charts/sentimentPercentileChart.ts src/utils/charts/sentimentPercentileChart.test.ts
```

Output: exit code `0` with no diagnostics after sorting the touched API-test import block.

### Diff Checks

```bash
git diff --check
git diff --cached --check
```

Output: both passed with exit code `0`.

### Fix Notes

- Every chart paint color is now a concrete fallback matching the workbench token defaults; the pure builder contains no unresolved `var(...)` strings.
- The fixture now has separate ice and overheated extremes, an ordinary middle point, and a latest `偏冷` point. Tests independently verify extreme symbols and the latest point's `#245b8a` level color.
- `SentimentAnalysisStatus` has an exact compile-time assertion for all five lifecycle states.

### Residual Concern

- A DOM-independent builder cannot automatically resolve active dark-theme token values. This fix intentionally uses the required concrete workbench defaults; dynamic theme colors would need an explicit resolved palette input in a separate task.

## Controller Verification

- Cross-checked the final TypeScript contracts against `apps/api/app/models.py`. The percentile level/cache unions, all five factor fields, percentile response fields, analysis lifecycle union, risk posture, result fields, and nullable lifecycle metadata match the Pydantic contracts exactly.
- Independent re-review approved the complete two-commit Task 7 diff with no Critical, Important, or Minor findings.
