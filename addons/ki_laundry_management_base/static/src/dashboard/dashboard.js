/* ----------------------------------------------------------------------------
 *  Kalvyai | Laundry Management - Base
 *  Copyright (c) 2026-Present Kalvyai (https://kalvyai.com)
 *  License: OPL-1. See the LICENSE file.
 * ---------------------------------------------------------------------------- */
import { Component, onWillStart, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { deserializeDateTime } from "@web/core/l10n/dates";
import { registry } from "@web/core/registry";
import { KeepLast } from "@web/core/utils/concurrency";
import { useService } from "@web/core/utils/hooks";
import { formatFloat, formatMonetary } from "@web/views/fields/formatters";
import { Layout } from "@web/search/layout";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";
import { LaundryDashboardChart } from "./dashboard_chart";

const { DateTime } = luxon;

/**
 * Registry of extra dashboard sections. Each entry: { component, sequence, dataKey }.
 * A section renders only when the server returned ``sections[dataKey]``, so the POS /
 * Website modules register their section and extend
 * ``ki.laundry.dashboard._ki_dashboard_sections`` on the server.
 * Sections receive ``data`` and ``helpers`` props.
 */
export const dashboardSections = registry.category("ki_laundry_dashboard_sections");

export class LaundryDashboard extends Component {
    static template = "ki_laundry_management_base.Dashboard";
    static components = { Layout, LaundryDashboardChart };
    static props = { ...standardActionServiceProps };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.keepLast = new KeepLast();
        this.periods = [
            { key: "today", label: _t("Today") },
            { key: "week", label: _t("7 Days") },
            { key: "month", label: _t("30 Days") },
            { key: "year", label: _t("This Year") },
        ];
        this.state = useState({ period: "week", data: null });
        onWillStart(() => this.load());
    }

    get display() {
        return { controlPanel: {} };
    }

    get data() {
        return this.state.data;
    }

    get periodLabel() {
        return this.periods.find((p) => p.key === this.state.period).label;
    }

    get sections() {
        const data = this.data;
        if (!data) {
            return [];
        }
        return dashboardSections
            .getEntries()
            .map(([key, section]) => ({ key, ...section }))
            .filter((section) => data.sections[section.dataKey])
            .sort((a, b) => a.sequence - b.sequence);
    }

    get helpers() {
        return {
            formatMoney: (value) => this.formatMoney(value),
            formatNumber: (value, digits = 0) => this.formatNumber(value, digits),
            open: (params) => this.open(params),
        };
    }

    get stepMax() {
        return Math.max(1, ...this.data.steps.map((s) => s.count));
    }

    get serviceMax() {
        return Math.max(1, ...(this.data.services || []).map((s) => s.amount));
    }

    get trendChart() {
        const trend = this.data.trend || [];
        return {
            labels: trend.map((t) => t.label),
            values: trend.map((t) => t.amount),
            total: trend.reduce((sum, t) => sum + t.amount, 0),
        };
    }

    async load() {
        this.state.data = await this.keepLast.add(
            this.orm.call("ki.laundry.dashboard", "get_data", [this.state.period])
        );
    }

    setPeriod(period) {
        if (this.state.period !== period) {
            this.state.period = period;
            this.load();
        }
    }

    formatMoney(value) {
        return formatMonetary(value || 0, {
            currencyId: this.data.currency.id,
            digits: [false, 0],
        });
    }

    formatNumber(value, digits = 0) {
        return formatFloat(value || 0, { digits: [false, digits] });
    }

    formatKpi(kpi) {
        return kpi.money ? this.formatMoney(kpi.value) : this.formatNumber(kpi.value);
    }

    /** "14:30" for today, "Mon 14:30" otherwise. */
    formatDue(value) {
        const due = deserializeDateTime(value);
        const time = due.toLocaleString(DateTime.TIME_SIMPLE);
        return due.hasSame(DateTime.local(), "day") ? time : `${due.toFormat("ccc")} ${time}`;
    }

    stateClass(order) {
        if (order.is_late) {
            return "text-bg-danger";
        }
        return order.state === "ready" ? "text-bg-success" : "text-bg-warning";
    }

    /** Open the records behind a figure, a bar or a row. */
    open({ model, domain, name }) {
        const views = ["ki.laundry.order", "ki.laundry.order.item"].includes(model)
            ? [[false, "list"], [false, "kanban"], [false, "form"]]
            : [[false, "list"], [false, "form"]];
        this.action.doAction({
            type: "ir.actions.act_window",
            name: name || _t("Laundry"),
            res_model: model,
            domain,
            views,
            context: { create: false },
        });
    }

    openDue() {
        this.open({ model: "ki.laundry.order", domain: this.data.due.domain, name: _t("Due Today") });
    }

    openOrder(orderId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "ki.laundry.order",
            res_id: orderId,
            views: [[false, "form"]],
        });
    }

    newOrder() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "ki.laundry.order",
            views: [[false, "form"]],
        });
    }
}

registry.category("actions").add("ki_laundry_dashboard", LaundryDashboard);
