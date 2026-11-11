# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
#  Kalvyai | Laundry Management - Base
#  Copyright (c) 2026-Present Kalvyai (https://kalvyai.com)
#  License: OPL-1. See the LICENSE file.
# ----------------------------------------------------------------------------
from odoo import fields, models


class LaundryOrderItemRoute(models.Model):
    _name = 'ki.laundry.order.item.route'
    _description = "Laundry Item Route Step"
    _order = 'item_id, sequence, id'

    item_id = fields.Many2one('ki.laundry.order.item', required=True, ondelete='cascade', index=True)
    step_id = fields.Many2one('ki.laundry.process.step', required=True, ondelete='restrict', index=True)
    sequence = fields.Integer()
    state = fields.Selection([('pending', "Pending"), ('done', "Done"), ('skipped', "Skipped")],
                             default='pending', required=True)
    user_id = fields.Many2one('res.users', string="Done By")
    date_done = fields.Datetime()
    company_id = fields.Many2one(related='item_id.company_id', store=True, index=True)

    _item_step_uniq = models.Constraint('unique(item_id, step_id)', "A step appears only once on an item route.")
