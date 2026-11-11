# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
#  Kalvyai | Laundry Management - Base
#  Copyright (c) 2026-Present Kalvyai (https://kalvyai.com)
#  License: OPL-1. See the LICENSE file.
# ----------------------------------------------------------------------------
from odoo import api, fields, models
from odoo.exceptions import UserError


class LaundryWeighWizard(models.TransientModel):
    _name = 'ki.laundry.weigh.wizard'
    _description = "Weigh Laundry Load"

    intake_id = fields.Many2one('ki.laundry.order.intake', required=True, ondelete='cascade')
    weight_estimated = fields.Float(related='intake_id.weight_estimated', string="Estimated Weight (kg)")
    weight_actual = fields.Float(string="Actual Weight (kg)", digits='Stock Weight', required=True)
    bag_count = fields.Integer(string="Bags", default=1)
    can_change_bags = fields.Boolean(compute='_compute_can_change_bags')

    @api.depends('intake_id')
    def _compute_can_change_bags(self):
        for wizard in self:
            wizard.can_change_bags = not wizard.intake_id.item_ids

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        intake = self.env['ki.laundry.order.intake'].browse(values.get('intake_id'))
        if intake:
            values.setdefault('weight_actual', intake.weight_actual or intake.weight_estimated)
            # Not setdefault: the field default (1) is already in values and would win.
            if 'bag_count' in fields_list:
                values['bag_count'] = intake.bag_count or 1
        return values

    def action_confirm(self):
        self.ensure_one()
        intake = self.intake_id
        order = intake.order_id
        if intake.pricing_mode != 'kg':
            raise UserError(self.env._("Only per-kg loads can be weighed."))
        if self.weight_actual <= 0:
            raise UserError(self.env._("The weight must be positive."))
        if self.bag_count < 1:
            raise UserError(self.env._("A load has at least one bag."))
        if order.garments_editable:
            intake.write({'weight_actual': self.weight_actual, 'bag_count': self.bag_count})
            return True
        if order.state != 'received' or intake.item_ids.route_ids.filtered(lambda r: r.state != 'pending'):
            raise UserError(self.env._("The load is already being processed; its weight is final."))
        if self.bag_count != len(intake.item_ids):
            raise UserError(self.env._("The number of bags cannot change once tags are printed."))
        intake.with_context(ki_laundry_system=True).write({'weight_actual': self.weight_actual})
        intake.item_ids.sudo().write({'weight': self.weight_actual / len(intake.item_ids)})
        order._ki_sync_charge_lines()
        return True
