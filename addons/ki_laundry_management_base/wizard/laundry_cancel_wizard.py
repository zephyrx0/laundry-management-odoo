# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
#  Kalvyai | Laundry Management - Base
#  Copyright (c) 2026-Present Kalvyai (https://kalvyai.com)
#  License: OPL-1. See the LICENSE file.
# ----------------------------------------------------------------------------
from odoo import api, fields, models


class LaundryCancelWizard(models.TransientModel):
    _name = 'ki.laundry.cancel.wizard'
    _description = "Cancel or Stop Laundry Order"

    order_id = fields.Many2one('ki.laundry.order', required=True, ondelete='cascade')
    currency_id = fields.Many2one(related='order_id.currency_id')
    mode = fields.Selection([('cancel', "Cancel"), ('stop', "Stop & Return")], compute='_compute_mode')
    reason = fields.Text(required=True)
    charge_policy = fields.Selection(
        [('none', "No charge"), ('partial', "Charge a fee"), ('full', "Charge in full")],
        default='partial', required=True)
    fee = fields.Monetary(string="Fee", currency_field='currency_id',
                          help="Amount (taxes included) charged to the customer.")
    amount_total = fields.Monetary(related='order_id.amount_total', string="Current Total")

    @api.depends('order_id.state')
    def _compute_mode(self):
        for wizard in self:
            wizard.mode = 'stop' if wizard.order_id.in_custody else 'cancel'

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        order = self.env['ki.laundry.order'].browse(values.get('order_id'))
        if order and 'fee' in fields_list:
            started = order.item_ids.filtered(
                lambda i: i.state in ('ready', 'damaged') or i.route_ids.filtered(lambda r: r.state == 'done'))
            values['fee'] = sum(started.mapped('price_total'))
        return values

    def action_confirm(self):
        self.ensure_one()
        if self.mode == 'cancel':
            self.order_id._ki_cancel(self.reason)
        else:
            self.order_id._ki_stop_and_return(self.reason, self.charge_policy, self.fee)
        return True
