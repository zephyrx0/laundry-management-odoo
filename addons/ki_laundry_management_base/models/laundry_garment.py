# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
#  Kalvyai | Laundry Management - Base
#  Copyright (c) 2026-Present Kalvyai (https://kalvyai.com)
#  License: OPL-1. See the LICENSE file.
# ----------------------------------------------------------------------------
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class LaundryGarment(models.Model):
    _name = 'ki.laundry.garment'
    _description = "Laundry Garment"
    _inherit = ['image.mixin']
    _order = 'sequence, id'

    attribute_value_id = fields.Many2one(
        'product.attribute.value', string="Attribute Value",
        required=True, ondelete='restrict', index=True, copy=False,
    )
    name = fields.Char(related='attribute_value_id.name', readonly=False, required=True)
    sequence = fields.Integer(related='attribute_value_id.sequence', readonly=False, store=True)
    code = fields.Char(string="Tag Code", size=8, help="Short code printed on garment tags, e.g. SHT.")
    category_id = fields.Many2one('ki.laundry.garment.category', string="Category", index=True)
    tag_mode = fields.Selection(
        [('per_piece', "One tag per piece"), ('per_line', "One tag per intake line")],
        string="Tagging", default='per_piece', required=True,
        help="Use 'One tag per intake line' for small items such as socks or handkerchiefs.",
    )
    parts_count = fields.Integer(
        string="Parts", default=1, required=True,
        help="Number of physical parts in one piece, e.g. 3 for a 3-piece suit.",
    )
    active = fields.Boolean(default=True)
    color = fields.Integer()
    service_count = fields.Integer(compute='_compute_service_count')

    _attribute_value_uniq = models.Constraint(
        'unique(attribute_value_id)', "This attribute value is already linked to a garment.")
    _parts_count_positive = models.Constraint(
        'CHECK(parts_count >= 1)', "A garment has at least one part.")

    @api.constrains('attribute_value_id')
    def _check_attribute_value_id(self):
        for garment in self:
            if not garment.attribute_value_id.attribute_id.ki_laundry_is_garment:
                raise ValidationError(self.env._(
                    "Garment %s must use a value of the laundry Garment attribute.", garment.name))

    def _compute_service_count(self):
        counts = dict(self.env['product.product']._read_group(
            [('ki_laundry_garment_id', 'in', self.ids), ('product_tmpl_id.ki_laundry_is_service', '=', True)],
            ['ki_laundry_garment_id'], ['__count']))
        for garment in self:
            garment.service_count = counts.get(garment, 0)

    @api.model_create_multi
    def create(self, vals_list):
        attribute = self.env['product.attribute']._ki_laundry_get_garment_attribute()
        Value = self.env['product.attribute.value'].sudo()
        for vals in vals_list:
            if vals.get('attribute_value_id'):
                continue
            name = vals.pop('name', False)
            if not name:
                raise UserError(self.env._("A garment needs a name."))
            existing = Value.search([('attribute_id', '=', attribute.id), ('name', '=ilike', name)], limit=1)
            if existing and not self.with_context(active_test=False).search_count(
                    [('attribute_value_id', '=', existing.id)]):
                vals['attribute_value_id'] = existing.id
            else:
                value_vals = {'attribute_id': attribute.id, 'name': name}
                if 'sequence' in vals:
                    value_vals['sequence'] = vals['sequence']
                vals['attribute_value_id'] = Value.create(value_vals).id
        garments = super().create(vals_list)
        # Variants created before the garment record must point to it.
        products = self.env['product.product'].sudo().with_context(active_test=False).search(
            [('product_template_attribute_value_ids.product_attribute_value_id', 'in',
              garments.attribute_value_id.ids)])
        if products:
            self.env.add_to_compute(products._fields['ki_laundry_garment_id'], products)
        return garments

    @api.ondelete(at_uninstall=False)
    def _unlink_except_used(self):
        if self.env['ki.laundry.order.intake'].sudo().search_count([('garment_id', 'in', self.ids)], limit=1):
            raise UserError(self.env._(
                "Garments used on laundry orders cannot be deleted. Archive them instead."))

    def unlink(self):
        values = self.attribute_value_id
        result = super().unlink()
        # Removes the value from the Garment attribute; Odoo refuses if it is still used on services.
        values.sudo().unlink()
        return result

    @api.model
    def _ki_demo_set_prices(self, prices):
        """Demo data helper: ``prices`` is a list of (service template id, garment id, price)."""
        Template = self.env['product.template']
        for service_id, garment_id, price in prices:
            Template.browse(service_id)._ki_laundry_set_garment_price(self.browse(garment_id), price)

    def action_open_price_grid(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'ki_laundry_price_grid',
            'name': self.env._("Prices"),
            'context': {'ki_search': self.name},
        }

    def action_open_services(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._("Services for %s", self.name),
            'res_model': 'product.product',
            'view_mode': 'list,form',
            'domain': [('ki_laundry_garment_id', '=', self.id)],
        }
