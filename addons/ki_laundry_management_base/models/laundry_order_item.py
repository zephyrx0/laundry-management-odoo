# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
#  Kalvyai | Laundry Management - Base
#  Copyright (c) 2026-Present Kalvyai (https://kalvyai.com)
#  License: OPL-1. See the LICENSE file.
# ----------------------------------------------------------------------------
from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError


ITEM_STATES = [
    ('pending', "Pending"),
    ('in_process', "In Process"),
    ('rework', "Rework"),
    ('ready', "Ready"),
    ('delivered', "Delivered"),
    ('damaged', "Damaged"),
    ('lost', "Lost"),
    ('cancelled', "Cancelled"),
]
OPEN_STATES = ('pending', 'in_process', 'rework')


class LaundryOrderItem(models.Model):
    _name = 'ki.laundry.order.item'
    _description = "Laundry Item (Tag)"
    _inherit = ['mail.thread']
    _order = 'order_id desc, sequence_number, id'
    _rec_name = 'barcode'
    _check_company_auto = True

    barcode = fields.Char(required=True, readonly=True, copy=False, index=True)
    name = fields.Char(compute='_compute_name')
    order_id = fields.Many2one('ki.laundry.order', required=True, ondelete='cascade', index=True, readonly=True)
    intake_id = fields.Many2one('ki.laundry.order.intake', required=True, ondelete='cascade', index=True,
                                readonly=True)
    sequence_number = fields.Integer(readonly=True)
    partner_id = fields.Many2one(related='order_id.partner_id', store=True, index=True)
    company_id = fields.Many2one(related='order_id.company_id', store=True, index=True)
    currency_id = fields.Many2one(related='order_id.currency_id')
    date_due = fields.Datetime(related='order_id.date_due', store=True)
    is_urgent = fields.Boolean(related='order_id.is_urgent', store=True)
    item_type = fields.Selection([('piece', "Piece"), ('set', "Set"), ('bag', "Bag")], required=True,
                                 default='piece', readonly=True)
    garment_id = fields.Many2one('ki.laundry.garment', readonly=True, index='btree_not_null')
    parts_count = fields.Integer(default=1)
    piece_count = fields.Integer(string="Pieces", default=1, help="Pieces sharing this tag.")
    weight = fields.Float(digits='Stock Weight')
    line_ids = fields.Many2many('ki.laundry.order.line', 'ki_laundry_item_line_rel', 'item_id', 'line_id',
                                string="Services", readonly=True)
    route_ids = fields.One2many('ki.laundry.order.item.route', 'item_id', string="Route")
    current_step_id = fields.Many2one('ki.laundry.process.step', compute='_compute_current_step', store=True,
                                      index=True, string="Current Step")
    progress = fields.Float(compute='_compute_current_step', store=True, aggregator='avg')
    state = fields.Selection(ITEM_STATES, default='pending', required=True, readonly=True, index=True,
                             tracking=True, copy=False)
    rack_location = fields.Char(string="Rack / Location", tracking=True)
    description = fields.Text(help="Colour, brand or marks to identify the garment.")
    has_damage = fields.Boolean(string="Pre-existing Damage", tracking=True)
    damage_note = fields.Text(related='intake_id.damage_note')
    attachment_ids = fields.Many2many('ir.attachment', 'ki_laundry_item_attachment_rel', 'item_id',
                                      'attachment_id', string="Photos")
    price_total = fields.Monetary(compute='_compute_price_total', currency_field='currency_id',
                                  help="Share of the service lines charged for this item.")
    date_ready = fields.Datetime(readonly=True, copy=False)
    date_delivered = fields.Datetime(readonly=True, copy=False)
    delivered_by_id = fields.Many2one('res.users', readonly=True, copy=False)
    log_ids = fields.One2many('ki.laundry.item.log', 'item_id', string="History", readonly=True)

    _barcode_uniq = models.Constraint('unique(barcode)', "The item barcode must be unique.")

    @api.depends('garment_id', 'sequence_number', 'item_type', 'order_id.item_ids')
    def _compute_name(self):
        for item in self:
            total = len(item.order_id.item_ids)
            if item.item_type == 'bag':
                label = self.env._("Bag")
            else:
                label = item.garment_id.name or self.env._("Item")
            item.name = "%s %s/%s" % (label, item.sequence_number, total)

    @api.depends('route_ids.state', 'route_ids.sequence')
    def _compute_current_step(self):
        for item in self:
            route = item.route_ids.sorted(lambda r: (r.sequence, r.id))
            pending = route.filtered(lambda r: r.state == 'pending')
            item.current_step_id = pending[:1].step_id
            item.progress = 100.0 * (len(route) - len(pending)) / len(route) if route else 0.0

    @api.depends('line_ids.price_total', 'line_ids.item_ids', 'weight', 'piece_count')
    def _compute_price_total(self):
        for item in self:
            total = 0.0
            for line in item.line_ids:
                siblings = line.item_ids
                if not siblings:
                    continue
                if item.item_type == 'bag':
                    weights = sum(siblings.mapped('weight'))
                    share = item.weight / weights if weights else 1.0 / len(siblings)
                else:
                    pieces = sum(siblings.mapped('piece_count'))
                    share = item.piece_count / pieces if pieces else 1.0 / len(siblings)
                total += line.price_total * share
            item.price_total = total

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get('ki_laundry_system'):
            raise UserError(self.env._("Items are created automatically when the order is received."))
        return super().create(vals_list)

    @api.ondelete(at_uninstall=False)
    def _unlink_except_system(self):
        if not self.env.context.get('ki_laundry_system') and not self.env.context.get('ki_laundry_order_unlink'):
            for item in self:
                if item.order_id.state not in ('draft', 'cancelled'):
                    raise UserError(self.env._("Items of a received order cannot be deleted. Mark them lost."))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _ki_is_manager(self):
        return self.env.su or self.env.user.has_group('ki_laundry_management_base.group_laundry_manager')

    def _ki_build_route(self, steps):
        Route = self.env['ki.laundry.order.item.route']
        for item in self:
            Route.create([{'item_id': item.id, 'step_id': step.id, 'sequence': step.sequence} for step in steps])

    def _ki_log(self, action, step_from=None, step_to=None, state_from=None, note=None):
        self.env['ki.laundry.item.log'].sudo().create([{
            'item_id': item.id,
            'action': action,
            'step_from_id': step_from.id if step_from else False,
            'step_to_id': step_to.id if step_to else False,
            'state_from': state_from,
            'state_to': item.state,
            'user_id': self.env.user.id,
            'note': note,
        } for item in self])

    def _ki_check_processable(self):
        for item in self:
            if not item.order_id.in_custody:
                raise UserError(self.env._(
                    "Item %(item)s cannot be processed: order %(order)s is %(state)s.",
                    item=item.barcode, order=item.order_id.name,
                    state=dict(item.order_id._fields['state'].selection)[item.order_id.state]))
            if item.order_id.is_stopped:
                raise UserError(self.env._("Order %s was stopped.", item.order_id.name))

    def _ki_set_ready(self, note=None):
        now = fields.Datetime.now()
        for item in self:
            state_from = item.state
            item.sudo().write({'state': 'ready', 'date_ready': now})
            item._ki_log('ready', state_from=state_from, note=note)

    def _ki_force_ready(self, note=None):
        """Skip every remaining step and mark the items ready (used when stopping an order)."""
        now = fields.Datetime.now()
        for item in self:
            item.route_ids.filtered(lambda r: r.state == 'pending').sudo().write(
                {'state': 'skipped', 'user_id': self.env.user.id, 'date_done': now})
        self._ki_set_ready(note)

    # ------------------------------------------------------------------
    # Actions (workstation / backend)
    # ------------------------------------------------------------------

    def action_complete_step(self, step=None, force=False):
        """Mark ``step`` (default: the current step) as done for every item.

        Earlier pending steps are skipped when allowed. ``force`` lets managers skip mandatory steps.
        """
        if force and not self._ki_is_manager():
            raise AccessError(self.env._("Only laundry managers can force steps."))
        self._ki_check_processable()
        now = fields.Datetime.now()
        for item in self:
            if item.state not in OPEN_STATES:
                raise UserError(self.env._(
                    "Item %(item)s is %(state)s.", item=item.barcode,
                    state=dict(self._fields['state'].selection)[item.state]))
            pending = item.route_ids.filtered(lambda r: r.state == 'pending').sorted(lambda r: (r.sequence, r.id))
            if not pending:
                item._ki_set_ready()
                continue
            if step:
                target = item.route_ids.filtered(lambda r: r.step_id == step)
                if not target:
                    raise UserError(self.env._(
                        "Item %(item)s does not need step %(step)s.", item=item.barcode, step=step.name))
                if target.state != 'pending':
                    raise UserError(self.env._(
                        "Step %(step)s is already done for item %(item)s.", item=item.barcode, step=step.name))
            else:
                target = pending[0]
            before = pending.filtered(lambda r: (r.sequence, r.id) < (target.sequence, target.id))
            mandatory = before.filtered(lambda r: not r.step_id.allow_skip)
            if mandatory and not force:
                raise UserError(self.env._(
                    "Item %(item)s must first go through: %(steps)s.",
                    item=item.barcode, steps=", ".join(mandatory.step_id.mapped('name'))))
            state_from = item.state
            for route in before:
                route.sudo().write({'state': 'skipped', 'user_id': self.env.user.id, 'date_done': now})
                item._ki_log('skip', step_from=route.step_id, state_from=state_from)
            target.sudo().write({'state': 'done', 'user_id': self.env.user.id, 'date_done': now})
            if pending - before - target:
                item.sudo().write({'state': 'in_process'})
                item._ki_log('advance', step_from=target.step_id, step_to=item.current_step_id,
                             state_from=state_from)
            else:
                item._ki_log('advance', step_from=target.step_id, state_from=state_from)
                item._ki_set_ready()
        self.order_id._ki_update_state_from_items()
        return True

    def action_skip_step(self):
        for item in self:
            route = item.route_ids.filtered(lambda r: r.state == 'pending').sorted(lambda r: (r.sequence, r.id))[:1]
            if not route:
                continue
            if not route.step_id.allow_skip and not self._ki_is_manager():
                raise AccessError(self.env._("Only laundry managers can skip step %s.", route.step_id.name))
            item._ki_check_processable()
            state_from = item.state
            route.sudo().write({'state': 'skipped', 'user_id': self.env.user.id,
                                'date_done': fields.Datetime.now()})
            item._ki_log('skip', step_from=route.step_id, step_to=item.current_step_id, state_from=state_from)
            if not item.route_ids.filtered(lambda r: r.state == 'pending'):
                item._ki_set_ready()
            elif item.state == 'pending':
                item.sudo().write({'state': 'in_process'})
        self.order_id._ki_update_state_from_items()
        return True

    def action_mark_ready(self):
        for item in self:
            if item.state not in OPEN_STATES:
                raise UserError(self.env._("Item %s is not in process.", item.barcode))
            pending = item.route_ids.filtered(lambda r: r.state == 'pending')
            if pending.filtered(lambda r: not r.step_id.allow_skip) and not self._ki_is_manager():
                raise AccessError(self.env._(
                    "Item %(item)s still has steps to do (%(steps)s). Only managers can mark it ready.",
                    item=item.barcode, steps=", ".join(pending.step_id.mapped('name'))))
        self._ki_check_processable()
        self._ki_force_ready()
        self.order_id._ki_update_state_from_items()
        return True

    def action_rework(self, step=None, note=None):
        """Send the items back to ``step`` (default: the first processing step of their route)."""
        for item in self:
            if item.state not in ('in_process', 'ready', 'rework', 'damaged'):
                raise UserError(self.env._("Item %s cannot be sent to rework.", item.barcode))
        self._ki_check_processable()
        for item in self:
            route = item.route_ids.sorted(lambda r: (r.sequence, r.id))
            if step:
                start = route.filtered(lambda r: r.step_id == step)
                if not start:
                    raise UserError(self.env._(
                        "Step %(step)s is not on the route of item %(item)s.", step=step.name, item=item.barcode))
            else:
                start = route.filtered(lambda r: r.step_id.step_type == 'process')[:1] or route[:1]
            state_from = item.state
            if start:
                route.filtered(lambda r: (r.sequence, r.id) >= (start.sequence, start.id)).sudo().write(
                    {'state': 'pending', 'user_id': False, 'date_done': False})
            item.sudo().write({'state': 'rework', 'date_ready': False})
            item._ki_log('rework', step_to=start.step_id, state_from=state_from, note=note)
        self.order_id.filtered(lambda o: o.state in ('ready', 'partially_ready')).sudo().write(
            {'date_ready': False})
        self.order_id._ki_update_state_from_items()
        return True

    def action_mark_damaged(self):
        if not self._ki_is_manager():
            raise AccessError(self.env._("Only laundry managers can mark items as damaged."))
        for item in self:
            if item.state in ('delivered', 'lost', 'cancelled'):
                raise UserError(self.env._("Item %s cannot be marked as damaged.", item.barcode))
            state_from = item.state
            item.sudo().write({'state': 'damaged', 'has_damage': True})
            item._ki_log('damage', state_from=state_from)
            item.order_id.message_post(body=self.env._("Item %s marked as damaged.", item.barcode))
        self.order_id._ki_update_state_from_items()
        return True

    def action_mark_lost(self):
        if not self._ki_is_manager():
            raise AccessError(self.env._("Only laundry managers can mark items as lost."))
        for item in self:
            if item.state in ('delivered', 'cancelled'):
                raise UserError(self.env._("Item %s cannot be marked as lost.", item.barcode))
            state_from = item.state
            item.sudo().write({'state': 'lost'})
            item._ki_log('lost', state_from=state_from)
            item.order_id.message_post(body=self.env._("Item %s marked as lost.", item.barcode))
        self.order_id._ki_update_state_from_items()
        return True

    def action_found(self):
        for item in self.filtered(lambda i: i.state == 'lost'):
            pending = item.route_ids.filtered(lambda r: r.state == 'pending')
            done = item.route_ids - pending
            new_state = 'ready' if not pending else ('in_process' if done else 'pending')
            item.sudo().write({'state': new_state})
            item._ki_log('found', state_from='lost')
        self.order_id._ki_update_state_from_items()
        return True

    def _ki_deliver(self):
        now = fields.Datetime.now()
        for item in self:
            if item.state not in ('ready', 'damaged'):
                raise UserError(self.env._("Item %s is not ready for delivery.", item.barcode))
            state_from = item.state
            item.sudo().write({'state': 'delivered', 'date_delivered': now, 'delivered_by_id': self.env.user.id})
            item._ki_log('deliver', state_from=state_from)
        self.order_id._ki_update_state_from_items()

    def action_print_tag(self):
        return self.env.ref('ki_laundry_management_base.action_report_laundry_tag').report_action(self)

    def action_open_rework_wizard(self):
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._("Send to Rework"),
            'res_model': 'ki.laundry.rework.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_item_ids': self.ids},
        }

    # ------------------------------------------------------------------
    # Workstation API
    # ------------------------------------------------------------------

    @api.model
    def ki_workstation_scan(self, barcode, step_id=False, force=False):
        """Complete ``step_id`` for the scanned item (or all items of a scanned order receipt)."""
        barcode = (barcode or '').strip()
        if not barcode:
            return {'success': False, 'message': self.env._("Empty barcode.")}
        step = self.env['ki.laundry.process.step'].browse(step_id).exists() if step_id else None
        items = self.search([('barcode', '=', barcode)], limit=1)
        if not items:
            order = self.env['ki.laundry.order'].search([('barcode', '=', barcode)], limit=1)
            if not order:
                return {'success': False, 'message': self.env._("No laundry item or order found for %s.", barcode)}
            items = order.item_ids.filtered(lambda i: i.state in OPEN_STATES)
            if step:
                # A receipt scanned at a station only moves the items waiting for that step.
                items = items.filtered(lambda i: i.route_ids.filtered(
                    lambda r: r.step_id == step and r.state == 'pending'))
            if not items:
                return {'success': False, 'message': self.env._(
                    "Order %(order)s has no item waiting for %(step)s.",
                    order=order.name, step=step.name if step else self.env._("processing"))}
        try:
            with self.env.cr.savepoint():
                items.action_complete_step(step=step, force=force)
        except (UserError, AccessError) as error:
            return {'success': False, 'message': str(error.args[0] if error.args else error),
                    'items': items._ki_workstation_data()}
        return {
            'success': True,
            'message': self.env._("%s item(s) updated.", len(items)),
            'items': items._ki_workstation_data(),
        }

    @api.model
    def ki_workstation_data(self, step_id=False, limit=50):
        """Stations with the number of garments waiting there, and the queue of ``step_id``
        (every open garment when no station is selected), the most urgent first."""
        open_domain = [('state', 'in', OPEN_STATES), ('order_id.is_stopped', '=', False)]
        counts = dict(self._read_group(open_domain + [('current_step_id', '!=', False)],
                                       ['current_step_id'], ['__count']))
        steps = self.env['ki.laundry.process.step'].search([])
        queue_domain = open_domain + ([('current_step_id', '=', step_id)] if step_id else [])
        queue = self.search(queue_domain, order='is_urgent desc, date_due, id', limit=limit)
        return {
            'steps': [{'id': step.id, 'name': step.name, 'count': counts.get(step, 0)} for step in steps],
            'total': self.search_count(open_domain),
            'queue': queue._ki_workstation_data(),
            'queue_count': self.search_count(queue_domain),
        }

    def _ki_workstation_data(self):
        state_labels = dict(self._fields['state'].selection)
        return [{
            'id': item.id,
            'barcode': item.barcode,
            'name': item.name,
            'order_id': item.order_id.id,
            'order': item.order_id.name,
            'customer': item.partner_id.display_name,
            'state': item.state,
            'state_label': state_labels.get(item.state),
            'current_step': item.current_step_id.name or '',
            'is_urgent': item.is_urgent,
            'date_due': fields.Datetime.to_string(item.date_due) if item.date_due else False,
            'description': item.description or '',
            'has_damage': item.has_damage,
            'route': [{'step': r.step_id.name, 'state': r.state,
                       'current': r.state == 'pending' and r.step_id == item.current_step_id}
                      for r in item.route_ids.sorted(lambda r: (r.sequence, r.id))],
        } for item in self]
