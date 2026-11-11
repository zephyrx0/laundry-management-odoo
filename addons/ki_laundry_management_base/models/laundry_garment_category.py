# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
#  Kalvyai | Laundry Management - Base
#  Copyright (c) 2026-Present Kalvyai (https://kalvyai.com)
#  License: OPL-1. See the LICENSE file.
# ----------------------------------------------------------------------------
from odoo import api, fields, models


class LaundryGarmentCategory(models.Model):
    _name = 'ki.laundry.garment.category'
    _description = "Laundry Garment Category"
    _order = 'sequence, name, id'

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    garment_ids = fields.One2many('ki.laundry.garment', 'category_id', string="Garments")
    garment_count = fields.Integer(compute='_compute_garment_count')

    @api.depends('garment_ids')
    def _compute_garment_count(self):
        counts = dict(self.env['ki.laundry.garment']._read_group(
            [('category_id', 'in', self.ids)], ['category_id'], ['__count']))
        for category in self:
            category.garment_count = counts.get(category, 0)
