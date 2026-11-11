# Web Responsive Enterprise

Bring the **Odoo 19 Enterprise** look and a polished, responsive UX to **Odoo 19
Community** — without modifying Odoo core. Free & open source (LGPL-3).

> Built and verified against the Odoo **19.0** source vendored in this repo
> (`odoo/`). It uses only public, stable extension points (asset bundles, the
> `systray`/`services`/`main_components` registries, template inheritance, SCSS
> variable overrides), so it survives 19.0 point releases.

---

## What you get

| Area | What changes |
|------|--------------|
| **Brand** | Enterprise purple navbar / accents (`#714B67` brand, `#875A7B` accent) via an SCSS variable override. |
| **App drawer** | A full-screen, Enterprise-style "home menu": the navbar apps button opens a search box + grid of app icons, with fuzzy search across every menu item. Navbar stays visible above it. |
| **Polish** | Rounded cards & dialogs, soft shadows, sticky control panel, accent notebook tabs, sticky list headers, chatter refinements. |
| **Responsive** | Touch-friendly targets, no horizontal scroll, edge-to-edge form sheets, full-width kanban cards on phones (≥320px). |
| **A11y** | Keyboard focus rings (`:focus-visible`), `prefers-reduced-motion` support, WCAG-AA text contrast. |

---

## How it works (architecture)

* **Brand colour** — `static/src/scss/primary_variables.scss` is injected into
  `web._assets_primary_variables` *before* Odoo's `primary_variables.scss`
  (`('before', …)` directive), so our non-default `$o-community-color` /
  `$o-action` win → purple navbar/accents everywhere.
* **App drawer** — an Owl 2 component registered in `main_components` (mounts
  once inside `.o_web_client`), toggled by a tiny shared-state service. The
  navbar apps button is repointed to it via `extension` template inheritance on
  `web.NavBar.AppsMenu` (no core edits).
* **Styling** — plain SCSS added to `web.assets_backend`, using `--wre-*` CSS
  custom-property design tokens.

---

## File structure

```
web_responsive_enterprise/
├── __init__.py                 # assets-only module, no Python models
├── __manifest__.py
├── README.md
└── static/
    ├── description/index.html
    └── src/
        ├── js/app_drawer/
        │   ├── app_drawer_service.js   # open/close shared state
        │   ├── app_drawer.js + .xml     # full-screen home menu component
        │   └── navbar_patch.js + .xml   # apps button -> opens drawer
        └── scss/
            ├── primary_variables.scss   # enterprise purple override
            ├── theme.scss               # design tokens + light polish
            ├── navbar.scss
            ├── control_panel.scss
            ├── views.scss               # kanban / list / form
            ├── chatter.scss
            ├── dialog.scss
            ├── responsive.scss
            └── app_drawer.scss
```

---

## Installation

This repo runs Odoo 19 via Docker (`./custom-addons` is mounted into the
container).

```bash
docker compose up -d
# Apps → search "Web Responsive Enterprise" → Install, or:
docker compose exec odoo \
  /opt/odoo/odoo/odoo-bin -c /etc/odoo/odoo.conf \
  -d <your_db> -i web_responsive_enterprise --stop-after-init
# then hard-refresh the browser (Ctrl/Cmd+Shift+R)
```

Open the **apps grid icon** (top-left) to launch the app drawer.

---

## Responsive breakpoints

| Breakpoint | Behaviour |
|------------|-----------|
| `≥ 992px` | Full Enterprise layout, sticky control panel, hover lifts. |
| `< 992px` | Larger touch targets on control-panel actions. |
| `< 768px` | No horizontal scroll, edge-to-edge sheets, full-width kanban, static control panel, 40px tap targets. |
| `≤ 360px` | Tightened paddings down to ~320px. |

---

## Scope & limitations

* **Not a 1:1 copy of Enterprise** (its assets are proprietary). This is an
  *inspired-by* community theme using Odoo's own design tokens.
* The app drawer reuses Odoo's `menu` service, so it reflects exactly the apps
  the current user can access.

## Author

**Arun A George** — [arunalexgeorge.online](https://arunalexgeorge.online) ·
[admin@arunalexgeorge.online](mailto:admin@arunalexgeorge.online)

## License

LGPL-3
