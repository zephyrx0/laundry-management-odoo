/** @odoo-module **/

import { reactive } from "@odoo/owl";
import { registry } from "@web/core/registry";

/**
 * Tiny shared-state service for the Enterprise-style app drawer (home menu).
 *
 * Kept separate from the component so the navbar (which triggers it) and the
 * drawer (rendered in `main_components`) can talk without prop drilling or
 * patching each other.
 */
export const appDrawerService = {
    start() {
        const state = reactive({ isOpen: false });
        return {
            state,
            open() {
                state.isOpen = true;
            },
            close() {
                state.isOpen = false;
            },
            toggle() {
                state.isOpen = !state.isOpen;
            },
        };
    },
};

registry
    .category("services")
    .add("web_responsive_enterprise.app_drawer", appDrawerService);
