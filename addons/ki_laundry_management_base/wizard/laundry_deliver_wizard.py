# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
#  Kalvyai | Laundry Management - Base
#  Copyright (c) 2026-Present Kalvyai (https://kalvyai.com)
#  License: OPL-1. See the LICENSE file.
# ----------------------------------------------------------------------------
import re

from odoo import api, fields, models
from odoo.exceptions import UserError


class LaundryDeliverWizard(models.TransientModel):
    _name = 'ki.laundry.deliver.wizard'
    _description = "Deliver Laundry Garments"

    order_id = fields.Many2one('ki.laundry.order', required=True, ondelete='cascade')
    currency_id = fields.Many2one(related='order_id.currency_id')
    item_ids = fields.Many2many(
        'ki.laundry.order.item', string="Items to Deliver",
        domain="[('order_id', '=', order_id), ('state', 'in', ('ready', 'damaged'))]")
    pending_item_count = fields.Integer(compute='_compute_info')
    amount_due = fields.Monetary(compute='_compute_info', currency_field='currency_id')
    require_scan = fields.Boolean(compute='_compute_info')
    scanned_barcodes = fields.Text(string="Scanned Tags", help="Scan every delivered tag, one per line.")
    confirm_unpaid = fields.Boolean(string="Deliver with an amount still due")

    @api.depends('order_id')
    def _compute_info(self):
        for wizard in self:
            order = wizard.order_id
            wizard.pending_item_count = len(order.item_ids.filtered(
                lambda i: i.state in ('pending', 'in_process', 'rework')))
            wizard.amount_due = order.amount_due
            wizard.require_scan = order.company_id.ki_laundry_require_scan_on_delivery

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        order = self.env['ki.laundry.order'].browse(values.get('order_id'))
        if order:
            values['item_ids'] = [(6, 0, order.item_ids.filtered(lambda i: i.state in ('ready', 'damaged')).ids)]
        return values

    def action_deliver(self):
        self.ensure_one()
        order = self.order_id
        if order.state not in order._ki_deliverable_states():
            raise UserError(self.env._("Order %s has nothing ready to deliver.", order.name))
        items = self.item_ids
        if not items:
            raise UserError(self.env._("Select the items handed over to the customer."))
        if items.filtered(lambda i: i.order_id != order):
            raise UserError(self.env._("All items must belong to order %s.", order.name))
        if self.require_scan:
            scanned = {code.strip() for code in re.split(r'[\s,;]+', self.scanned_barcodes or '') if code.strip()}
            missing = items.filtered(lambda i: i.barcode not in scanned)
            if missing:
                raise UserError(self.env._(
                    "These tags were not scanned: %s", ", ".join(missing.mapped('barcode'))))
        unpaid = order.currency_id.compare_amounts(order.amount_due, 0.0) > 0 \
            and order.payment_policy != 'credit' and not order._ki_paid_elsewhere()
        if unpaid and not self.confirm_unpaid:
            raise UserError(self.env._(
                "%(amount)s is still due on %(order)s. Collect the payment or tick 'Deliver with an amount "
                "still due'.", amount=order.amount_due, order=order.name))
        items._ki_deliver()
        if unpaid:
            order.message_post(body=self.env._("Delivered with %s still due.", order.amount_due))
        return True
