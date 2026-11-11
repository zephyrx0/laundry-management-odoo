# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
#  Kalvyai | Laundry Management - Base
#  Copyright (c) 2026-Present Kalvyai (https://kalvyai.com)
#  License: OPL-1. See the LICENSE file.
# ----------------------------------------------------------------------------
from odoo import fields, models


class LaundryItemLog(models.Model):
    _name = 'ki.laundry.item.log'
    _description = "Laundry Item History"
    _order = 'date desc, id desc'

    item_id = fields.Many2one('ki.laundry.order.item', required=True, ondelete='cascade', index=True)
    order_id = fields.Many2one(related='item_id.order_id', store=True, index=True)
    company_id = fields.Many2one(related='item_id.company_id', store=True, index=True)
    action = fields.Selection([
        ('advance', "Step Done"),
        ('skip', "Step Skipped"),
        ('rework', "Rework"),
        ('ready', "Ready"),
        ('deliver', "Delivered"),
        ('damage', "Damaged"),
        ('lost', "Lost"),
        ('found', "Found"),
    ], required=True)
    step_from_id = fields.Many2one('ki.laundry.process.step', string="Step")
    step_to_id = fields.Many2one('ki.laundry.process.step', string="Next Step")
    state_from = fields.Char()
    state_to = fields.Char()
    user_id = fields.Many2one('res.users', string="User", default=lambda self: self.env.user)
    date = fields.Datetime(default=fields.Datetime.now, required=True)
    note = fields.Text()
