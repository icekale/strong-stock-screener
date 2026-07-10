# Sector Page UI Layout Design

## Goal

Improve `/sectors` for fast intraday scanning while preserving the current sector radar data contract, cache behavior, and existing workbench visual language.

The chosen direction is the existing two-column composition: a fixed-width sector list on the left, with the selected sector chart and component-stock table on the right/below.

## Scope

In scope:

- Rebalance the `/sectors` layout and spacing for desktop, tablet, and mobile.
- Keep all 12 market-emotion metrics visible.
- Make current-board selection and curve-comparison selection visually distinct.
- Improve loading, refresh, error, selected, hover, and focus states.
- Keep the existing API response shapes, session cache validation, refresh intervals, and stock navigation.
- Verify the page at desktop and mobile widths.

Out of scope:

- Backend data-source or curve-generation changes.
- New navigation modules.
- New market metrics or new sector-ranking logic.

## Composition

### Page frame

- Keep the full-height workbench shell and existing neutral surface tokens.
- Reduce unnecessary outer padding so the radar uses the available viewport without becoming a nested card stack.
- Preserve the current compact system font and market red/green semantic colors.

### Emotion metrics

- Render all 12 emotion metrics in a compact grid.
- Use six columns by two rows on wide desktop screens.
- Use four columns by three rows on medium screens.
- Preserve all metrics on narrow screens through structural reflow or horizontal overflow; do not remove metrics.
- Keep metric states quiet by default and reserve stronger color for semantic values.

### Radar workspace

- Use a two-column grid on desktop.
- Keep the left board list near 280px wide and allow the chart to consume remaining width.
- Add a compact board-list header showing the active mode and selected comparison count.
- Keep list rows dense, keyboard accessible, and independently scrollable.
- Keep the chart header, source status, and refresh control on one aligned row when space allows.
- Keep the chart as the primary visual surface with stable height and responsive resize behavior.

### Sub-themes and stocks

- Keep the sub-theme selector directly above the stock table.
- Use a single dense horizontal rail with overflow scrolling so selecting a theme does not change page height unpredictably.
- Preserve the `全部` option and selected state.
- Keep the stock table compact with a sticky header, hover feedback, semantic change colors, and horizontal scrolling on narrow screens.
- Preserve stock links to the existing K-line route.

## Interaction Model

- Clicking a board name changes the current board and refreshes the sub-theme and stock context.
- Checking a board controls whether its curve is included in the comparison set.
- The current board may remain active even when the comparison set contains multiple boards.
- Mode changes clear the active sub-theme, refresh the radar, and keep the current comparison behavior.
- Manual refresh keeps the existing loading state and does not discard valid cached data while the request is pending.
- Background refresh updates data without blocking the current visible layout.
- When a board or stock request is loading, retain the existing content where possible and show a compact status indication.
- Error messages remain inline near the affected radar content and do not replace the entire page.

## Responsive Behavior

- Wide desktop: metrics in a 6x2 grid; radar list and chart side by side; stock table below.
- Tablet: metrics in a 4x3 grid; board list moves above the chart; board rows use a compact two-column layout.
- Mobile: metrics remain available through horizontal scrolling or compact reflow; mode tabs and active board remain reachable; board list, sub-theme rail, and table scroll horizontally or vertically within bounded containers.
- Do not use fluid display typography. Keep labels and controls within their containers at all widths.

## Visual and Accessibility States

- Selected board, active board, comparison checkbox, and active sub-theme must have distinct visual treatments.
- All buttons and checkboxes keep visible keyboard focus styles.
- Disabled refresh controls must communicate the loading state without hiding the latest data.
- Error, stale, and estimated source statuses must remain readable and not rely on color alone.
- Respect `prefers-reduced-motion` by reducing transitions to immediate state changes.

## Verification

- Add or update focused frontend tests for selection, cache-safe rendering, and state labels where behavior changes.
- Run the web test suite and production build.
- Run `git diff --check`.
- Smoke-test `/sectors` with valid and stale session cache data.
- Inspect desktop and mobile screenshots for clipping, overlap, chart resize, table overflow, and control focus.

## Success Criteria

- A user can identify the active board, comparison set, chart status, and stock context within three seconds.
- All 12 metrics remain available without crowding the chart or causing uncontrolled page growth.
- Board selection and curve comparison no longer appear to be the same action.
- The page remains usable at desktop, tablet, and mobile widths.
- Existing sector data and navigation behavior continue to work unchanged.
