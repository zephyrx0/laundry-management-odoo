# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
#  Kalvyai | Laundry Management - Base
#  Copyright (c) 2026-Present Kalvyai (https://kalvyai.com)
#  License: OPL-1. See the LICENSE file.
# ----------------------------------------------------------------------------
from odoo import api, fields, models


class ProductProduct(models.Model):
    _inherit = 'product.product'

    ki_laundry_garment_id = fields.Many2one(
        'ki.laundry.garment', string="Laundry Garment",
        compute='_compute_ki_laundry_garment_id', store=True, index='btree_not_null',
    )

    @api.depends('product_template_attribute_value_ids.product_attribute_value_id')
    def _compute_ki_laundry_garment_id(self):
        values = self.product_template_attribute_value_ids.product_attribute_value_id
        garments = self.env['ki.laundry.garment'].sudo().with_context(active_test=False).search(
            [('attribute_value_id', 'in', values.ids)]) if values else self.env['ki.laundry.garment']
        garment_by_value = {garment.attribute_value_id.id: garment.id for garment in garments}
        for product in self:
            garment_id = False
            for value in product.product_template_attribute_value_ids.product_attribute_value_id:
                if value.id in garment_by_value:
                    garment_id = garment_by_value[value.id]
                    break
            product.ki_laundry_garment_id = garment_id
