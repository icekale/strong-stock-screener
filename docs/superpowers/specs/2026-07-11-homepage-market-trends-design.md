# Homepage Market Trends Design

## Goal

Fill the unused lower half of the market overview with decision-useful change data instead of restoring the decision queue or stretching the existing snapshot panels.

## Composition

Keep the current first row unchanged:

- sector capital flow snapshot
- market state snapshot
- four-index strip

Add one second-row trend band below the index strip:

- left, wider panel: intraday sector rotation curves for up to six leading themes
- right, narrower panel: intraday market emotion score and market breadth curves

The trend band uses the same compact panel vocabulary, borders, typography, and product tokens as the current homepage. It does not introduce nested cards, decorative gradients, large hero metrics, or a decision queue.

## Data Sources

### Sector rotation

Use `getSectorReplicaRadar({ mode: "strength", limit: 6, stockLimit: 1 })`. The endpoint already returns a fixed intraday axis and multiple aligned series used by the sector radar. Show up to six non-empty series and link the panel to `/market?view=sectors`.

### Market emotion

Use `getMarketEmotionSnapshot(tradeDate, 80)`. Plot:

- emotion score on a 0-100 axis
- market breadth percentage, calculated as `advance / (advance + decline) * 100`, on the same 0-100 scale

Show current emotion level, score change from the first usable sample, and current limit-up / limit-down counts in a compact summary row below the chart. Do not add a second metric-card grid.

## Loading

The existing market snapshot requests remain the homepage priority. Render the trend panel shells below the index strip and activate their requests through `IntersectionObserver` when the trend band approaches the viewport. Browsers without `IntersectionObserver` load the trends after mount.

The main refresh button refreshes the trend requests only after the trend band has been activated. Sector and emotion requests settle independently, preserving stale data when a refresh fails.

## States

- Loading: compact skeleton/data state inside each panel.
- Empty: state that explains the relevant intraday history is not available yet.
- Error: local retry action for the failed panel.
- Stale: preserve the prior chart and display the existing stale-data notice.

One failed source must not blank the other panel.

## Responsive Behavior

- Desktop: two columns, approximately 1.55fr / 0.85fr.
- Tablet and mobile: one column.
- Chart area: stable 250-280px desktop height and 220-240px mobile height.
- Legends and summaries may wrap, but the page must not gain horizontal overflow.

## Testing

- Unit-test emotion sample normalization, breadth calculation, duplicate timestamp handling, and empty samples.
- Source-contract test the homepage lazy activation and both API calls.
- Run the full web test suite and production build.
- Visually verify `/` at desktop, tablet, and phone widths with real local data.

## Out Of Scope

- Restoring the decision queue.
- Adding screening, auction Top3, or watchlist requests to the homepage.
- Changing the sector radar or sentiment detail pages.
- Adding new backend endpoints or dependencies.
