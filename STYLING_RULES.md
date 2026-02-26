# STYLING RULES

## 1) Source of Truth
- Global styles and design tokens are defined in:
  - `frontend/src/app/globals.css`

Do not redefine theme colors inline when a token exists.

## 2) Color System
- Use CSS variables for all major surfaces and text:
  - `--bg-primary`, `--bg-secondary`, `--bg-tertiary`
  - `--text-primary`, `--text-muted`
  - `--border-primary`
  - semantic tokens: success/warning/danger/info
- For new components:
  - map background/text/border to existing tokens first.
  - add new token only when no existing token fits.

## 3) Typography
- Primary UI font: `IBM Plex Sans Arabic`.
- Mono font: `JetBrains Mono` for code/ids/technical labels.
- Keep heading hierarchy consistent:
  - page title
  - section title
  - card title

## 4) Dark Mode
- Theme toggle is based on `html[data-theme='dark']` and `html[data-theme='light']`.
- New styles must support both modes.
- Avoid hardcoded `#fff`/`#000` unless semantically required.

## 5) RTL and Localization
- Default direction is RTL (`body { direction: rtl; }`).
- All new layouts must be RTL-safe by default.
- When mixing LTR snippets (URLs, IDs, code), isolate direction at element level if needed.

## 6) Spacing and Surfaces
- Use consistent card/surface classes and token-based backgrounds.
- Prefer reusable utility classes over repeated one-off style blocks.
- Keep border opacity and contrast accessible in both themes.

## 7) Motion and Effects
- Existing animations:
  - `animate-fade-in-up`
  - `animate-slide-in-right`
  - `breaking-pulse`
- Use motion with purpose only (state change or information priority).
- Avoid continuous decorative animation on dense views.

## 8) Accessibility Baseline
- Maintain readable contrast in dark/light themes.
- Keep visible focus styles (`app-focus-ring` or equivalent).
- Avoid using color alone for critical status communication.
