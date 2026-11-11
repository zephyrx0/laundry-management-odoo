# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
#  Kalvyai | Laundry Management - Base
#  Copyright (c) 2026-Present Kalvyai (https://kalvyai.com)
#  License: OPL-1. See the LICENSE file.
# ----------------------------------------------------------------------------
from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    ki_laundry_order_ids = fields.Many2many(
        'ki.laundry.order', string="Laundry Orders", compute='_compute_ki_laundry_order_ids', compute_sudo=True)
    ki_laundry_order_count = fields.Integer(compute='_compute_ki_laundry_order_ids', compute_sudo=True)

    @api.depends('line_ids.ki_laundry_line_ids')
    def _compute_ki_laundry_order_ids(self):
        for move in self:
            orders = move.line_ids.ki_laundry_line_ids.order_id
            move.ki_laundry_order_ids = orders
            move.ki_laundry_order_count = len(orders)

    def action_view_ki_laundry_orders(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('ki_laundry_management_base.action_laundry_order')
        orders = self.ki_laundry_order_ids
        if len(orders) == 1:
            action['views'] = [(False, 'form')]
            action['res_id'] = orders.id
        else:
            action['domain'] = [('id', 'in', orders.ids)]
        return action

    def _ki_laundry_release_orders(self, orders):
        """Orders whose invoices are all gone / cancelled can be paid through another channel again."""
        for order in orders.sudo():
            if order.financial_path == 'invoice' and not order.invoice_ids.filtered(lambda m: m.state != 'cancel'):
                order.financial_path = False

    def button_cancel(self):
        orders = self.sudo().line_ids.ki_laundry_line_ids.order_id
        result = super().button_cancel()
        self._ki_laundry_release_orders(orders)
        return result

    def unlink(self):
        orders = self.sudo().line_ids.ki_laundry_line_ids.order_id
        result = super().unlink()
        self._ki_laundry_release_orders(orders.exists())
        return result
