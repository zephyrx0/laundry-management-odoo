/** @odoo-module **/

import { Component, useState, useRef, useEffect, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Transition } from "@web/core/transition";
import { fuzzyLookup } from "@web/core/utils/search";
import { _t } from "@web/core/l10n/translation";

/**
 * Enterprise-style App Drawer ("home menu").
 *
 * A full-screen overlay with a search box and a grid of large app icons,
 * replacing Community's plain apps dropdown. Typing also fuzzy-searches every
 * menu item across apps. Rendered once via the `main_components` registry and
 * toggled through the `app_drawer` service (the navbar apps button triggers it).
 */
export class AppDrawer extends Component {
    static template = "web_responsive_enterprise.AppDrawer";
    static components = { Transition };
    static props = {};

    setup() {
        this.menuService = useService("menu");
        this.drawerSvc = useService("web_responsive_enterprise.app_drawer");
        this.drawer = useState(this.drawerSvc.state);
        this.state = useState({ query: "" });
        this.searchRef = useRef("search");

        // Focus the search on open; clear the query on close.
        useEffect(
            (isOpen) => {
                if (isOpen) {
                    // Defer so the (transitioned) input is in the DOM.
                    const id = setTimeout(() => this.searchRef.el?.focus(), 50);
                    return () => clearTimeout(id);
                }
                this.state.query = "";
            },
            () => [this.drawer.isOpen]
        );

        // Close on Escape from anywhere.
        const onKeydown = (ev) => {
            if (this.drawer.isOpen && ev.key === "Escape") {
                this.drawerSvc.close();
            }
        };
        window.addEventListener("keydown", onKeydown);
        onWillUnmount(() => window.removeEventListener("keydown", onKeydown));
    }

    get apps() {
        const apps = this.menuService.getApps();
        const q = this.state.query.trim();
        return q ? fuzzyLookup(q, apps, (a) => a.name) : apps;
    }

    /** Matching sub-menus (only while searching), with their app for context. */
    get menuItems() {
        const q = this.state.query.trim();
        if (!q) {
            return [];
        }
        const subMenus = this.menuService
            .getAll()
            .filter((m) => m.id !== "root" && m.actionID && m.id !== m.appID && m.name);
        return fuzzyLookup(q, subMenus, (m) => `${this.appName(m)} / ${m.name}`).slice(0, 24);
    }

    get menuItemsLabel() {
        return _t("Menu Items");
    }

    appName(menu) {
        const app = this.menuService.getMenu(menu.appID);
        return app ? app.name : "";
    }

    /** Direct URL so middle-click / open-in-new-tab works on the tiles. */
    href(menu) {
        return `/odoo/${menu.actionPath || "action-" + menu.actionID}`;
    }

    open(menu) {
        this.menuService.selectMenu(menu);
        this.drawerSvc.close();
    }

    onSearchKeydown(ev) {
        if (ev.key === "Enter") {
            const target = this.apps[0] || this.menuItems[0];
            if (target) {
                this.open(target);
            }
        }
    }
}

registry.category("main_components").add("web_responsive_enterprise.AppDrawer", {
    Component: AppDrawer,
});
