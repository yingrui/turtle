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
