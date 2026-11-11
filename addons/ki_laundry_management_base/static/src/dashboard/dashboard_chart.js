/* ----------------------------------------------------------------------------
 *  Kalvyai | Laundry Management - Base
 *  Copyright (c) 2026-Present Kalvyai (https://kalvyai.com)
 *  License: OPL-1. See the LICENSE file.
 * ---------------------------------------------------------------------------- */
import { Component, onWillStart, onWillUnmount, useEffect, useRef } from "@odoo/owl";
import { loadBundle } from "@web/core/assets";
import { cookie } from "@web/core/browser/cookie";
import { getColor, getCustomColor } from "@web/core/colors/colors";

/**
 * Single-series Chart.js chart styled like Odoo's graph view.
 */
export class LaundryDashboardChart extends Component {
    static template = "ki_laundry_management_base.DashboardChart";
    static props = {
        type: { type: String, validate: (t) => ["bar", "line"].includes(t) },
        labels: Array,
        values: Array,
        seriesLabel: String,
        horizontal: { type: Boolean, optional: true },
        integer: { type: Boolean, optional: true },
        formatValue: { type: Function, optional: true },
        onPointClick: { type: Function, optional: true },
        height: { type: Number, optional: true },
    };
    static defaultProps = { height: 260 };

    setup() {
        this.canvasRef = useRef("canvas");
        this.chart = null;
        onWillStart(() => loadBundle("web.chartjs_lib"));
        useEffect(
            () => this.renderChart(),
            () => [this.props.labels, this.props.values, this.props.type]
        );
        onWillUnmount(() => this.chart?.destroy());
    }

    renderChart() {
        this.chart?.destroy();
        const scheme = cookie.get("color_scheme");
        const color = getColor(0, scheme);
        const gridColor = getCustomColor(scheme, "rgba(0,0,0,.1)", "rgba(255,255,255,.15)");
        const labelColor = getCustomColor(scheme, "#111827", "#E4E4E4");
        const format = this.props.formatValue || ((v) => v);
        const isLine = this.props.type === "line";
        const valueAxis = this.props.horizontal ? "x" : "y";
        const categoryAxis = this.props.horizontal ? "y" : "x";
        this.chart = new Chart(this.canvasRef.el, {
            type: this.props.type,
            data: {
                labels: this.props.labels,
                datasets: [
                    {
                        label: this.props.seriesLabel,
                        data: this.props.values,
                        backgroundColor: isLine ? color + "33" : color,
                        borderColor: color,
                        borderWidth: 2,
                        borderRadius: isLine ? 0 : 4,
                        fill: isLine ? "origin" : false,
                        tension: 0.25,
                        pointRadius: isLine ? 3 : 0,
                        pointHoverRadius: 5,
                        maxBarThickness: 32,
                    },
                ],
            },
            options: {
                indexAxis: this.props.horizontal ? "y" : "x",
                maintainAspectRatio: false,
                interaction: { mode: "index", intersect: false },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => `${this.props.seriesLabel}: ${format(ctx.raw)}`,
                        },
                    },
                },
                scales: {
                    [valueAxis]: {
                        beginAtZero: true,
                        grid: { color: gridColor },
                        border: { display: false },
                        ticks: {
                            color: labelColor,
                            callback: (v) => format(v),
                            maxTicksLimit: 6,
                            precision: this.props.integer ? 0 : undefined,
                        },
                    },
                    [categoryAxis]: {
                        grid: { display: false },
                        ticks: { color: labelColor, autoSkip: true, maxRotation: 0 },
                    },
                },
                onClick: (ev, elements) => {
                    if (elements.length && this.props.onPointClick) {
                        this.props.onPointClick(elements[0].index);
                    }
                },
                onHover: (ev, elements) => {
                    ev.native.target.style.cursor =
                        elements.length && this.props.onPointClick ? "pointer" : "default";
                },
            },
        });
    }
}
