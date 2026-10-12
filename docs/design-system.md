# Frontend design system

SCSS tokens and styling conventions for the stock trading SPA (`frontend/src/styles/`). **Derived from [openKMS](https://github.com/yingrui/openKMS)** — same palette, spacing rhythm, and `.btn*` primitives; this project omits openKMS-only modules (knowledge map, account-page layout, TableRowActions).

## What was copied from openKMS

These files are **byte-identical** to openKMS (copied at scaffold time):

| File | Role |
|------|------|
| `_css-variables.scss` | Runtime `var(--*)` tokens — palette, spacing, typography, z-index, dark mode (`[data-theme='dark']`) |
| `_tokens.scss` | Compile-time breakpoints, `$km-layout-max`, z-index |
| `_mixins.scss` | `max-width` / `min-width`, `focus-ring-accent`, `motion-tokens` |
| `_global.scss` | Reset, `body`, links, `.btn*` buttons |
| `_utilities.scss` | Cross-route helpers (error banners, table empty, flex modifiers) |
| `_pagination.scss` + `Pagination.tsx` | Shared pagination component |

## Not copied (openKMS-only)

| openKMS path | Why omitted |
|--------------|-------------|
| `_index.scss`, `index.ts` | Barrel exports — this app imports SCSS paths directly |
| `TableRowActions.tsx`, `_table-row-actions.scss` | Not used in current routes yet |
| `knowledge-map/` | Map-specific tokens |
| `styles/account-page.scss` | Settings/account layout — no Profile/Settings pages here |

To add a shared component from openKMS later, copy the file pair and register it in this doc.

## Entry

- **`frontend/src/index.scss`** — loads `design-system/_css-variables`, `_global`, `_utilities`

## Conventions

1. **Colors** — `var(--color-*)`; avoid raw hex in feature SCSS
2. **Spacing** — `var(--space-*)` on a 4px grid
3. **Breakpoints** — `@include max-width(ds.$bp-md-min)` via `@use '…/tokens' as ds` and `@use '…/mixins' as *`
4. **Theme** — toggle sets `data-theme="dark"` on `<html>`
5. **Layout shell** — sidebar 220px (`--sidebar-width`), header 56px (`--header-height`), accent teal (`--color-accent`)

### Market direction colours

Quote changes, holdings P&L and trade P&L all use the A-share convention: **up/gain is red,
down/loss is green**. Use the shared utilities instead of page-local `.up` / `.down` rules:

| Token / class | Meaning |
|---------------|---------|
| `--color-up` / `.price-up` | Rise, gain, positive P&L |
| `--color-down` / `.price-down` | Fall, loss, negative P&L |
| `.price-flat` | Unchanged (`--color-text-secondary`) |

Both tokens have dark-mode values in `_css-variables.scss`. Used by Home, Market, Stock detail,
Watchlist and Portfolio.

## Shared components

| Component | Where | Use |
|-----------|-------|-----|
| `DataTable` | `frontend/src/components/DataTable.tsx` | Every data table. Column definitions (`align`, `sortable`, `sortValue`, `render`, `cellClassName`), client-side sorting by default, optional controlled sorting for server-sorted data, selection checkboxes, loading/empty slots, row click, horizontal scroll. |
| `Pagination` | `styles/design-system/Pagination.tsx` | Page controls next to a table. |
| `TradeDrawer` | `components/portfolio/TradeDrawer.tsx` | Record a buy/sell for one symbol (portfolio page and screening results). |

```tsx
const columns: Column<Row>[] = [
  { key: 'code', label: 'Code', sortable: true, sortValue: (r) => r.code, render: (r) => r.code },
  { key: 'chg', label: 'Chg', align: 'right', sortValue: (r) => r.pct, render: (r) => r.pct },
];

<DataTable columns={columns} rows={rows} rowKey={(row) => row.code} empty={t('…')} />;
```

Sorting is uncontrolled unless you pass `sortCol` + `onSortChange` (do that when the server returns
sorted rows, e.g. the market list). Numeric columns use `align: 'right'` (adds `.num` with
tabular-nums). Market colours come from `cellClassName` returning `price-up` / `price-down`.
Tests: `DataTable.test.tsx` covers sort order, nulls-last, controlled mode, empty/loading and
selection.

## New page stylesheet

Colocate `Page.scss` next to the component:

```scss
@use '../../styles/design-system/mixins' as *;
@use '../../styles/design-system/tokens' as ds;
```

(Adjust `../` depth from `src/pages/` vs `src/components/`.)

## Stack

- React 19 + TypeScript + Vite
- SCSS (no Tailwind/MUI)
- lucide-react icons, sonner toasts
- Apache ECharts for charts

## Updating this doc

When adding reusable patterns under `frontend/src/styles/` or copying more files from openKMS, update this page and the table in [Architecture](architecture.md).
