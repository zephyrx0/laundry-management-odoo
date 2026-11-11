# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
#  Kalvyai | Laundry Management - Base
#  Copyright (c) 2026-Present Kalvyai (https://kalvyai.com)
#  License: OPL-1. See the LICENSE file.
# ----------------------------------------------------------------------------
from odoo import api, fields, models


class LaundryReworkWizard(models.TransientModel):
    _name = 'ki.laundry.rework.wizard'
    _description = "Send Laundry Items to Rework"

    item_ids = fields.Many2many('ki.laundry.order.item', string="Items", required=True)
    available_step_ids = fields.Many2many('ki.laundry.process.step', compute='_compute_available_step_ids')
    step_id = fields.Many2one('ki.laundry.process.step', string="Restart From",
                              domain="[('id', 'in', available_step_ids)]")
    note = fields.Text(string="Reason")

    @api.depends('item_ids')
    def _compute_available_step_ids(self):
        for wizard in self:
            steps = wizard.item_ids[:1].route_ids.step_id
            for item in wizard.item_ids[1:]:
                steps &= item.route_ids.step_id
            wizard.available_step_ids = steps

    def action_confirm(self):
        self.ensure_one()
        self.item_ids.action_rework(step=self.step_id or None, note=self.note)
        return True
