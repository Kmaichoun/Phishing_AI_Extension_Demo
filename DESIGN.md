# Phish Radar AI Design System

## Direction

The Web App combines calm security tooling with a cinematic editorial entry point. The scanner hero is large and direct, while the functional workbench remains dense, gapless, and evidence-led. Near-black application chrome, quiet charcoal surfaces, thin dividers, and a restrained rose action accent keep the product serious without leaning into neon or hacker imagery. Security states retain their own semantic colors so danger, warning, and safe results remain immediately recognizable.

The Dockit source remains a historical visual reference and is licensed under MIT with credit to Astro contributors and Themefisher. Phish Radar AI now uses its own editorial layout, icon system, motion language, and product identity.

## Core tokens

| Role | Dark | Light |
| --- | --- | --- |
| App background | `#0a0a0b` | `#f4f1ed` |
| Surface | `#121214` | `#fbfaf8` |
| Raised/selected surface | `#1a1a1d` | `#eeeae6` |
| Main text | `#f5f3f1` | `#191719` |
| Muted text | `#aaa5a7` | `#686165` |
| Divider | `#2b292c` | `#d7d1cc` |
| Primary rose | `#e17a84` | `#cf646f` |
| Safe | `#43c59e` | `#16835f` |
| Warning | `#f3bd65` | `#9a5b00` |
| Danger | `#f07178` | `#b4232b` |

## Component rules

- Satoshi is the display and Latin UI font. Thai falls back to Leelawadee UI, Noto Sans Thai, and Segoe UI in that order.
- The scanner hero is capped at `72rem`, balanced to two lines on desktop, and uses fluid `clamp()` sizing.
- The scanner follows a single vertical task flow: hero action, URL field, URL preview, then the full analysis. Dashboard uses a dense 12-column grid with 7+5 followed by 4+8.
- Product panels favor thin divider borders; floating overlays may add one short shadow for separation from the host page.
- Cards and panels use 10–14px radii; inputs and buttons use 8–10px.
- Accent is reserved for primary actions, active tabs, focus, and selected state.
- Icons are inline SVG with a shared 24px stroke system. Character and emoji icons are not used.
- The product mark combines a fishing rod and hook with a radar target at the rod tip. `web-app/assets/brand-mark.svg` is the editable source for Web App and Extension PNG icons.
- The Scanner hero presents the mark without decorative radar rings, using one broad rose-violet background fade for separation.
- Risk colors always include labels or icons; color never carries meaning alone.
- Micro-interactions are 150–220ms. Longer scroll-linked motion must explain hierarchy and is removed when `prefers-reduced-motion` is enabled.
- Web theme preference uses local storage only. Passwords and session secrets never use browser storage.

## Surfaces

- `web-app/dockit-theme.css` is the Web App/Login theme layer.
- `web-app/professional-ui.css` is the final Web App, Login, and Settings composition layer.
- `extension/popup.css` owns the compact Popup treatment and its light/dark theme tokens.
- `extension/dockit-extension.css` is the shared theme layer for Warning and QR pages.
- `extension/content.css` and `extension/safe-preview.css` contain scoped Dockit overrides for UI injected into third-party pages; they must never style the host page globally.

## Motion and navigation

- The Web App uses direct, visible navigation for Scanner, QR, Dashboard, account settings, theme, privacy, and session controls.
- Header controls remain on one line on wide screens and move into a dedicated action row at narrower breakpoints.
- Theme changes use a short View Transition when supported; scanning uses a bounded sheen only while analysis is running.
- Page and result transitions explain a state change. Warning content never waits for decorative entrance choreography.
- The Web App uses a sliding active-tab indicator, animated score ring, count-up metrics, staggered result/dashboard content, and a camera scan line tied to live QR state.
- The Web App adds a continuous capability marquee while keeping scanning, navigation, themes, forms, and evidence content available without external motion libraries.
- The Login signature radar communicates layered Rule-based, ML, and LLM protection; it becomes static when reduced motion is requested.
