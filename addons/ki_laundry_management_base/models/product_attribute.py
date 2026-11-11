# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
#  Kalvyai | Laundry Management - Base
#  Copyright (c) 2026-Present Kalvyai (https://kalvyai.com)
#  License: OPL-1. See the LICENSE file.
# ----------------------------------------------------------------------------
from odoo import api, fields, models
from odoo.exceptions import UserError


class ProductAttribute(models.Model):
    _inherit = 'product.attribute'

    ki_laundry_is_garment = fields.Boolean(
        string="Laundry Garment Attribute",
        copy=False,
        readonly=True,
        help="Technical flag marking the single attribute whose values are the laundry garments.",
    )

    _ki_laundry_unique_garment_attribute = models.UniqueIndex(
        '(ki_laundry_is_garment) WHERE (ki_laundry_is_garment IS TRUE)',
        "Only one product attribute can be the laundry garment attribute.",
    )

    @api.model
    def _ki_laundry_get_garment_attribute(self, create=True):
        """Return the garment attribute, recreating it if it was removed."""
        attribute = self.sudo().with_context(active_test=False).search(
            [('ki_laundry_is_garment', '=', True)], limit=1,
        )
        if not attribute and create:
            attribute = self.sudo().create({
                'name': self.env._("Garment"),
                'create_variant': 'always',
                'display_type': 'radio',
                'ki_laundry_is_garment': True,
            })
        elif attribute and not attribute.active:
            attribute.active = True
        return attribute

    def write(self, vals):
        if 'create_variant' in vals and vals['create_variant'] != 'always' \
                and any(attr.ki_laundry_is_garment for attr in self):
            raise UserError(self.env._(
                "The laundry Garment attribute must always create variants."
            ))
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_except_ki_laundry_garment(self):
        if any(attr.ki_laundry_is_garment for attr in self):
            raise UserError(self.env._(
                "The laundry Garment attribute cannot be deleted. Archive or delete the garments instead."
            ))
