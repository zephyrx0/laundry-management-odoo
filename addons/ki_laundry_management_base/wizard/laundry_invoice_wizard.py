# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
#  Kalvyai | Laundry Management - Base
#  Copyright (c) 2026-Present Kalvyai (https://kalvyai.com)
#  License: OPL-1. See the LICENSE file.
# ----------------------------------------------------------------------------
from odoo import api, fields, models
from odoo.exceptions import UserError


class LaundryInvoiceWizard(models.TransientModel):
    _name = 'ki.laundry.invoice.wizard'
    _description = "Create Laundry Invoice"

    order_ids = fields.Many2many('ki.laundry.order', string="Orders", required=True)
    order_count = fields.Integer(compute='_compute_order_count')
    invoice_mode = fields.Selection(
        [('regular', "Regular invoice"), ('advance', "Advance payment")], default='regular', required=True)
    consolidate = fields.Boolean(string="One invoice per customer")
    advance_method = fields.Selection(
        [('percent', "Percentage"), ('fixed', "Fixed amount")], default='percent', required=True)
    advance_percent = fields.Float(string="Advance (%)")
    advance_fixed = fields.Monetary(string="Advance Amount", currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', compute='_compute_order_count')

    @api.depends('order_ids')
    def _compute_order_count(self):
        for wizard in self:
            wizard.order_count = len(wizard.order_ids)
            wizard.currency_id = wizard.order_ids[:1].currency_id or self.env.company.currency_id

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        if self.env.context.get('active_model') == 'ki.laundry.order' and self.env.context.get('active_ids'):
            values['order_ids'] = [(6, 0, self.env.context['active_ids'])]
        values.setdefault('advance_percent', self.env.company.ki_laundry_advance_percent)
        return values

    def action_create_invoices(self):
        self.ensure_one()
        orders = self.order_ids
        if self.invoice_mode == 'advance':
            if len(orders) != 1:
                raise UserError(self.env._("Advances are invoiced one order at a time."))
            amount = self.advance_fixed if self.advance_method == 'fixed' \
                else orders.amount_total * self.advance_percent / 100.0
            moves = orders._ki_create_invoices(advance_amount=orders.currency_id.round(amount))
        else:
            moves = orders._ki_create_invoices(consolidate=self.consolidate)
        if not self.env.user.has_group('account.group_account_invoice'):
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'success',
                    'message': self.env._("Invoice(s) created: %s", ", ".join(moves.mapped('display_name'))),
                    'next': {'type': 'ir.actions.act_window_close'},
                },
            }
        action = self.env['ir.actions.act_window']._for_xml_id('account.action_move_out_invoice_type')
        if len(moves) == 1:
            action['views'] = [(self.env.ref('account.view_move_form').id, 'form')]
            action['res_id'] = moves.id
        else:
            action['domain'] = [('id', 'in', moves.ids)]
        return action
