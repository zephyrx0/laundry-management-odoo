# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
#  Kalvyai | Laundry Management - Base
#  Copyright (c) 2026-Present Kalvyai (https://kalvyai.com)
#  License: OPL-1. See the LICENSE file.
# ----------------------------------------------------------------------------
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare


SYNC_FIELDS = {'pricing_mode', 'garment_id', 'quantity', 'weight_estimated', 'weight_actual',
               'service_ids', 'addon_product_ids'}


class LaundryOrderIntake(models.Model):
    _name = 'ki.laundry.order.intake'
    _description = "Laundry Intake Line"
    _order = 'order_id, sequence, id'
    _check_company_auto = True

    order_id = fields.Many2one('ki.laundry.order', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one(related='order_id.company_id', store=True, index=True)
    currency_id = fields.Many2one(related='order_id.currency_id')
    state = fields.Selection(related='order_id.state')
    pricing_mode = fields.Selection(
        [('piece', "Per Piece"), ('kg', "Per Kg")], default='piece', required=True)
    garment_id = fields.Many2one('ki.laundry.garment', string="Garment", index=True, ondelete='restrict')
    quantity = fields.Integer(string="Pieces", default=1)
    weight_estimated = fields.Float(string="Estimated Weight (kg)", digits='Stock Weight')
    weight_actual = fields.Float(string="Actual Weight (kg)", digits='Stock Weight')
    bag_count = fields.Integer(string="Bags", default=1, help="Number of tags for a per-kg load.")
    service_ids = fields.Many2many(
        'product.template', 'ki_laundry_intake_service_rel', 'intake_id', 'product_tmpl_id',
        string="Services", check_company=True,
        domain="[('ki_laundry_is_service', '=', True), ('ki_laundry_pricing_mode', '=', pricing_mode)]")
    addon_product_ids = fields.Many2many(
        'product.product', 'ki_laundry_intake_addon_rel', 'intake_id', 'product_id',
        string="Add-ons", check_company=True, domain="[('ki_laundry_is_addon', '=', True)]")
    note = fields.Text(string="Description", help="Brand, colour, special instructions.")
    damage_note = fields.Text(string="Condition at Intake")
    attachment_ids = fields.Many2many(
        'ir.attachment', 'ki_laundry_intake_attachment_rel', 'intake_id', 'attachment_id', string="Photos")
    line_ids = fields.One2many('ki.laundry.order.line', 'intake_id', string="Billing Lines", copy=False)
    item_ids = fields.One2many('ki.laundry.order.item', 'intake_id', string="Items", copy=False)
    price_unit_total = fields.Monetary(
        string="Price / Unit", compute='_compute_amounts', currency_field='currency_id')
    amount_total = fields.Monetary(string="Total", compute='_compute_amounts', currency_field='currency_id')

    _quantity_positive = models.Constraint('CHECK(quantity >= 0)', "The number of pieces cannot be negative.")
    _weights_positive = models.Constraint(
        'CHECK(weight_estimated >= 0 AND weight_actual >= 0)', "Weights cannot be negative.")
    _bag_count_positive = models.Constraint('CHECK(bag_count >= 1)', "A load has at least one bag.")

    @api.depends('line_ids.price_total', 'line_ids.product_uom_qty')
    def _compute_amounts(self):
        for intake in self:
            intake.amount_total = sum(intake.line_ids.mapped('price_total'))
            intake.price_unit_total = sum(
                line.price_total / line.product_uom_qty for line in intake.line_ids if line.product_uom_qty)

    @api.constrains('pricing_mode', 'service_ids')
    def _check_services_mode(self):
        for intake in self:
            wrong = intake.service_ids.filtered(
                lambda s: not s.ki_laundry_is_service or s.ki_laundry_pricing_mode != intake.pricing_mode)
            if wrong:
                raise ValidationError(self.env._(
                    "Services %(services)s cannot be used on a %(mode)s line. Per-piece and per-kg services "
                    "must be on separate lines.",
                    services=", ".join(wrong.mapped('display_name')),
                    mode=dict(self._fields['pricing_mode'].selection)[intake.pricing_mode]))

    @api.onchange('pricing_mode')
    def _onchange_pricing_mode(self):
        self.service_ids = self.service_ids.filtered(lambda s: s.ki_laundry_pricing_mode == self.pricing_mode)
        if self.pricing_mode == 'kg':
            self.garment_id = False

    # ------------------------------------------------------------------
    # Labels
    # ------------------------------------------------------------------

    def _ki_label(self):
        self.ensure_one()
        if self.pricing_mode == 'kg':
            return self.env._("Load (kg)") if not self.garment_id else self.garment_id.name
        return self.garment_id.name or ''

    def _ki_display_quantity(self):
        self.ensure_one()
        if self.pricing_mode == 'kg':
            weight = self.weight_actual or self.weight_estimated
            return self.env._("%(weight)s kg%(est)s", weight=round(weight, 3),
                              est='' if self.weight_actual else self.env._(" (est.)"))
        return str(self.quantity)

    def _compute_display_name(self):
        for intake in self:
            services = ", ".join(intake.service_ids.mapped('name'))
            intake.display_name = "%s x %s [%s]" % (intake._ki_label(), intake._ki_display_quantity(), services)

    # ------------------------------------------------------------------
    # ORM
    # ------------------------------------------------------------------

    def _ki_check_editable(self):
        if self.env.context.get('ki_laundry_system'):
            return
        for intake in self:
            if not intake.order_id.garments_editable:
                raise UserError(self.env._(
                    "Garments of order %s were already received. Use the split / weigh actions instead.",
                    intake.order_id.name))

    @api.model_create_multi
    def create(self, vals_list):
        intakes = super().create(vals_list)
        intakes._ki_check_editable()
        intakes._ki_sync_lines()
        intakes.order_id._ki_sync_charge_lines()
        return intakes

    def write(self, vals):
        if SYNC_FIELDS & set(vals):
            self._ki_check_editable()
        result = super().write(vals)
        if SYNC_FIELDS & set(vals):
            self._ki_sync_lines()
            self.order_id._ki_sync_charge_lines()
        return result

    def unlink(self):
        self._ki_check_editable()
        orders = self.order_id
        if self.line_ids.filtered('qty_invoiced'):
            raise UserError(self.env._("Invoiced intake lines cannot be removed. Issue a credit note first."))
        self.line_ids.with_context(ki_laundry_system=True).unlink()
        result = super().unlink()
        orders._ki_sync_charge_lines()
        return result

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _ki_check_valid(self, final=False):
        """Validate intake lines before confirmation (``final``: before receiving the garments)."""
        for intake in self:
            label = intake._ki_label() or self.env._("line %s", intake.sequence)
            if not intake.service_ids:
                raise UserError(self.env._("Select at least one service for %s.", label))
            if intake.pricing_mode == 'piece':
                if not intake.garment_id:
                    raise UserError(self.env._("Select the garment of every per-piece line."))
                if intake.quantity <= 0:
                    raise UserError(self.env._("Set the number of pieces for %s.", label))
                for service in intake.service_ids:
                    if not service._ki_laundry_get_variant(intake.garment_id):
                        raise UserError(self.env._(
                            "Service %(service)s is not offered for %(garment)s. Set a price for it in "
                            "Configuration > Prices.", service=service.name, garment=intake.garment_id.name))
            else:
                if final and intake.weight_actual <= 0:
                    raise UserError(self.env._(
                        "Weigh the load '%s' before receiving the order.", label))
                if not final and intake.weight_actual <= 0 and intake.weight_estimated <= 0:
                    raise UserError(self.env._("Set the (estimated) weight of the load '%s'.", label))

    # ------------------------------------------------------------------
    # Billing lines
    # ------------------------------------------------------------------

    def _ki_billable_qty(self, service=None):
        self.ensure_one()
        if self.pricing_mode == 'kg':
            qty = self.weight_actual or self.weight_estimated
        else:
            qty = float(self.quantity)
        if service and service.ki_laundry_min_qty and qty:
            qty = max(qty, service.ki_laundry_min_qty)
        return qty

    def _ki_sync_lines(self):
        """Create, update or remove the billing lines generated by the intake lines."""
        Line = self.env['ki.laundry.order.line'].with_context(ki_laundry_system=True)
        for intake in self:
            wanted = {}
            for service in intake.service_ids:
                variant = service._ki_laundry_get_variant(intake.garment_id)
                if not variant:
                    if intake.pricing_mode == 'piece' and not intake.garment_id:
                        continue  # incomplete line, validated at reception
                    raise UserError(self.env._(
                        "Service %(service)s is not offered for %(garment)s. Set a price for it in "
                        "Configuration > Prices.", service=service.name, garment=intake.garment_id.name or '-'))
                wanted[variant] = ('service', intake._ki_billable_qty(service))
            for addon in intake.addon_product_ids:
                wanted.setdefault(addon, ('addon', intake._ki_billable_qty()))
            to_remove = Line
            for line in intake.line_ids:
                if line.product_id not in wanted:
                    to_remove |= line
                    continue
                line_type, qty = wanted.pop(line.product_id)
                if float_compare(line.product_uom_qty, qty,
                                 precision_rounding=line.product_uom_id.rounding or 0.001):
                    line.with_context(ki_laundry_system=True).write({'product_uom_qty': qty})
                    line._ki_recompute_price()
            if to_remove.filtered('qty_invoiced'):
                raise UserError(self.env._(
                    "Invoiced services cannot be removed from %s. Issue a credit note first.", intake._ki_label()))
            to_remove.with_context(ki_laundry_system=True).unlink()
            new_lines = Line.create([{
                'order_id': intake.order_id.id,
                'intake_id': intake.id,
                'line_type': line_type,
                'product_id': product.id,
                'product_uom_qty': qty,
                'sequence': intake.sequence,
            } for product, (line_type, qty) in wanted.items()])
            new_lines._ki_recompute_price()
            # Items follow the services of their intake line.
            if intake.item_ids:
                intake.item_ids.write({'line_ids': [(6, 0, intake.line_ids.ids)]})

    # ------------------------------------------------------------------
    # Items / tags
    # ------------------------------------------------------------------

    def _ki_route_steps(self):
        self.ensure_one()
        steps = self.service_ids.ki_laundry_step_ids.filtered('active')
        return steps.sorted(lambda s: (s.sequence, s.id))

    def _ki_generate_items(self):
        """Create one item (tag) per physical piece, set or bag. Idempotent."""
        Item = self.env['ki.laundry.order.item'].with_context(ki_laundry_system=True)
        for intake in self:
            if intake.item_ids:
                continue
            order = intake.order_id
            if not order.barcode:
                order.sudo().barcode = order._ki_new_barcode()
            if intake.pricing_mode == 'kg':
                count = max(intake.bag_count, 1)
                weight = (intake.weight_actual or intake.weight_estimated) / count
                specs = [{'item_type': 'bag', 'weight': weight, 'piece_count': 0} for _i in range(count)]
            elif intake.garment_id.tag_mode == 'per_line':
                specs = [{'item_type': 'piece', 'piece_count': intake.quantity}]
            else:
                item_type = 'set' if intake.garment_id.parts_count > 1 else 'piece'
                specs = [{'item_type': item_type, 'piece_count': 1} for _i in range(intake.quantity)]
            start = len(order.item_ids)
            vals_list = []
            for index, spec in enumerate(specs, start=start + 1):
                vals_list.append(dict(
                    spec,
                    order_id=order.id,
                    intake_id=intake.id,
                    sequence_number=index,
                    barcode="%s-%03d" % (order.barcode, index),
                    garment_id=intake.garment_id.id,
                    parts_count=intake.garment_id.parts_count or 1,
                    description=intake.note,
                    has_damage=bool(intake.damage_note),
                    line_ids=[(6, 0, intake.line_ids.ids)],
                ))
            items = Item.create(vals_list)
            items._ki_build_route(intake._ki_route_steps())

    # ------------------------------------------------------------------
    # Wizards
    # ------------------------------------------------------------------

    def action_open_split_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._("Split / Change Services"),
            'res_model': 'ki.laundry.intake.split.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_intake_id': self.id},
        }

    def action_open_weigh_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._("Weigh Load"),
            'res_model': 'ki.laundry.weigh.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_intake_id': self.id},
        }
