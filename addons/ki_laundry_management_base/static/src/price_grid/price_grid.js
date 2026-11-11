/* ----------------------------------------------------------------------------
 *  Kalvyai | Laundry Management - Base
 *  Copyright (c) 2026-Present Kalvyai (https://kalvyai.com)
 *  License: OPL-1. See the LICENSE file.
 * ---------------------------------------------------------------------------- */
import { Component, onWillStart, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Layout } from "@web/search/layout";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";

/**
 * Prices screen. Pick a garment on the left, then switch on the services offered for it
 * and type their price. Per-kg services and add-ons have a single price each.
 */
export class LaundryPriceGrid extends Component {
    static template = "ki_laundry_management_base.PriceGrid";
    static components = { Layout };
    static props = { ...standardActionServiceProps };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.action = useService("action");
        this.state = useState({
            loaded: false,
            garments: [],
            categories: [],
            pieceServices: [],
            kgServices: [],
            addons: [],
            currency: { symbol: "", position: "after", digits: 2 },
            search: this.props.action?.context?.ki_search || "",
            categoryId: false,
            selected: false, // "g<id>", "kg" or "addons"
            saving: {},
            saved: {},
            newGarment: "",
        });
        onWillStart(() => this.load());
    }

    get display() {
        return { controlPanel: {} };
    }

    async load() {
        const data = await this.orm.call("product.template", "ki_laundry_price_grid_data", []);
        Object.assign(this.state, {
            loaded: true,
            garments: data.garments,
            categories: data.categories,
            pieceServices: data.piece_services,
            kgServices: data.kg_services,
            addons: data.addons,
            currency: data.currency,
        });
        if (!this.isValidSelection(this.state.selected)) {
            const first = this.filteredGarments[0] || this.state.garments[0];
            this.state.selected = first
                ? `g${first.id}`
                : this.state.kgServices.length
                ? "kg"
                : this.state.addons.length
                ? "addons"
                : false;
        }
    }

    isValidSelection(key) {
        if (key === "kg") {
            return this.state.kgServices.length > 0;
        }
        if (key === "addons") {
            return this.state.addons.length > 0;
        }
        return Boolean(key) && this.state.garments.some((g) => `g${g.id}` === key);
    }

    // ------------------------------------------------------------------
    // Getters
    // ------------------------------------------------------------------

    get filteredGarments() {
        const search = this.state.search.trim().toLowerCase();
        return this.state.garments.filter(
            (g) =>
                (!this.state.categoryId || g.category_id === this.state.categoryId) &&
                (!search ||
                    g.name.toLowerCase().includes(search) ||
                    g.code.toLowerCase().includes(search) ||
                    g.category.toLowerCase().includes(search))
        );
    }

    get garment() {
        return this.state.garments.find((g) => `g${g.id}` === this.state.selected);
    }

    get hasServices() {
        return Boolean(
            this.state.pieceServices.length || this.state.kgServices.length || this.state.addons.length
        );
    }

    offeredCount(garment) {
        return this.state.pieceServices.filter((s) => this.priceOf(s, garment) !== null).length;
    }

    countClass(garment) {
        const count = this.offeredCount(garment);
        if (!count) {
            return "text-bg-warning";
        }
        return count === this.state.pieceServices.length ? "text-bg-success" : "text-bg-light";
    }

    initials(name) {
        const words = (name || "").match(/\p{L}+/gu) || ["?"];
        return words
            .slice(0, 2)
            .map((word) => word[0])
            .join("")
            .toUpperCase();
    }

    priceOf(service, garment) {
        const price = service.prices[garment.id];
        return price === undefined ? null : price;
    }

    /** Price proposed when a service is switched on: the usual price of the other garments. */
    defaultPrice(service) {
        const prices = Object.values(service.prices)
            .filter((price) => price !== null)
            .sort((a, b) => a - b);
        return prices.length ? prices[Math.floor(prices.length / 2)] : service.base_price || 0;
    }

    displayPrice(value) {
        if (value === null || value === undefined) {
            return "";
        }
        return Number(value).toFixed(this.state.currency.digits);
    }

    key(serviceId, garmentId) {
        return `${serviceId}-${garmentId || 0}`;
    }

    // ------------------------------------------------------------------
    // Saving
    // ------------------------------------------------------------------

    async save(serviceId, garmentId, price) {
        const key = this.key(serviceId, garmentId);
        this.state.saving[key] = true;
        try {
            return await this.orm.call("product.template", "ki_laundry_price_grid_set", [
                serviceId,
                garmentId || false,
                price,
            ]);
        } finally {
            delete this.state.saving[key];
        }
    }

    flashSaved(serviceId, garmentId) {
        const key = this.key(serviceId, garmentId);
        this.state.saved[key] = true;
        setTimeout(() => delete this.state.saved[key], 1500);
    }

    /** Read a price from an input; ``undefined`` when it is not a valid number. */
    parsePrice(input) {
        const raw = input.value.trim().replace(",", ".");
        const price = Number(raw);
        if (raw === "" || Number.isNaN(price) || price < 0) {
            this.notification.add(_t("Type a price, for example 25 or 12.50."), { type: "warning" });
            return undefined;
        }
        return price;
    }

    async toggleService(service, garment, ev) {
        const on = ev.target.checked;
        try {
            const result = await this.save(service.id, garment.id, on ? this.defaultPrice(service) : null);
            if (service.all_garments) {
                // The service now has its own price per garment: reload every garment.
                await this.load();
            } else {
                service.prices[garment.id] = on ? result ?? 0 : null;
            }
            this.flashSaved(service.id, garment.id);
        } catch (error) {
            ev.target.checked = !on;
            throw error;
        }
    }

    async onPiecePriceChange(service, garment, ev) {
        const previous = this.priceOf(service, garment);
        const price = this.parsePrice(ev.target);
        if (price === undefined) {
            ev.target.value = this.displayPrice(previous);
            return;
        }
        if (previous !== null && Math.abs(price - previous) < 1e-6) {
            ev.target.value = this.displayPrice(previous);
            return;
        }
        try {
            const result = await this.save(service.id, garment.id, price);
            if (service.all_garments) {
                await this.load();
            } else {
                service.prices[garment.id] = result;
                ev.target.value = this.displayPrice(result);
            }
            this.flashSaved(service.id, garment.id);
        } catch (error) {
            ev.target.value = this.displayPrice(previous);
            throw error;
        }
    }

    async onSinglePriceChange(record, ev) {
        const price = this.parsePrice(ev.target);
        if (price === undefined || Math.abs(price - record.price) < 1e-6) {
            ev.target.value = this.displayPrice(record.price);
            return;
        }
        try {
            record.price = await this.save(record.id, false, price);
            ev.target.value = this.displayPrice(record.price);
            this.flashSaved(record.id, false);
        } catch (error) {
            ev.target.value = this.displayPrice(record.price);
            throw error;
        }
    }

    /** Price typed in a row: per garment (piece services) or single (per kg / add-on). */
    onPriceChange(ev, record, garment) {
        return garment ? this.onPiecePriceChange(record, garment, ev) : this.onSinglePriceChange(record, ev);
    }

    onPriceKeydown(ev) {
        if (ev.key === "Enter") {
            ev.target.blur();
        }
    }

    // ------------------------------------------------------------------
    // Navigation / records
    // ------------------------------------------------------------------

    select(key) {
        this.state.selected = key;
    }

    onSearch(ev) {
        this.state.search = ev.target.value;
    }

    setCategory(categoryId) {
        this.state.categoryId = categoryId;
    }

    async onNewGarmentKeydown(ev) {
        if (ev.key === "Enter") {
            await this.addGarment();
        }
    }

    async addGarment() {
        const name = this.state.newGarment.trim();
        if (!name) {
            return;
        }
        const [garmentId] = await this.orm.create("ki.laundry.garment", [
            { name, category_id: this.state.categoryId || false },
        ]);
        this.state.newGarment = "";
        this.state.search = "";
        this.state.selected = `g${garmentId}`;
        await this.load();
    }

    editGarment(garment) {
        this.action.doAction(
            {
                type: "ir.actions.act_window",
                res_model: "ki.laundry.garment",
                res_id: garment.id,
                views: [[false, "form"]],
                target: "new",
            },
            { onClose: () => this.load() }
        );
    }

    openService(serviceId) {
        this.action.doAction(
            {
                type: "ir.actions.act_window",
                res_model: "product.template",
                res_id: serviceId,
                views: [[false, "form"]],
                target: "new",
            },
            { onClose: () => this.load() }
        );
    }

    newService() {
        this.action.doAction(
            {
                type: "ir.actions.act_window",
                name: _t("New Service"),
                res_model: "product.template",
                views: [[false, "form"]],
                target: "new",
                context: {
                    default_ki_laundry_is_service: true,
                    default_type: "service",
                    default_sale_ok: true,
                    default_purchase_ok: false,
                },
            },
            { onClose: () => this.load() }
        );
    }
}

registry.category("actions").add("ki_laundry_price_grid", LaundryPriceGrid);
