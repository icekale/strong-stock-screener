# Watchlist Symbol Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users search and select A-share stocks in the watchlist by code, Chinese name, full pinyin, or pinyin initials without ever saving raw unmatched input as a symbol.

**Architecture:** Extend the existing cached symbol service with internal pinyin search keys and deterministic ranking while keeping the public response unchanged. Expose a generic frontend API name over the existing endpoint, then replace the watchlist plain input with a debounced remote autocomplete that only submits a selected match and ignores stale responses.

**Tech Stack:** Python 3.12, FastAPI, Pydantic 2, `pypinyin`, pytest, Ruff, Vue 3, TypeScript, Ant Design Vue, Vitest.

---

## File Map

- `apps/api/pyproject.toml`: declare the lightweight runtime pinyin dependency.
- `apps/api/uv.lock`: lock the exact transitive dependency graph.
- `apps/api/app/services/chanlun/symbols.py`: build cached internal search entries, rank code/name/pinyin matches, and return the existing public model.
- `apps/api/tests/test_chanlun_service.py`: prove pinyin matching, ranking, deduplication, and local fallback.
- `apps/web-vue/src/service/product-api.ts`: expose a domain-neutral `searchStockSymbols` request while preserving the old export.
- `apps/web-vue/src/service/api.test.ts`: verify query encoding and endpoint behavior.
- `apps/web-vue/src/views/WatchlistView.vue`: render remote candidates and only add a selected stock.
- `apps/web-vue/src/views/WatchlistView.test.ts`: cover search, selection, stale responses, invalid input, and errors.

## Global Constraints

- Preserve the existing watchlist text format, groups, tags, GSGF status, and stock navigation.
- Keep `/api/chanlun/symbols/search` backward compatible; do not create a second symbol-master cache.
- Do not submit text that has not been resolved to a `ChanlunSymbolMatch`.
- Do not touch the unrelated dirty files in the main worktree.
- Keep the implementation scoped to this plan; Chanlun structure work and Docker slimming resume afterward.

### Task 1: Add Cached Pinyin Search Keys and Deterministic Ranking

**Files:**
- Modify: `apps/api/pyproject.toml`
- Modify: `apps/api/uv.lock`
- Modify: `apps/api/app/services/chanlun/symbols.py`
- Test: `apps/api/tests/test_chanlun_service.py`

- [ ] **Step 1: Write failing backend tests**

Add `ChanlunSymbolMatch` to the existing `from app.models import (...)` list, then append tests that prove all accepted query forms return the same public item and that exact matches outrank contains matches:

```python
def test_symbol_search_matches_code_name_full_pinyin_and_initials() -> None:
    service = ChanlunSymbolSearchService(
        loader=lambda: [
            {"code": "600000", "name": "浦发银行"},
            {"code": "600001", "name": "浦发控股"},
            {"code": "000001", "name": "平安银行"},
        ]
    )

    for query in ("600000", "600000.SH", "浦发银行", "pufayinhang", "PFYH"):
        matches, _ = service.search(query, limit=5)
        assert matches[0] == ChanlunSymbolMatch(symbol="600000.SH", name="浦发银行")


def test_symbol_search_ranks_and_deduplicates_matches() -> None:
    service = ChanlunSymbolSearchService(
        loader=lambda: [
            {"code": "600001", "name": "浦发控股"},
            {"code": "600000", "name": "浦发银行"},
        ],
        watchlist_loader=lambda: [{"symbol": "600000.SH", "name": "浦发银行"}],
    )

    exact, _ = service.search("PFYH", limit=10)
    prefix, _ = service.search("PF", limit=10)

    assert [item.symbol for item in exact] == ["600000.SH"]
    assert [item.symbol for item in prefix] == ["600000.SH", "600001.SH"]
```

Extend the existing failure test with `service.search("PFYH")` so the local watchlist row still matches when the Akshare loader fails.

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
/Users/kale/Documents/strong-stock-screener/apps/api/.venv/bin/python -m pytest \
  apps/api/tests/test_chanlun_service.py::test_symbol_search_matches_code_name_full_pinyin_and_initials \
  apps/api/tests/test_chanlun_service.py::test_symbol_search_ranks_and_deduplicates_matches \
  apps/api/tests/test_chanlun_service.py::test_symbol_search_normalizes_local_results_and_fails_safely -q
```

Expected: pinyin queries return no items, so the new assertions fail.

- [ ] **Step 3: Add and lock `pypinyin`**

Add this direct dependency beside the other runtime dependencies:

```toml
"pypinyin>=0.55.0,<0.56.0",
```

Then regenerate only the lockfile:

```bash
uv lock --project apps/api
```

Expected: `apps/api/uv.lock` contains `pypinyin` and the project dependency list remains locked.

- [ ] **Step 4: Implement indexed entries and ranked filtering**

Add a private immutable entry type and pinyin key builder:

```python
from dataclasses import dataclass

from pypinyin import Style, lazy_pinyin


@dataclass(frozen=True)
class _SymbolSearchEntry:
    match: ChanlunSymbolMatch
    full_pinyin: str
    initials: str


def _index_match(match: ChanlunSymbolMatch) -> _SymbolSearchEntry:
    name = match.name.casefold()
    return _SymbolSearchEntry(
        match=match,
        full_pinyin="".join(lazy_pinyin(name, style=Style.NORMAL)).casefold(),
        initials="".join(lazy_pinyin(name, style=Style.FIRST_LETTER)).casefold(),
    )
```

Change the constructor cache annotation and remote loader return type to indexed entries:

```python
cache: TtlCache[tuple[list[_SymbolSearchEntry], StrongStockSourceStatus]] | None = None,

def _load_remote_matches(
    self,
) -> tuple[list[_SymbolSearchEntry], StrongStockSourceStatus]:
```

Index remote matches once inside `_load_remote_matches` with `[_index_match(match) for match in matches]`; index the small local result set in `search` before combining it with the cached entries. Replace `_filter_matches` with deterministic ranking:

```python
def _filter_matches(entries: list[_SymbolSearchEntry], query: str) -> list[ChanlunSymbolMatch]:
    needle = query.strip().casefold()
    ranked: list[tuple[int, str, ChanlunSymbolMatch]] = []
    seen: set[str] = set()
    for entry in entries:
        match = entry.match
        if match.symbol in seen:
            continue
        rank = _match_rank(entry, needle)
        if rank is None:
            continue
        seen.add(match.symbol)
        ranked.append((rank, match.symbol, match))
    ranked.sort(key=lambda item: (item[0], item[1]))
    return [item[2] for item in ranked]


def _match_rank(entry: _SymbolSearchEntry, needle: str) -> int | None:
    if not needle:
        return 0
    symbol = entry.match.symbol.casefold()
    code = symbol.partition(".")[0]
    name = entry.match.name.casefold()
    if needle in {symbol, code}:
        return 0
    if symbol.startswith(needle) or code.startswith(needle):
        return 1
    if name == needle:
        return 2
    if name.startswith(needle):
        return 3
    if entry.initials == needle or entry.initials.startswith(needle):
        return 4
    if entry.full_pinyin.startswith(needle):
        return 5
    if any(needle in value for value in (symbol, name, entry.initials, entry.full_pinyin)):
        return 6
    return None
```

Keep the existing `ChanlunSymbolMatch` response and `source_status` unchanged.

- [ ] **Step 5: Run backend tests and lint**

Run:

```bash
/Users/kale/Documents/strong-stock-screener/apps/api/.venv/bin/python -m pip install 'pypinyin>=0.55.0,<0.56.0'
/Users/kale/Documents/strong-stock-screener/apps/api/.venv/bin/python -m pytest \
  apps/api/tests/test_chanlun_service.py::test_symbol_search_matches_code_name_full_pinyin_and_initials \
  apps/api/tests/test_chanlun_service.py::test_symbol_search_ranks_and_deduplicates_matches \
  apps/api/tests/test_chanlun_service.py::test_symbol_search_normalizes_local_results_and_fails_safely \
  apps/api/tests/test_api.py::test_chanlun_workspace_and_symbol_search_return_service_payloads -q
/Users/kale/Documents/strong-stock-screener/apps/api/.venv/bin/python -m ruff check \
  apps/api/app/services/chanlun/symbols.py apps/api/tests/test_chanlun_service.py
```

Expected: all selected tests pass and Ruff reports no errors.

- [ ] **Step 6: Commit backend search support**

```bash
git add apps/api/pyproject.toml apps/api/uv.lock \
  apps/api/app/services/chanlun/symbols.py apps/api/tests/test_chanlun_service.py
git commit -m "fix(watchlist): support pinyin symbol search"
```

### Task 2: Expose a Domain-Neutral Frontend Search Function

**Files:**
- Modify: `apps/web-vue/src/service/product-api.ts`
- Test: `apps/web-vue/src/service/api.test.ts`

- [ ] **Step 1: Write a failing request-contract test**

Add `searchStockSymbols` to the existing import from `./product-api`, then add:

```typescript
it('encodes generic stock symbol search queries', async () => {
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
    new Response(JSON.stringify({ items: [], source_status: [] }), { status: 200 })
  );

  await searchStockSymbols('浦发 PFYH', { limit: 8 });

  const requestUrl = new URL(String(fetchMock.mock.calls[0]?.[0]));
  expect(requestUrl.pathname).toBe('/api/chanlun/symbols/search');
  expect(Array.from(requestUrl.searchParams.entries())).toEqual([
    ['query', '浦发 PFYH'],
    ['limit', '8']
  ]);
});
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```bash
cd apps/web-vue
CI=true ./node_modules/.bin/vitest run src/service/api.test.ts --reporter=dot
```

Expected: TypeScript module loading fails because `searchStockSymbols` is not exported.

- [ ] **Step 3: Add the generic function and compatibility alias**

Replace the current implementation with:

```typescript
export async function searchStockSymbols(
  query: string,
  options: { limit?: number } = {}
): Promise<ChanlunSymbolSearchResponse> {
  const params = new URLSearchParams({ query, limit: String(options.limit ?? 20) });
  const response = await apiFetch(`${API_BASE_URL}/api/chanlun/symbols/search?${params.toString()}`);
  if (!response.ok) {
    throw new Error(`搜索股票失败：${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<ChanlunSymbolSearchResponse>;
}

export const searchChanlunSymbols = searchStockSymbols;
```

- [ ] **Step 4: Run the frontend API tests**

Run:

```bash
cd apps/web-vue
CI=true ./node_modules/.bin/vitest run src/service/api.test.ts --reporter=dot
```

Expected: all tests in `api.test.ts` pass.

- [ ] **Step 5: Commit the API contract**

```bash
git add apps/web-vue/src/service/product-api.ts apps/web-vue/src/service/api.test.ts
git commit -m "refactor(web): expose generic stock search"
```

### Task 3: Replace Raw Watchlist Input with Remote Stock Selection

**Files:**
- Modify: `apps/web-vue/src/views/WatchlistView.vue`
- Create: `apps/web-vue/src/views/WatchlistView.test.ts`

- [ ] **Step 1: Create failing view tests**

Create `apps/web-vue/src/views/WatchlistView.test.ts` with a remote autocomplete stub and deterministic deferred promises:

```typescript
// @vitest-environment jsdom

import { defineComponent } from 'vue';
import { flushPromises, mount } from '@vue/test-utils';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { ChanlunSymbolSearchResponse, WatchlistPoolResponse } from '@/service/types';
import WatchlistView from './WatchlistView.vue';

type Deferred<T> = {
  promise: Promise<T>;
  resolve: (value: T) => void;
};

const navigation = vi.hoisted(() => ({ push: vi.fn() }));
const api = vi.hoisted(() => ({
  addWatchlistPoolItem: vi.fn(),
  getWatchlistGsgfStatus: vi.fn(),
  getWatchlistPool: vi.fn(),
  saveWatchlistPool: vi.fn(),
  searchStockSymbols: vi.fn()
}));

vi.mock('vue-router', () => ({ useRouter: () => ({ push: navigation.push }) }));
vi.mock('@/service/product-api', () => api);

const AutoCompleteStub = defineComponent({
  inheritAttrs: false,
  props: ['notFoundContent', 'options', 'value'],
  emits: ['search', 'select', 'update:value'],
  template: `
    <div>
      <input
        v-bind="$attrs"
        :value="value"
        @input="$emit('update:value', $event.target.value); $emit('search', $event.target.value)"
      />
      <button
        v-for="option in options"
        :key="option.value"
        :data-symbol="option.symbol"
        @click="$emit('update:value', option.value); $emit('select', option.value)"
      >{{ option.name }} {{ option.symbol }}</button>
      <div v-if="notFoundContent" data-testid="search-empty">{{ notFoundContent }}</div>
    </div>
  `
});

const ButtonStub = defineComponent({
  inheritAttrs: false,
  props: ['disabled', 'loading'],
  emits: ['click'],
  template: '<button v-bind="$attrs" :disabled="disabled" @click="$emit(\'click\')"><slot /></button>'
});

const PlainStub = defineComponent({
  props: ['items', 'title'],
  template: '<section><slot /><slot name="meta" /></section>'
});

function poolFixture(): WatchlistPoolResponse {
  return { content: '', items: [] };
}

function searchFixture(symbol: string, name: string): ChanlunSymbolSearchResponse {
  return { items: [{ symbol, name }], source_status: [] };
}

function deferred<T>(): Deferred<T> {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>(resolvePromise => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
}

function mountView() {
  return mount(WatchlistView, {
    global: {
      stubs: {
        AAlert: { props: ['title'], template: '<div role="alert">{{ title }}</div>' },
        AAutoComplete: AutoCompleteStub,
        AButton: ButtonStub,
        ASpaceCompact: PlainStub,
        ATextarea: true,
        DataList: PlainStub,
        PageHeader: PlainStub,
        SectionHeader: PlainStub,
        StatusTag: true
      }
    }
  });
}

beforeEach(() => {
  vi.useFakeTimers();
  api.getWatchlistPool.mockResolvedValue(poolFixture());
  api.getWatchlistGsgfStatus.mockResolvedValue({ items: [] });
  api.saveWatchlistPool.mockResolvedValue(poolFixture());
  api.addWatchlistPoolItem.mockResolvedValue(poolFixture());
});

afterEach(() => {
  vi.clearAllMocks();
  vi.useRealTimers();
});

describe('WatchlistView symbol search', () => {
  it('searches by user text and renders name plus standard symbol', async () => {
    api.searchStockSymbols.mockResolvedValue(searchFixture('600000.SH', '浦发银行'));
    const wrapper = mountView();
    await flushPromises();

    await wrapper.get('[data-testid="symbol-search-input"]').setValue('PFYH');
    await vi.advanceTimersByTimeAsync(260);
    await flushPromises();

    expect(api.searchStockSymbols).toHaveBeenCalledWith('PFYH', { limit: 20 });
    expect(wrapper.text()).toContain('浦发银行');
    expect(wrapper.text()).toContain('600000.SH');
  });

  it('only submits the selected standard symbol and name', async () => {
    api.searchStockSymbols.mockResolvedValue(searchFixture('600000.SH', '浦发银行'));
    const wrapper = mountView();
    await flushPromises();

    await wrapper.get('[data-testid="symbol-search-input"]').setValue('PFYH');
    await vi.advanceTimersByTimeAsync(260);
    await flushPromises();
    await wrapper.get('[data-symbol="600000.SH"]').trigger('click');
    await wrapper.get('[data-testid="add-symbol"]').trigger('click');
    await flushPromises();

    expect(api.addWatchlistPoolItem).toHaveBeenCalledWith({
      symbol: '600000.SH',
      name: '浦发银行',
      group: '人工关注',
      tags: []
    });
  });

  it('keeps add disabled and reports an empty result until a candidate is selected', async () => {
    api.searchStockSymbols.mockResolvedValue({ items: [], source_status: [] });
    const wrapper = mountView();
    await flushPromises();

    await wrapper.get('[data-testid="symbol-search-input"]').setValue('not-a-stock');
    await vi.advanceTimersByTimeAsync(260);
    await flushPromises();

    expect((wrapper.get('[data-testid="add-symbol"]').element as HTMLButtonElement).disabled).toBe(true);
    expect(wrapper.get('[data-testid="search-empty"]').text()).toBe('未找到匹配股票');
    expect(api.addWatchlistPoolItem).not.toHaveBeenCalled();
  });

  it('ignores a stale response from an older query', async () => {
    const first = deferred<ChanlunSymbolSearchResponse>();
    api.searchStockSymbols
      .mockImplementationOnce(() => first.promise)
      .mockResolvedValueOnce(searchFixture('000001.SZ', '平安银行'));
    const wrapper = mountView();
    await flushPromises();

    await wrapper.get('[data-testid="symbol-search-input"]').setValue('PFYH');
    await vi.advanceTimersByTimeAsync(260);
    await wrapper.get('[data-testid="symbol-search-input"]').setValue('PAYH');
    await vi.advanceTimersByTimeAsync(260);
    await flushPromises();
    expect(wrapper.text()).toContain('平安银行');

    first.resolve(searchFixture('600000.SH', '浦发银行'));
    await flushPromises();

    expect(wrapper.text()).not.toContain('浦发银行');
    expect(wrapper.text()).toContain('平安银行');
  });

  it('shows a rejected search request', async () => {
    api.searchStockSymbols.mockRejectedValue(new Error('股票搜索服务不可用'));
    const wrapper = mountView();
    await flushPromises();

    await wrapper.get('[data-testid="symbol-search-input"]').setValue('PFYH');
    await vi.advanceTimersByTimeAsync(260);
    await flushPromises();

    expect(wrapper.text()).toContain('股票搜索服务不可用');
  });
});
```

- [ ] **Step 2: Run the view tests and verify RED**

Run:

```bash
cd apps/web-vue
CI=true ./node_modules/.bin/vitest run src/views/WatchlistView.test.ts --reporter=dot
```

Expected: tests fail because the page has no autocomplete, search call, or selection state.

- [ ] **Step 3: Implement debounced, stale-safe search state**

Update imports and add the private option state:

```typescript
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import {
  addWatchlistPoolItem,
  getWatchlistGsgfStatus,
  getWatchlistPool,
  saveWatchlistPool,
  searchStockSymbols
} from '@/service/product-api';
import type {
  ChanlunSymbolMatch,
  GsgfAction,
  WatchlistGsgfStatusResponse,
  WatchlistPoolItem,
  WatchlistPoolResponse
} from '@/service/types';

type SymbolOption = ChanlunSymbolMatch & { label: string; value: string };

const symbolOptions = ref<SymbolOption[]>([]);
const selectedSymbol = ref<ChanlunSymbolMatch | null>(null);
const symbolSearchLoading = ref(false);
const symbolSearchError = ref<string | null>(null);
const adding = ref(false);
let symbolSearchTimer: ReturnType<typeof setTimeout> | null = null;
let symbolSearchRequestId = 0;
```

Add the search and selection functions:

```typescript
function queueSymbolSearch(query: string) {
  selectedSymbol.value = null;
  symbolSearchError.value = null;
  if (symbolSearchTimer) clearTimeout(symbolSearchTimer);
  const requestId = ++symbolSearchRequestId;
  const normalized = query.trim();
  if (!normalized) {
    symbolOptions.value = [];
    symbolSearchLoading.value = false;
    return;
  }
  symbolSearchLoading.value = true;
  symbolSearchTimer = setTimeout(() => void runSymbolSearch(normalized, requestId), 250);
}

async function runSymbolSearch(query: string, requestId: number) {
  try {
    const response = await searchStockSymbols(query, { limit: 20 });
    if (requestId !== symbolSearchRequestId) return;
    symbolOptions.value = response.items.map(item => ({
      ...item,
      label: `${item.name} ${item.symbol}`,
      value: item.symbol
    }));
  } catch (cause) {
    if (requestId !== symbolSearchRequestId) return;
    symbolOptions.value = [];
    symbolSearchError.value = cause instanceof Error ? cause.message : '搜索股票失败';
  } finally {
    if (requestId === symbolSearchRequestId) symbolSearchLoading.value = false;
  }
}

function selectSymbol(value: string) {
  const option = symbolOptions.value.find(item => item.value === value);
  selectedSymbol.value = option ? { symbol: option.symbol, name: option.name } : null;
  if (option) symbolInput.value = option.symbol;
}

function stopSymbolSearch() {
  symbolSearchRequestId += 1;
  if (symbolSearchTimer) clearTimeout(symbolSearchTimer);
  symbolSearchTimer = null;
}
```

Replace `addSymbol` so it consumes only `selectedSymbol` and sends the name:

```typescript
async function addSymbol() {
  const selected = selectedSymbol.value;
  if (!selected) return;
  adding.value = true;
  error.value = null;
  try {
    pool.value = await addWatchlistPoolItem({
      symbol: selected.symbol,
      name: selected.name,
      group: '人工关注',
      tags: []
    });
    symbolInput.value = '';
    symbolOptions.value = [];
    selectedSymbol.value = null;
    await load();
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '加入自选失败';
  } finally {
    adding.value = false;
  }
}

onBeforeUnmount(stopSymbolSearch);
```

- [ ] **Step 4: Render the autocomplete and explicit states**

Replace the input inside `a-space-compact` with:

```vue
<a-auto-complete
  v-model:value="symbolInput"
  data-testid="symbol-search-input"
  :options="symbolOptions"
  :not-found-content="symbolSearchLoading ? '搜索中…' : symbolInput.trim() ? '未找到匹配股票' : null"
  placeholder="输入代码、名称或拼音首字母"
  @keydown.enter="addSymbol"
  @search="queueSymbolSearch"
  @select="selectSymbol"
>
  <template #option="option">
    <div class="watchlist-symbol-option">
      <strong>{{ option.name }}</strong>
      <span>{{ option.symbol }}</span>
    </div>
  </template>
</a-auto-complete>
<a-button
  data-testid="add-symbol"
  :disabled="!selectedSymbol"
  :loading="adding"
  type="primary"
  @click="addSymbol"
>加入自选</a-button>
```

Render `<a-alert v-if="symbolSearchError" :title="symbolSearchError" show-icon type="warning" />` directly below the compact input group and add restrained option styling:

```css
.watchlist-symbol-option {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.watchlist-symbol-option span {
  color: var(--wb-muted);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}
```

- [ ] **Step 5: Run view tests and typecheck**

Run:

```bash
cd apps/web-vue
CI=true ./node_modules/.bin/vitest run src/views/WatchlistView.test.ts src/service/api.test.ts --reporter=dot
./node_modules/.bin/vue-tsc --noEmit --skipLibCheck
```

Expected: all selected Vitest tests pass and Vue typecheck exits zero.

- [ ] **Step 6: Commit the watchlist UI**

```bash
git add apps/web-vue/src/views/WatchlistView.vue apps/web-vue/src/views/WatchlistView.test.ts
git commit -m "fix(watchlist): select stocks from search results"
```

### Task 4: Full Verification and Browser Acceptance

**Files:**
- Modify only if verification exposes a defect in files already listed above.

- [ ] **Step 1: Run focused backend verification**

```bash
/Users/kale/Documents/strong-stock-screener/apps/api/.venv/bin/python -m pytest \
  apps/api/tests/test_chanlun_service.py apps/api/tests/test_api.py -q
/Users/kale/Documents/strong-stock-screener/apps/api/.venv/bin/python -m ruff check \
  apps/api/app/services/chanlun/symbols.py apps/api/tests/test_chanlun_service.py
```

Expected: all tests pass and Ruff reports no errors.

- [ ] **Step 2: Run full frontend verification**

```bash
cd apps/web-vue
CI=true ./node_modules/.bin/vitest run --reporter=dot
./node_modules/.bin/vue-tsc --noEmit --skipLibCheck
pnpm build
```

Expected: all Vitest tests pass, typecheck exits zero, and `dist/index.html` is generated.

- [ ] **Step 3: Start local services and verify the browser workflow**

Start the API and frontend on unused local ports. In the watchlist page, verify each query below resolves to `浦发银行 600000.SH` and can be added exactly once:

```text
600000
浦发
pufayinhang
PFYH
```

Verify unmatched text keeps “加入自选” disabled, a search error is visible, existing text-pool editing still saves, and the resulting watchlist row contains the stock name.

- [ ] **Step 4: Commit any verification-only correction**

If verification required a correction, commit only the files already in this plan:

```bash
git add apps/api/pyproject.toml apps/api/uv.lock apps/api/app/services/chanlun/symbols.py \
  apps/api/tests/test_chanlun_service.py apps/web-vue/src/service/product-api.ts \
  apps/web-vue/src/service/api.test.ts apps/web-vue/src/views/WatchlistView.vue \
  apps/web-vue/src/views/WatchlistView.test.ts
git commit -m "fix(watchlist): harden symbol search workflow"
```

If no correction was needed, do not create an empty commit.
