# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
#  Kalvyai | Laundry Management - Base
#  Copyright (c) 2026-Present Kalvyai (https://kalvyai.com)
#  License: OPL-1. See the LICENSE file.
# ----------------------------------------------------------------------------
from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.fields import Command


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    ki_laundry_is_service = fields.Boolean(
        string="Laundry Service", index=True,
        help="Use this product as a laundry service (Wash, Dry Clean, Iron...). "
             "Garments are managed as variants of the service.",
    )
    ki_laundry_is_addon = fields.Boolean(
        string="Laundry Add-on", index=True,
        help="Extra option that can be added on laundry intake lines (starch, fragrance...).",
    )
    ki_laundry_pricing_mode = fields.Selection(
        [('piece', "Per Piece"), ('kg', "Per Kg")],
        string="Pricing Mode", default='piece', required=True,
    )
    ki_laundry_step_ids = fields.Many2many(
        'ki.laundry.process.step', 'ki_laundry_service_step_rel', 'product_tmpl_id', 'step_id',
        string="Process Steps",
        help="Steps a garment goes through for this service. The final order of steps "
             "comes from each step's sequence, so several services can be combined.",
    )
    ki_laundry_tat_hours = fields.Float(string="Turnaround (Hours)", default=48.0)
    ki_laundry_urgent_tat_hours = fields.Float(string="Urgent Turnaround (Hours)", default=24.0)
    ki_laundry_urgent_surcharge_type = fields.Selection(
        [('percent', "Percentage"), ('fixed', "Fixed per Unit")],
        string="Urgent Surcharge Type", default='percent', required=True,
    )
    ki_laundry_urgent_surcharge = fields.Float(string="Urgent Surcharge", default=50.0)
    ki_laundry_min_qty = fields.Float(
        string="Minimum Billed Quantity",
        help="Minimum quantity billed for this service on an intake line (e.g. 3 kg).",
    )
    ki_laundry_is_package = fields.Boolean(
        string="Package Service",
        help="Combined service (e.g. Wash + Dry + Iron) sold at its own price.",
    )
    ki_laundry_sequence = fields.Integer(string="Laundry Sequence", default=10)
    ki_laundry_color = fields.Integer(string="Laundry Color")
    ki_laundry_garment_count = fields.Integer(
        string="Garments", compute='_compute_ki_laundry_garment_count',
    )

    @api.depends('ki_laundry_is_service', 'attribute_line_ids.value_ids')
    def _compute_ki_laundry_garment_count(self):
        for template in self:
            line = template._ki_laundry_garment_line()
            template.ki_laundry_garment_count = len(line.value_ids) if line else 0

    @api.onchange('ki_laundry_is_service', 'ki_laundry_is_addon')
    def _onchange_ki_laundry_is_service(self):
        if self.ki_laundry_is_service or self.ki_laundry_is_addon:
            self.type = 'service'
            self.sale_ok = True
        if self.ki_laundry_is_service:
            self.ki_laundry_is_addon = False

    @api.onchange('ki_laundry_pricing_mode')
    def _onchange_ki_laundry_pricing_mode(self):
        if self.ki_laundry_is_service and self.ki_laundry_pricing_mode == 'kg':
            kg = self.env.ref('uom.product_uom_kgm', raise_if_not_found=False)
            if kg:
                self.uom_id = kg

    @api.model_create_multi
    def create(self, vals_list):
        # The unit field is hidden unless "Units of Measure" is enabled, so the onchange
        # above cannot set it: a per-kg service without an explicit unit is sold by kg.
        kg = self.env.ref('uom.product_uom_kgm', raise_if_not_found=False)
        if kg:
            for vals in vals_list:
                if (vals.get('ki_laundry_is_service') or self.env.context.get('default_ki_laundry_is_service')) \
                        and vals.get('ki_laundry_pricing_mode') == 'kg' and not vals.get('uom_id'):
                    vals['uom_id'] = kg.id
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('ki_laundry_pricing_mode') == 'kg' and not vals.get('uom_id'):
            kg = self.env.ref('uom.product_uom_kgm', raise_if_not_found=False)
            to_kg = kg and self.filtered(
                lambda t: (vals.get('ki_laundry_is_service', t.ki_laundry_is_service))
                and not (t.uom_id and t.uom_id._has_common_reference(kg)))
            if to_kg:
                super(ProductTemplate, to_kg).write(dict(vals, uom_id=kg.id))
                return super(ProductTemplate, self - to_kg).write(vals)
        return super().write(vals)

    @api.constrains('ki_laundry_is_service', 'ki_laundry_is_addon', 'type', 'ki_laundry_pricing_mode',
                    'uom_id', 'attribute_line_ids')
    def _check_ki_laundry_service(self):
        kg = self.env.ref('uom.product_uom_kgm', raise_if_not_found=False)
        for template in self:
            if template.ki_laundry_is_service and template.ki_laundry_is_addon:
                raise ValidationError(self.env._(
                    "%s cannot be both a laundry service and a laundry add-on.", template.display_name))
            if not (template.ki_laundry_is_service or template.ki_laundry_is_addon):
                continue
            if template.type != 'service':
                raise ValidationError(self.env._(
                    "Laundry service/add-on %s must be of type Service.", template.display_name))
            if not template.ki_laundry_is_service:
                continue
            variant_lines = template.attribute_line_ids.filtered(
                lambda l: l.attribute_id.create_variant != 'no_variant')
            if variant_lines.filtered(lambda l: not l.attribute_id.ki_laundry_is_garment):
                raise ValidationError(self.env._(
                    "Laundry service %s can only use the Garment attribute to create variants.",
                    template.display_name))
            if template.ki_laundry_pricing_mode == 'kg':
                if kg and template.uom_id and not template.uom_id._has_common_reference(kg):
                    raise ValidationError(self.env._(
                        "Per-kg laundry service %s must use a weight unit of measure.",
                        template.display_name))
                if variant_lines:
                    raise ValidationError(self.env._(
                        "Per-kg laundry service %s cannot have garment variants.", template.display_name))

    @api.constrains('ki_laundry_tat_hours', 'ki_laundry_urgent_tat_hours', 'ki_laundry_urgent_surcharge',
                    'ki_laundry_min_qty')
    def _check_ki_laundry_values(self):
        for template in self.filtered('ki_laundry_is_service'):
            if min(template.ki_laundry_tat_hours, template.ki_laundry_urgent_tat_hours,
                   template.ki_laundry_urgent_surcharge, template.ki_laundry_min_qty) < 0:
                raise ValidationError(self.env._(
                    "Turnaround times, surcharge and minimum quantity cannot be negative (%s).",
                    template.display_name))

    # ------------------------------------------------------------------
    # Garment helpers
    # ------------------------------------------------------------------

    def _ki_laundry_garment_line(self):
        self.ensure_one()
        return self.attribute_line_ids.filtered(lambda l: l.attribute_id.ki_laundry_is_garment)[:1]

    def _ki_laundry_get_variant(self, garment=None):
        """Return the variant to bill for this service and garment.

        A service without the Garment attribute is generic and applies to any garment.
        Returns an empty recordset when the garment is not enabled on the service.
        """
        self.ensure_one()
        variants = self.product_variant_ids
        if not self._ki_laundry_garment_line():
            return variants[:1]
        if not garment:
            return self.env['product.product']
        return variants.filtered(lambda p: p.ki_laundry_garment_id == garment)[:1]

    def _ki_laundry_set_garment_price(self, garment, price):
        """Enable the garment on this service at ``price`` (sales price, company currency),
        or disable it when ``price`` is ``None``."""
        self.ensure_one()
        if not self.ki_laundry_is_service or self.ki_laundry_pricing_mode != 'piece':
            raise UserError(self.env._("Garment prices only apply to per-piece laundry services."))
        attribute = self.env['product.attribute']._ki_laundry_get_garment_attribute()
        value = garment.attribute_value_id
        line = self._ki_laundry_garment_line()
        if price is None:
            if line and value in line.value_ids:
                if len(line.value_ids) == 1:
                    raise UserError(self.env._(
                        "%(service)s must keep at least one garment. To offer it for every garment at "
                        "one price, remove the Garment attribute from the service.",
                        service=self.display_name))
                line.value_ids = [Command.unlink(value.id)]
            return
        if price < 0:
            raise UserError(self.env._("A laundry price cannot be negative."))
        if not line:
            self.attribute_line_ids = [Command.create({
                'attribute_id': attribute.id,
                'value_ids': [Command.set(value.ids)],
            })]
            line = self._ki_laundry_garment_line()
        elif value not in line.value_ids:
            line.value_ids = [Command.link(value.id)]
        ptav = line.product_template_value_ids.filtered(
            lambda v: v.product_attribute_value_id == value)
        ptav.price_extra = price - self.list_price

    # ------------------------------------------------------------------
    # Price grid API (used by the OWL client action)
    # ------------------------------------------------------------------

    def _ki_laundry_check_manager(self):
        if not self.env.user.has_group('ki_laundry_management_base.group_laundry_manager'):
            raise AccessError(self.env._("Only laundry managers can edit laundry prices."))

    @api.model
    def ki_laundry_price_grid_data(self):
        """Everything the Prices screen needs: garments, per-piece services with a price per
        garment (``None`` = not offered), per-kg services and add-ons with their single price."""
        self._ki_laundry_check_manager()
        garments = self.env['ki.laundry.garment'].search([])
        services = self.search([('ki_laundry_is_service', '=', True)], order='ki_laundry_sequence, name, id')
        addons = self.search([('ki_laundry_is_addon', '=', True)], order='ki_laundry_sequence, name, id')
        currency = self.env.company.currency_id

        def base_price(template):
            return template.list_price

        piece_services = []
        for service in services.filtered(lambda s: s.ki_laundry_pricing_mode == 'piece'):
            # Without the Garment attribute, the service applies to any garment at its base price.
            all_garments = not service._ki_laundry_garment_line()
            prices = {}
            for garment in garments:
                if all_garments:
                    prices[garment.id] = base_price(service)
                else:
                    variant = service._ki_laundry_get_variant(garment)
                    prices[garment.id] = variant.lst_price if variant else None
            piece_services.append({
                'id': service.id,
                'name': service.name,
                'all_garments': all_garments,
                'base_price': base_price(service),
                'prices': prices,
            })
        def single(templates):
            return [{'id': t.id, 'name': t.name, 'price': base_price(t), 'uom': t.uom_id.name} for t in templates]

        categories = garments.category_id
        return {
            'garments': [{
                'id': g.id,
                'name': g.name,
                'code': g.code or '',
                'category_id': g.category_id.id,
                'category': g.category_id.name or '',
            } for g in garments],
            'categories': [{'id': c.id, 'name': c.name} for c in categories.sorted(lambda c: (c.sequence, c.name))],
            'piece_services': piece_services,
            'kg_services': single(services.filtered(lambda s: s.ki_laundry_pricing_mode == 'kg')),
            'addons': single(addons),
            'currency': {'id': currency.id, 'symbol': currency.symbol, 'position': currency.position,
                         'digits': currency.decimal_places},
        }

    @api.model
    def ki_laundry_price_grid_set(self, service_id, garment_id, price):
        """Set the price of a service for a garment, or stop offering it with ``price=None``.

        Without ``garment_id``, set the single price of a per-kg service or an add-on. A per-piece
        service offered to every garment at one price keeps every other garment at that price
        when one garment gets its own price (or is removed).
        """
        self._ki_laundry_check_manager()
        service = self.browse(service_id).exists()
        if not service or not (service.ki_laundry_is_service or service.ki_laundry_is_addon):
            raise UserError(self.env._("This laundry service no longer exists."))
        if price is not None:
            price = float(price)
            if price < 0:
                raise UserError(self.env._("A laundry price cannot be negative."))
        if not garment_id:
            if service.ki_laundry_is_service and service.ki_laundry_pricing_mode == 'piece' \
                    and service._ki_laundry_garment_line():
                raise UserError(self.env._("Set the price of %s for each garment.", service.name))
            if price is None:
                raise UserError(self.env._("%s needs a price.", service.name))
            service.list_price = price
            return service.product_variant_ids[:1].lst_price
        garment = self.env['ki.laundry.garment'].browse(garment_id).exists()
        if not garment:
            raise UserError(self.env._("This garment no longer exists."))
        if not service._ki_laundry_garment_line():
            others = self.env['ki.laundry.garment'].search([('id', '!=', garment.id)])
            if price is None and not others:
                raise UserError(self.env._(
                    "%s must be offered for at least one garment. Archive the service to stop selling it.",
                    service.name))
            for other in others:
                service._ki_laundry_set_garment_price(other, service.list_price)
            if price is None:
                return None
        service._ki_laundry_set_garment_price(garment, price)
        variant = service._ki_laundry_get_variant(garment)
        return variant.lst_price if price is not None and variant else None

    def action_ki_laundry_open_variants(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('product.product_variant_action')
        action['domain'] = [('product_tmpl_id', '=', self.id)]
        action['context'] = {'default_product_tmpl_id': self.id}
        return action
