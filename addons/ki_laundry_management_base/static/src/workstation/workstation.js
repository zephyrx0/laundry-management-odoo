/* ----------------------------------------------------------------------------
 *  Kalvyai | Laundry Management - Base
 *  Copyright (c) 2026-Present Kalvyai (https://kalvyai.com)
 *  License: OPL-1. See the LICENSE file.
 * ---------------------------------------------------------------------------- */
import { Component, onWillStart, useRef, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { deserializeDateTime } from "@web/core/l10n/dates";
import { registry } from "@web/core/registry";
import { browser } from "@web/core/browser/browser";
import { useAutofocus, useBus, useService } from "@web/core/utils/hooks";
import { KeepLast } from "@web/core/utils/concurrency";
import { Layout } from "@web/search/layout";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";

const { DateTime } = luxon;
const STEP_STORAGE_KEY = "ki_laundry_workstation_step";
const HELP_STORAGE_KEY = "ki_laundry_workstation_help_hidden";

function readStorage(key) {
    try {
        return browser.localStorage.getItem(key);
    } catch {
        return null;
    }
}

function writeStorage(key, value) {
    try {
        browser.localStorage.setItem(key, value);
    } catch {
        // Storage unavailable (private mode): the preference simply is not remembered.
    }
}

/**
 * Station screen. A worker picks the station they work at (Wash, Iron...), then scans the
 * tag of each garment they finish, or taps "Done" in the queue. The garment then moves to
 * its next station; when every garment of an order is done, the order becomes Ready.
 */
export class LaundryWorkstation extends Component {
    static template = "ki_laundry_management_base.Workstation";
    static components = { Layout };
    static props = { ...standardActionServiceProps };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.keepLast = new KeepLast();
        this.inputRef = useRef("manualInput");
        useAutofocus({ refName: "manualInput" });
        this.state = useState({
            steps: [],
            total: 0,
            stepId: parseInt(readStorage(STEP_STORAGE_KEY)) || false,
            queue: [],
            queueCount: 0,
            busy: false,
            last: null,
            history: [],
            showHelp: !readStorage(HELP_STORAGE_KEY),
        });
        const barcode = useService("barcode");
        useBus(barcode.bus, "barcode_scanned", (ev) => this.scan(ev.detail.barcode));
        onWillStart(() => this.load());
    }

    get display() {
        return { controlPanel: {} };
    }

    get step() {
        return this.state.steps.find((s) => s.id === this.state.stepId);
    }

    get stepName() {
        return this.step ? this.step.name : _t("their next station");
    }

    async load() {
        const data = await this.keepLast.add(
            this.orm.call("ki.laundry.order.item", "ki_workstation_data", [this.state.stepId || false])
        );
        this.state.steps = data.steps;
        this.state.total = data.total;
        this.state.queue = data.queue;
        this.state.queueCount = data.queue_count;
        if (this.state.stepId && !this.step) {
            this.setStep(false);
        }
    }

    setStep(stepId) {
        this.state.stepId = stepId || false;
        writeStorage(STEP_STORAGE_KEY, String(this.state.stepId || ""));
        this.load();
        this.inputRef.el?.focus();
    }

    toggleHelp() {
        this.state.showHelp = !this.state.showHelp;
        writeStorage(HELP_STORAGE_KEY, this.state.showHelp ? "" : "1");
    }

    async scan(barcode) {
        barcode = (barcode || "").trim();
        if (!barcode || this.state.busy) {
            return;
        }
        this.state.busy = true;
        try {
            const result = await this.orm.call("ki.laundry.order.item", "ki_workstation_scan", [
                barcode,
                this.state.stepId || false,
            ]);
            this.state.last = { barcode, ...result };
            this.state.history.unshift({
                key: `${Date.now()}-${barcode}`,
                barcode,
                success: result.success,
                message: result.message,
                time: DateTime.local().toLocaleString(DateTime.TIME_SIMPLE),
            });
            this.state.history.splice(8);
            if (!result.success) {
                this.notification.add(result.message, { title: barcode, type: "danger" });
            }
        } finally {
            this.state.busy = false;
        }
        await this.load();
    }

    onManualKeydown(ev) {
        if (ev.key === "Enter") {
            const value = ev.target.value;
            ev.target.value = "";
            this.scan(value);
        }
    }

    formatDue(value) {
        if (!value) {
            return "";
        }
        const due = deserializeDateTime(value);
        const time = due.toLocaleString(DateTime.TIME_SIMPLE);
        return due.hasSame(DateTime.local(), "day") ? time : `${due.toFormat("dd MMM")} ${time}`;
    }

    isLate(value) {
        return value && deserializeDateTime(value) < DateTime.local();
    }

    routeClass(route) {
        if (route.state === "done") {
            return "o_ki_ws_route_done";
        }
        if (route.state === "skipped") {
            return "o_ki_ws_route_skipped";
        }
        return route.current ? "o_ki_ws_route_current" : "o_ki_ws_route_pending";
    }

    openItem(itemId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "ki.laundry.order.item",
            res_id: itemId,
            views: [[false, "form"]],
        });
    }

    openOrder(orderId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "ki.laundry.order",
            res_id: orderId,
            views: [[false, "form"]],
        });
    }
}

registry.category("actions").add("ki_laundry_workstation", LaundryWorkstation);
