# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
#  Kalvyai | Laundry Management - Base
#  Copyright (c) 2026-Present Kalvyai (https://kalvyai.com)
#  License: OPL-1. See the LICENSE file.
# ----------------------------------------------------------------------------
from odoo import fields, models


class ProductPricelistItem(models.Model):
    _inherit = 'product.pricelist.item'

    ki_laundry_offer_id = fields.Many2one(
        'ki.laundry.offer', string="Laundry Offer",
        index='btree_not_null', ondelete='cascade', copy=False, readonly=True,
    )
