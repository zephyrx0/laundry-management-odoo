# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
#  Kalvyai | Laundry Management - Base
#  Copyright (c) 2026-Present Kalvyai (https://kalvyai.com)
#  License: OPL-1. See the LICENSE file.
# ----------------------------------------------------------------------------
from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError

from ..models.laundry_order_item import OPEN_STATES


class LaundryIntakeSplitWizard(models.TransientModel):
    _name = 'ki.laundry.intake.split.wizard'
    _description = "Split Laundry Intake Line"

    intake_id = fields.Many2one('ki.laundry.order.intake', required=True, ondelete='cascade')
    order_id = fields.Many2one(related='intake_id.order_id')
    is_received = fields.Boolean(compute='_compute_is_received')
    quantity = fields.Integer(string="Pieces to Split", default=1)
    item_ids = fields.Many2many(
        'ki.laundry.order.item', string="Items to Split",
        domain="[('intake_id', '=', intake_id), ('state', 'in', ('pending', 'in_process', 'rework', 'ready'))]")
    service_ids = fields.Many2many(
        'product.template', string="Services for the Split Pieces",
        domain="[('ki_laundry_is_service', '=', True), ('ki_laundry_pricing_mode', '=', 'piece')]")

    @api.depends('intake_id')
    def _compute_is_received(self):
        for wizard in self:
            wizard.is_received = bool(wizard.intake_id.item_ids)

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        intake = self.env['ki.laundry.order.intake'].browse(values.get('intake_id'))
        if intake:
            values.setdefault('service_ids', [(6, 0, intake.service_ids.ids)])
        return values

    def action_split(self):
        self.ensure_one()
        intake = self.intake_id
        order = intake.order_id
        if intake.pricing_mode != 'piece':
            raise UserError(self.env._("Only per-piece lines can be split. Use the weigh action for loads."))
        if not self.service_ids:
            raise UserError(self.env._("Select the services of the split pieces."))
        if order.garments_editable:
            if not 0 < self.quantity < intake.quantity:
                raise UserError(self.env._("Split between 1 and %s pieces.", intake.quantity - 1))
            intake.copy({'quantity': self.quantity, 'service_ids': [(6, 0, self.service_ids.ids)],
                         'sequence': intake.sequence + 1})
            intake.quantity -= self.quantity
            return True

        if not order.in_custody:
            raise UserError(self.env._("The garments of %s cannot be changed in this state.", order.name))
        items = self.item_ids
        if not items:
            raise UserError(self.env._("Select the items to split."))
        if items.filtered(lambda i: i.intake_id != intake or i.state not in OPEN_STATES + ('ready',)):
            raise UserError(self.env._("Only items of this line that are not delivered can be split."))
        if intake.garment_id.tag_mode == 'per_line':
            raise UserError(self.env._("Pieces sharing a single tag cannot be split."))
        removed = intake.service_ids - self.service_ids
        if removed and not order._ki_is_manager():
            raise AccessError(self.env._("Only laundry managers can remove services after reception."))
        if len(items) == len(intake.item_ids.filtered(lambda i: i.state not in ('cancelled', 'lost'))):
            # Every piece moves: simply change the services of the line.
            target = intake
            intake.with_context(ki_laundry_system=True).service_ids = [(6, 0, self.service_ids.ids)]
        else:
            target = intake.with_context(ki_laundry_system=True).copy({
                'quantity': len(items),
                'service_ids': [(6, 0, self.service_ids.ids)],
                'sequence': intake.sequence + 1,
            })
            intake.with_context(ki_laundry_system=True).quantity = intake.quantity - len(items)
            items.sudo().write({'intake_id': target.id, 'line_ids': [(6, 0, target.line_ids.ids)]})
        self._ki_update_routes(items, target)
        order._ki_update_state_from_items()
        order.message_post(body=self.env._(
            "%(count)s item(s) of %(line)s now get: %(services)s",
            count=len(items), line=intake._ki_label(), services=", ".join(self.service_ids.mapped('name'))))
        return True

    def _ki_update_routes(self, items, intake):
        steps = intake._ki_route_steps()
        Route = self.env['ki.laundry.order.item.route'].sudo()
        for item in items:
            item.route_ids.filtered(lambda r: r.state == 'pending' and r.step_id not in steps).unlink()
            missing = steps - item.route_ids.step_id
            if missing:
                Route.create([{'item_id': item.id, 'step_id': s.id, 'sequence': s.sequence} for s in missing])
                if item.state == 'ready':
                    item.sudo().write({'state': 'in_process', 'date_ready': False})
            elif item.state in OPEN_STATES and not item.route_ids.filtered(lambda r: r.state == 'pending'):
                item._ki_set_ready()
