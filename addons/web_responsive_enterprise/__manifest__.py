# -*- coding: utf-8 -*-
{
    "name": "Web Responsive Enterprise",
    "summary": "Odoo 19 Enterprise look & feel and responsive UX for "
               "Community Edition (light mode).",
    "description": """
Web Responsive Enterprise
=========================
Brings the Odoo 19 *Enterprise* look and feel to the *Community* backend
without touching Odoo core:

* Enterprise purple brand colour scheme (navbar, accents, buttons).
* Full-screen Enterprise-style app drawer (home menu) with search.
* Visual polish: rounded cards, soft shadows, sticky control panel, refined
  notebook tabs, dialogs with backdrop blur.
* Responsive / touch refinements layered on top of Odoo's already-responsive
  web client, plus accessibility (focus rings, reduced-motion, WCAG-AA text).

100% Community compatible and upgrade-safe across 19.0 point releases.
""",
    "version": "19.0.2.0.0",
    "category": "Theme/Backend",
    "author": "Arun A George",
    "maintainer": "Arun A George",
    "website": "https://arunalexgeorge.online",
    "support": "admin@arunalexgeorge.online",
    "license": "LGPL-3",
    "images": ["static/description/banner.png"],
    "depends": ["web"],
    "assets": {
        # --- SCSS variable overrides --------------------------------------
        # Processed *before* Odoo's primary_variables.scss so our non-default
        # assignments win over the core `!default` values (enterprise purple).
        "web._assets_primary_variables": [
            (
                "before",
                "web/static/src/scss/primary_variables.scss",
                "web_responsive_enterprise/static/src/scss/primary_variables.scss",
            ),
        ],
        # --- Backend styles + app drawer ----------------------------------
        "web.assets_backend": [
            "web_responsive_enterprise/static/src/scss/theme.scss",
            "web_responsive_enterprise/static/src/scss/navbar.scss",
            "web_responsive_enterprise/static/src/scss/control_panel.scss",
            "web_responsive_enterprise/static/src/scss/views.scss",
            "web_responsive_enterprise/static/src/scss/chatter.scss",
            "web_responsive_enterprise/static/src/scss/dialog.scss",
            "web_responsive_enterprise/static/src/scss/responsive.scss",
            "web_responsive_enterprise/static/src/scss/app_drawer.scss",
            "web_responsive_enterprise/static/src/js/app_drawer/app_drawer_service.js",
            "web_responsive_enterprise/static/src/js/app_drawer/app_drawer.js",
            "web_responsive_enterprise/static/src/js/app_drawer/app_drawer.xml",
            "web_responsive_enterprise/static/src/js/app_drawer/navbar_patch.js",
            "web_responsive_enterprise/static/src/js/app_drawer/navbar_patch.xml",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
