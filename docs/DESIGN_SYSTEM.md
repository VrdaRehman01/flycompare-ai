# FlyCompare design system

All theme values live in `frontend/src/tokens.css`. Components use tokens only; a hard-coded colour in a component is a bug (it will break dark mode).

## Brand

| Role | Token | Light | Dark | Use |
|---|---|---|---|---|
| Primary | `--blue` | `#1a6dff` | `#5b93ff` | Actions, selection, focus |
| Secondary | `--dusk` | `#d9733a` | `#f0975c` | Warm highlights: today, "lowest observed", flexible-date window |
| Ink | `--ink` / `--ink-2` / `--muted` | | | Primary text / secondary text / hints |

The dusk accent comes from the hero photograph, so the warm and cool accents read as one palette.

## Surfaces

`--bg` (page) → `--surface` (cards, popovers) → `--surface-2` (insets, footers) → `--surface-3` (wells, chips, hover). Borders: `--line` (default), `--line-2` (inputs, emphasis).

Dark mode uses neutral graphite surfaces (a faint blue cast) separated by lightness, not saturated navy. Elevation in the dark adds a 1px light edge to the shadow so cards stay distinct.

## Status

`--green` success / live data · `--amber` warning / test data · `--red` errors. Each has a `-soft` background. Data-source labels always use `StatusPill` (Live, Test data, Demo data).

Fare comparisons use `--fare-low`, `--fare-mid` and `--fare-high`, and only when there is enough comparable data (see the fare calendar rules).

## Type

- Display: **Bricolage Grotesque** for `h1`, `h2` and `.display` (page titles, section titles, calendar months, ticket dates).
- UI and body: **Plus Jakarta Sans**.
- Scale: `--fs-xs` 11 · `--fs-sm` 12.5 · `--fs-md` 14 · `--fs-lg` 16 · `--fs-xl` 20 · `--fs-2xl` 28 · `--fs-display` clamp(34–56).

## Space, shape, motion

- Spacing on a 4px grid: `--space-1` (4) … `--space-12` (56).
- Radii: `--radius-xs` 6 (tags) · `--radius-sm` 10 (inputs, tiles) · `--radius` 16 (cards) · `--radius-lg` 22 (popovers, sheets) · `--radius-pill`.
- Motion: `--dur-fast` .15s for hover and press, `--dur` .25s for entering panels, easing `--ease-out`. `prefers-reduced-motion` disables animation globally.
- Layers: `--z-sticky` 20 · `--z-popover` 40 · `--z-modal` 60 · `--z-toast` 80.

## Patterns

- **Popovers** become bottom sheets under 640px, with a dimmed backdrop and sticky header and footer.
- **Unknown is not "no".** Missing provider data is shown as *Unknown* or *Not supplied*, never as "not included" or zero.
- **Observed is not live.** Any price from stored searches says it was *seen*, shows when, and carries its data-source pill.
- **Explain rankings and categories.** Each score and filter category shows the rule behind it.

## Fare calendar

`components/DateField.tsx`, styles in `calendar.css`.

- Ticket-style header with departure and return stubs and a nights counter. Click a stub to choose which date you are editing.
- Modes: *Exact dates*, *± 3 days* (highlights the window and the lowest observed day in it), *Whole month* (12 month tiles with the lowest observed fare per month).
- Day prices come from `GET /api/prices/calendar`: the lowest fare seen per departure date in earlier searches with the same route, trip type, cabin and passengers. Currencies and data sources are never mixed.
- Tiers (lower, typical, higher) appear only with at least 3 observed dates. "Lowest observed month" appears only when 2 or more months each have at least 3 observed dates. Observations older than 7 days are shown faded.
- Keyboard: arrows move by day or week, Home/End jump to the start or end of the week, PageUp/PageDown move a month, Enter selects, Esc closes.
- The search always runs on the exact date chosen; the provider prices one date at a time.
