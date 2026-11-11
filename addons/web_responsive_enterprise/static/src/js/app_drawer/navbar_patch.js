/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { NavBar } from "@web/webclient/navbar/navbar";

/**
 * Make the navbar "apps" (grid) button open the Enterprise-style app drawer
 * instead of the stock Community dropdown. The template override in
 * `navbar_patch.xml` swaps the <Dropdown> for a button that calls this.
 */
patch(NavBar.prototype, {
    setup() {
        super.setup();
        this.appDrawer = useService("web_responsive_enterprise.app_drawer");
    },

    onAppDrawerToggle() {
        this.appDrawer.toggle();
    },
});
