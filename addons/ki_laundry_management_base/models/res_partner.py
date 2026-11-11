# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
#  Kalvyai | Laundry Management - Base
#  Copyright (c) 2026-Present Kalvyai (https://kalvyai.com)
#  License: OPL-1. See the LICENSE file.
# ----------------------------------------------------------------------------
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    ki_laundry_order_ids = fields.One2many('ki.laundry.order', 'partner_id', string="Laundry Orders")
    ki_laundry_order_count = fields.Integer(
        string="Laundry Order Count", compute='_compute_ki_laundry_order_count',
        groups='ki_laundry_management_base.group_laundry_worker')
    ki_laundry_preference = fields.Text(
        string="Laundry Preferences", help="Shown when creating a laundry order, e.g. 'no starch, fold shirts'.")

    def _compute_ki_laundry_order_count(self):
        all_partners = self.with_context(active_test=False).search_fetch(
            [('id', 'child_of', self.ids)], ['parent_id'])
        counts = self.env['ki.laundry.order']._read_group(
            [('partner_id', 'in', all_partners.ids)], ['partner_id'], ['__count'])
        self.ki_laundry_order_count = 0
        self_ids = set(self._ids)
        for partner, count in counts:
            while partner:
                if partner.id in self_ids:
                    partner.ki_laundry_order_count += count
                partner = partner.parent_id

    def action_view_ki_laundry_orders(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('ki_laundry_management_base.action_laundry_order')
        action['domain'] = [('partner_id', 'child_of', self.ids)]
        action['context'] = {'default_partner_id': self.id}
        return action
