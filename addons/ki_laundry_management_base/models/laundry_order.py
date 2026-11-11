# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
#  Kalvyai | Laundry Management - Base
#  Copyright (c) 2026-Present Kalvyai (https://kalvyai.com)
#  License: OPL-1. See the LICENSE file.
# ----------------------------------------------------------------------------
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.fields import Command
from odoo.tools import float_is_zero

# Channel modules (website pickup, ...) add their own states with selection_add and extend
# the ``_ki_*_states`` methods below, so every check follows.
ORDER_STATES = [
    ('draft', "Draft"),
    ('received', "Received"),
    ('in_process', "In Process"),
    ('partially_ready', "Partially Ready"),
    ('ready', "Ready"),
    ('delivered', "Delivered"),
    ('cancelled', "Cancelled"),
]
FINISHED_ITEM_STATES = ('ready', 'delivered', 'damaged')

MAIL_EVENTS = {
    'received': 'ki_laundry_management_base.mail_template_laundry_received',
    'ready': 'ki_laundry_management_base.mail_template_laundry_ready',
    'delivered': 'ki_laundry_management_base.mail_template_laundry_delivered',
    'reminder': 'ki_laundry_management_base.mail_template_laundry_reminder',
}


class LaundryOrder(models.Model):
    _name = 'ki.laundry.order'
    _description = "Laundry Order"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_order desc, id desc'
    _check_company_auto = True

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------
    name = fields.Char(
        string="Reference", required=True, readonly=True, copy=False, index='trigram',
        default=lambda self: self.env._("New"),
    )
    barcode = fields.Char(copy=False, readonly=True, index=True)
    company_id = fields.Many2one(
        'res.company', required=True, index=True, default=lambda self: self.env.company)
    channel = fields.Selection(
        [('backend', "Backend")], default='backend', required=True, readonly=True,
        help="Where the order was created. The POS and Website modules add their channel.")
    partner_id = fields.Many2one(
        'res.partner', string="Customer", required=True, index=True, tracking=True,
        check_company=True, domain="[('type', '!=', 'private')]")
    partner_phone = fields.Char(related='partner_id.phone', string="Phone")
    partner_email = fields.Char(related='partner_id.email', string="Email")
    partner_invoice_id = fields.Many2one(
        'res.partner', string="Invoice Address", check_company=True,
        compute='_compute_partner_invoice_id', store=True, readonly=False, precompute=True)
    user_id = fields.Many2one('res.users', string="Responsible", default=lambda self: self.env.user,
                              tracking=True, check_company=True)
    origin = fields.Char(string="Source Document")

    # ------------------------------------------------------------------
    # State & dates
    # ------------------------------------------------------------------
    state = fields.Selection(ORDER_STATES, default='draft', required=True, readonly=True,
                             copy=False, index=True, tracking=True)
    delivery_status = fields.Selection(
        [('none', "Not Delivered"), ('partial', "Partially Delivered"), ('full', "Fully Delivered")],
        compute='_compute_item_counts', store=True)
    date_order = fields.Datetime(string="Order Date", required=True, default=fields.Datetime.now, copy=False)
    date_received = fields.Datetime(readonly=True, copy=False)
    date_due = fields.Datetime(
        string="Due Date", compute='_compute_date_due', store=True, readonly=False, copy=False,
        index=True, tracking=True)
    date_ready = fields.Datetime(readonly=True, copy=False)
    date_delivered = fields.Datetime(readonly=True, copy=False)
    is_urgent = fields.Boolean(string="Urgent", tracking=True)
    is_late = fields.Boolean(compute='_compute_is_late', search='_search_is_late')
    cancel_reason = fields.Text(readonly=True, copy=False)
    is_stopped = fields.Boolean(
        string="Stopped", readonly=True, copy=False,
        help="Processing was stopped and garments are returned to the customer.")
    reminder_count = fields.Integer(readonly=True, copy=False)
    ready_notified = fields.Boolean(readonly=True, copy=False,
                                    help="The 'order ready' e-mail was sent (it is not repeated after a rework).")

    # State groups, for the views (they follow the ``_ki_*_states`` methods).
    garments_editable = fields.Boolean(
        compute='_compute_state_flags', help="Garments can still be added or changed (not received yet).")
    prices_editable = fields.Boolean(
        compute='_compute_state_flags', help="Prices and charges can still change (processing not started).")
    in_custody = fields.Boolean(compute='_compute_state_flags', help="The garments are at the store.")
    can_deliver = fields.Boolean(compute='_compute_state_flags', help="Ready garments can be handed over.")

    # ------------------------------------------------------------------
    # Pricing
    # ------------------------------------------------------------------
    pricelist_id = fields.Many2one(
        'product.pricelist', string="Pricelist", check_company=True,
        compute='_compute_pricelist_id', store=True, readonly=False, precompute=True, tracking=True)
    currency_id = fields.Many2one(
        'res.currency', compute='_compute_currency_id', store=True, precompute=True, readonly=True)
    fiscal_position_id = fields.Many2one(
        'account.fiscal.position', string="Fiscal Position", check_company=True,
        compute='_compute_fiscal_position_id', store=True, readonly=False, precompute=True)
    payment_term_id = fields.Many2one(
        'account.payment.term', string="Payment Terms", check_company=True,
        compute='_compute_payment_term_id', store=True, readonly=False, precompute=True)
    price_date = fields.Datetime(
        readonly=True, copy=False,
        help="Date used for every price computation of this order, so that offers valid when the "
             "order was received still apply when the price is updated later (e.g. after weighing).")

    # ------------------------------------------------------------------
    # Lines
    # ------------------------------------------------------------------
    intake_ids = fields.One2many('ki.laundry.order.intake', 'order_id', string="Intake", copy=True)
    line_ids = fields.One2many('ki.laundry.order.line', 'order_id', string="Billing Lines", copy=False)
    item_ids = fields.One2many('ki.laundry.order.item', 'order_id', string="Items", copy=False)
    item_count = fields.Integer(compute='_compute_item_counts', store=True)
    item_ready_count = fields.Integer(compute='_compute_item_counts', store=True)
    item_delivered_count = fields.Integer(compute='_compute_item_counts', store=True)
    piece_count = fields.Integer(string="Pieces", compute='_compute_intake_totals', store=True)
    weight_total = fields.Float(string="Weight (kg)", compute='_compute_intake_totals', store=True,
                                digits='Stock Weight')

    # ------------------------------------------------------------------
    # Money
    # ------------------------------------------------------------------
    amount_untaxed = fields.Monetary(compute='_compute_amounts', store=True, tracking=True)
    amount_tax = fields.Monetary(compute='_compute_amounts', store=True)
    amount_total = fields.Monetary(compute='_compute_amounts', store=True, tracking=True)
    tax_totals = fields.Binary(compute='_compute_tax_totals', exportable=False)
    payment_policy = fields.Selection(
        [('prepaid', "Pay at Drop-off"), ('on_collection', "Pay at Collection"),
         ('advance', "Advance + Balance"), ('credit', "On Credit (Invoice)")],
        default=lambda self: self.env.company.ki_laundry_payment_policy or 'on_collection',
        required=True, tracking=True)
    financial_path = fields.Selection(
        [('invoice', "Invoice")], readonly=True, copy=False,
        help="Set by the first financial document. An order is paid through a single path (invoices, "
             "or the Point of Sale when installed), never both, which prevents double invoicing.")
    invoice_ids = fields.Many2many('account.move', compute='_compute_invoice_ids', string="Invoices",
                                   compute_sudo=True)
    invoice_count = fields.Integer(compute='_compute_invoice_ids', compute_sudo=True)
    invoice_status = fields.Selection(
        [('no', "Nothing to Invoice"), ('to_invoice', "To Invoice"), ('invoiced', "Fully Invoiced")],
        compute='_compute_invoice_status', store=True)
    amount_paid = fields.Monetary(compute='_compute_amount_paid', compute_sudo=True)
    amount_due = fields.Monetary(compute='_compute_amount_paid', compute_sudo=True)

    note = fields.Text(string="Customer Note")
    internal_note = fields.Text()

    _barcode_uniq = models.UniqueIndex('(barcode) WHERE (barcode IS NOT NULL)', "The order barcode must be unique.")
    _state_date_due_idx = models.Index('(state, date_due)')

    # ------------------------------------------------------------------
    # State groups (extended by channel modules)
    # ------------------------------------------------------------------

    @api.model
    def _ki_pre_receive_states(self):
        """States where the garments are not at the store yet."""
        return ['draft']

    @api.model
    def _ki_process_states(self):
        """States where the garments are in our custody."""
        return ['received', 'in_process', 'partially_ready', 'ready']

    @api.model
    def _ki_charge_states(self):
        """States where prices and automatic charges still follow the order."""
        return self._ki_pre_receive_states() + ['received']

    @api.model
    def _ki_deliverable_states(self):
        """States where ready garments can be handed over."""
        return ['ready', 'partially_ready']

    @api.model
    def _ki_late_states(self):
        """States where a passed due date means the order is late."""
        return [s for s in self._ki_pre_receive_states() if s != 'draft'] + \
            ['received', 'in_process', 'partially_ready']

    @api.depends('state')
    def _compute_state_flags(self):
        pre_receive = self._ki_pre_receive_states()
        charge = self._ki_charge_states()
        process = self._ki_process_states()
        deliverable = self._ki_deliverable_states()
        for order in self:
            order.garments_editable = order.state in pre_receive
            order.prices_editable = order.state in charge
            order.in_custody = order.state in process
            order.can_deliver = order.state in deliverable

    def _ki_paid_elsewhere(self):
        """The order is paid through another channel (e.g. the Point of Sale), not invoices."""
        self.ensure_one()
        return bool(self.financial_path) and self.financial_path != 'invoice'

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------

    @api.depends('partner_id')
    def _compute_partner_invoice_id(self):
        for order in self:
            order.partner_invoice_id = order.partner_id.address_get(['invoice'])['invoice'] \
                if order.partner_id else False

    @api.depends('partner_id', 'company_id')
    def _compute_pricelist_id(self):
        for order in self:
            if order.state != 'draft' and order.pricelist_id:
                continue
            pricelist = order.partner_id.with_company(order.company_id).property_product_pricelist \
                if order.partner_id else False
            if pricelist and pricelist.company_id and pricelist.company_id != order.company_id:
                pricelist = False
            order.pricelist_id = pricelist

    @api.depends('pricelist_id', 'company_id')
    def _compute_currency_id(self):
        for order in self:
            order.currency_id = order.pricelist_id.currency_id or order.company_id.currency_id

    @api.depends('partner_invoice_id', 'company_id')
    def _compute_fiscal_position_id(self):
        cache = {}
        for order in self:
            if not order.partner_id:
                order.fiscal_position_id = False
                continue
            partner = order.partner_invoice_id or order.partner_id
            key = (order.company_id.id, partner.id)
            if key not in cache:
                cache[key] = self.env['account.fiscal.position'].with_company(
                    order.company_id)._get_fiscal_position(partner)
            order.fiscal_position_id = cache[key]

    @api.depends('partner_id', 'company_id')
    def _compute_payment_term_id(self):
        for order in self:
            order.payment_term_id = order.partner_id.with_company(order.company_id).property_payment_term_id \
                if order.partner_id else False

    @api.depends('intake_ids.service_ids', 'is_urgent', 'date_received', 'date_order', 'company_id')
    def _compute_date_due(self):
        for order in self:
            services = order.intake_ids.service_ids
            if not services:
                order.date_due = order.date_due or False
                continue
            field = 'ki_laundry_urgent_tat_hours' if order.is_urgent else 'ki_laundry_tat_hours'
            hours = max(services.mapped(field) or [0.0])
            start = order.date_received or order.date_order or fields.Datetime.now()
            order.date_due = order.company_id._ki_laundry_plan(start, hours)

    @api.depends('date_due', 'state')
    def _compute_is_late(self):
        now = fields.Datetime.now()
        late_states = self._ki_late_states()
        for order in self:
            order.is_late = bool(order.date_due and order.date_due < now and order.state in late_states)

    def _search_is_late(self, operator, value):
        if operator not in ('=', '!=') or not isinstance(value, bool):
            raise UserError(self.env._("Unsupported search on 'Late'."))
        domain = [('date_due', '<', fields.Datetime.now()), ('state', 'in', self._ki_late_states())]
        if (operator == '=') == value:
            return domain
        return ['!', '&'] + domain

    @api.depends('item_ids.state')
    def _compute_item_counts(self):
        for order in self:
            items = order.item_ids.filtered(lambda i: i.state not in ('cancelled', 'lost'))
            delivered = items.filtered(lambda i: i.state == 'delivered')
            order.item_count = len(items)
            order.item_ready_count = len(items.filtered(lambda i: i.state in FINISHED_ITEM_STATES))
            order.item_delivered_count = len(delivered)
            if not delivered:
                order.delivery_status = 'none'
            elif len(delivered) == len(items):
                order.delivery_status = 'full'
            else:
                order.delivery_status = 'partial'

    @api.depends('intake_ids.quantity', 'intake_ids.pricing_mode', 'intake_ids.weight_actual',
                 'intake_ids.weight_estimated')
    def _compute_intake_totals(self):
        for order in self:
            piece = order.intake_ids.filtered(lambda i: i.pricing_mode == 'piece')
            kg = order.intake_ids - piece
            order.piece_count = sum(piece.mapped('quantity'))
            order.weight_total = sum(i.weight_actual or i.weight_estimated for i in kg)

    def _ki_get_base_lines(self):
        self.ensure_one()
        lines = self.line_ids.filtered(lambda l: l.line_type != 'advance')
        return [line._ki_prepare_base_line() for line in lines]

    @api.depends('line_ids.price_subtotal', 'line_ids.price_total', 'line_ids.line_type', 'currency_id')
    def _compute_amounts(self):
        AccountTax = self.env['account.tax']
        for order in self:
            base_lines = order._ki_get_base_lines()
            AccountTax._add_tax_details_in_base_lines(base_lines, order.company_id)
            AccountTax._round_base_lines_tax_details(base_lines, order.company_id)
            totals = AccountTax._get_tax_totals_summary(
                base_lines=base_lines, currency=order.currency_id or order.company_id.currency_id,
                company=order.company_id)
            order.amount_untaxed = totals['base_amount_currency']
            order.amount_tax = totals['tax_amount_currency']
            order.amount_total = totals['total_amount_currency']

    @api.depends_context('lang')
    @api.depends('line_ids.price_subtotal', 'line_ids.price_total', 'line_ids.line_type', 'currency_id')
    def _compute_tax_totals(self):
        AccountTax = self.env['account.tax']
        for order in self:
            base_lines = order._ki_get_base_lines()
            AccountTax._add_tax_details_in_base_lines(base_lines, order.company_id)
            AccountTax._round_base_lines_tax_details(base_lines, order.company_id)
            order.tax_totals = AccountTax._get_tax_totals_summary(
                base_lines=base_lines, currency=order.currency_id or order.company_id.currency_id,
                company=order.company_id)

    @api.depends('line_ids.invoice_line_ids.move_id')
    def _compute_invoice_ids(self):
        for order in self:
            moves = order.line_ids.invoice_line_ids.move_id.filtered(
                lambda m: m.move_type in ('out_invoice', 'out_refund'))
            order.invoice_ids = moves
            order.invoice_count = len(moves)

    @api.depends('state', 'financial_path', 'line_ids.qty_to_invoice', 'line_ids.qty_invoiced')
    def _compute_invoice_status(self):
        for order in self:
            lines = order.line_ids.filtered(lambda l: l.line_type != 'advance')
            if order.state == 'draft' or order._ki_paid_elsewhere() or not lines:
                order.invoice_status = 'no'
            elif any(not float_is_zero(l.qty_to_invoice, precision_rounding=l.product_uom_id.rounding or 0.01)
                     for l in lines):
                order.invoice_status = 'to_invoice'
            elif any(l.qty_invoiced for l in lines):
                order.invoice_status = 'invoiced'
            else:
                order.invoice_status = 'no'

    @api.depends('amount_total', 'line_ids.invoice_line_ids.move_id.amount_residual',
                 'line_ids.invoice_line_ids.move_id.state')
    def _compute_amount_paid(self):
        for order in self:
            order.amount_paid = order._ki_laundry_get_amount_paid()
            order.amount_due = order.currency_id.round(order.amount_total - order.amount_paid) \
                if order.currency_id else order.amount_total - order.amount_paid

    def _ki_laundry_get_amount_paid(self):
        """Amount already paid by the customer. Extended by the POS module."""
        self.ensure_one()
        paid = 0.0
        for move in self.sudo().invoice_ids.filtered(lambda m: m.state == 'posted'):
            amount = move.amount_total - move.amount_residual
            if move.currency_id != self.currency_id:
                amount = move.currency_id._convert(amount, self.currency_id, self.company_id,
                                                   move.invoice_date or fields.Date.context_today(self))
            paid += amount if move.move_type == 'out_invoice' else -amount
        return paid

    # ------------------------------------------------------------------
    # ORM
    # ------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', self.env._("New")) == self.env._("New"):
                company = self.env['res.company'].browse(vals.get('company_id')) or self.env.company
                vals['name'] = self.env['ir.sequence'].with_company(company).next_by_code(
                    'ki.laundry.order') or self.env._("New")
        orders = super().create(vals_list)
        orders._ki_sync_charge_lines()
        return orders

    LOCKED_AFTER_CONFIRM = ('partner_id', 'pricelist_id', 'company_id', 'fiscal_position_id')

    def write(self, vals):
        charge_fields = self._ki_charge_fields()
        if not self.env.context.get('ki_laundry_force'):
            locked = [f for f in self.LOCKED_AFTER_CONFIRM if f in vals]
            if locked and any(order.state != 'draft' for order in self):
                raise UserError(self.env._(
                    "Customer, pricelist, fiscal position and company cannot be changed once the order "
                    "is received."))
            if charge_fields & set(vals) and any(o.state not in o._ki_charge_states() for o in self):
                raise UserError(self.env._("Order options cannot be changed once processing has started."))
        result = super().write(vals)
        if (charge_fields | {'pricelist_id', 'fiscal_position_id'}) & set(vals):
            if 'pricelist_id' in vals or 'fiscal_position_id' in vals:
                self.line_ids.filtered(lambda l: l.line_type in ('service', 'addon'))._ki_recompute_taxes()
                self.line_ids.filtered(lambda l: l.line_type in ('service', 'addon'))._ki_recompute_price()
            self._ki_sync_charge_lines()
        return result

    @api.ondelete(at_uninstall=False)
    def _unlink_except_processed(self):
        for order in self:
            if order.state not in ('draft', 'cancelled'):
                raise UserError(self.env._(
                    "Only draft or cancelled laundry orders can be deleted (%s).", order.name))
            if order.invoice_ids.filtered(lambda m: m.state != 'cancel'):
                raise UserError(self.env._("Order %s is linked to invoices and cannot be deleted.", order.name))

    @api.onchange('partner_id')
    def _onchange_partner_id_warning(self):
        if self.partner_id.ki_laundry_preference:
            return {'warning': {
                'title': self.env._("Customer preference"),
                'message': self.partner_id.ki_laundry_preference,
                'type': 'notification',
            }}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _ki_check_access_group(self, xmlid, message):
        if not self.env.su and not self.env.user.has_group(xmlid):
            raise AccessError(message)

    def _ki_is_manager(self):
        return self.env.su or self.env.user.has_group('ki_laundry_management_base.group_laundry_manager')

    def _ki_services_subtotal(self):
        self.ensure_one()
        return sum(self.line_ids.filtered(lambda l: l.line_type in ('service', 'addon')).mapped('price_subtotal'))

    # ------------------------------------------------------------------
    # Automatic charge lines (extended by channel modules, e.g. delivery charges)
    # ------------------------------------------------------------------

    @api.model
    def _ki_charge_line_types(self):
        """Line types created / updated / removed by ``_ki_sync_charge_lines``."""
        return ['urgent']

    @api.model
    def _ki_charge_fields(self):
        """Order fields the automatic charges depend on."""
        return {'is_urgent'}

    def _ki_wanted_charges(self):
        """Return ``{line_type: (product, name, price)}`` for the charges this order needs."""
        self.ensure_one()
        wanted = {}
        if self.is_urgent:
            surcharge = 0.0
            for line in self.line_ids.filtered(lambda l: l.line_type == 'service'):
                service = line.product_id.product_tmpl_id
                if service.ki_laundry_urgent_surcharge_type == 'percent':
                    surcharge += line.price_subtotal * service.ki_laundry_urgent_surcharge / 100.0
                else:
                    surcharge += service.ki_laundry_urgent_surcharge * line.product_uom_qty
            if not self.currency_id.is_zero(surcharge):
                wanted['urgent'] = (self.company_id._ki_laundry_system_product('urgent'),
                                    self.env._("Urgent service surcharge"), self.currency_id.round(surcharge))
        return wanted

    def _ki_sync_charge_lines(self):
        """Create / update / remove the automatic charge lines (urgent surcharge, ...)."""
        Line = self.env['ki.laundry.order.line'].with_context(ki_laundry_system=True)
        for order in self.filtered(lambda o: o.state in o._ki_charge_states()):
            wanted = order._ki_wanted_charges()
            for line_type in order._ki_charge_line_types():
                existing = order.line_ids.filtered(lambda l, t=line_type: l.line_type == t)
                if line_type not in wanted:
                    existing.filtered(lambda l: not l.qty_invoiced).with_context(ki_laundry_system=True).unlink()
                    continue
                product, name, price = wanted[line_type]
                if existing:
                    line = existing[0]
                    if line.qty_invoiced:
                        continue
                    if line.currency_id.compare_amounts(line.price_unit, price) or line.name != name:
                        line.with_context(ki_laundry_system=True).write({'price_unit': price, 'name': name})
                else:
                    Line.create({
                        'order_id': order.id,
                        'line_type': line_type,
                        'product_id': product.id,
                        'name': name,
                        'product_uom_qty': 1.0,
                        'price_unit': price,
                        'price_is_manual': True,
                        'sequence': 1000,
                    })

    def _ki_check_before_receive(self):
        self.ensure_one()
        if not self.intake_ids:
            raise UserError(self.env._("Add at least one garment or load to order %s.", self.name))
        self.intake_ids._ki_check_valid(final=True)

    def _ki_send_mail(self, event):
        template = self.env.ref(MAIL_EVENTS[event], raise_if_not_found=False)
        if not template:
            return
        for order in self:
            if not order.company_id[f'ki_laundry_mail_{event}'] or not order.partner_id.email:
                continue
            order.sudo().message_post_with_source(
                template.sudo(),
                email_layout_xmlid='mail.mail_notification_light',
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
                author_id=self.env.user.partner_id.id,
            )

    def _ki_new_barcode(self):
        return self.env['ir.sequence'].sudo().next_by_code('ki.laundry.order.barcode')

    # ------------------------------------------------------------------
    # Workflow actions
    # ------------------------------------------------------------------

    def action_receive(self):
        """Garments are at the store: freeze prices, finalise quantities / weights and create the tags."""
        for order in self:
            if order.state not in order._ki_pre_receive_states():
                raise UserError(self.env._("Order %s cannot be received in its current state.", order.name))
            order._ki_check_before_receive()
        now = fields.Datetime.now()
        for order in self:
            vals = {'state': 'received', 'date_received': now}
            if not order.price_date:
                vals['price_date'] = now
            if not order.barcode:
                vals['barcode'] = order._ki_new_barcode()
            order.write(vals)
            order.intake_ids._ki_sync_lines()
            order.line_ids.filtered(lambda l: l.line_type in ('service', 'addon'))._ki_recompute_price()
            order._ki_sync_charge_lines()
            order.intake_ids._ki_generate_items()
        self._ki_send_mail('received')
        self._ki_update_state_from_items()
        return True

    def action_open_deliver_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._("Deliver Garments"),
            'res_model': 'ki.laundry.deliver.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_order_id': self.id},
        }

    def action_open_cancel_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._("Cancel / Stop Order"),
            'res_model': 'ki.laundry.cancel.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_order_id': self.id},
        }

    def action_open_invoice_wizard(self):
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._("Create Invoice"),
            'res_model': 'ki.laundry.invoice.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'active_model': self._name, 'active_ids': self.ids},
        }

    def action_draft(self):
        for order in self:
            if order.state != 'cancelled' or order.is_stopped:
                raise UserError(self.env._("Only cancelled orders can be reset to draft."))
        self.write({'state': 'draft', 'cancel_reason': False, 'price_date': False})
        return True

    def action_recompute_prices(self):
        if not self._ki_is_manager():
            raise AccessError(self.env._("Only laundry managers can recompute prices."))
        for order in self:
            if order.state not in order._ki_charge_states():
                raise UserError(self.env._("Prices of %s are final once processing has started.", order.name))
            lines = order.line_ids.filtered(lambda l: l.line_type in ('service', 'addon') and not l.qty_invoiced)
            lines.write({'price_is_manual': False})
            lines._ki_recompute_price()
            order._ki_sync_charge_lines()
        return True

    def _ki_cancel(self, reason):
        """Cancel orders whose garments are not in our custody yet."""
        for order in self:
            if order.state not in order._ki_pre_receive_states():
                raise UserError(self.env._(
                    "Order %s has garments in custody: use 'Stop & Return' instead.", order.name))
            order._ki_laundry_check_cancel_allowed()
            posted = order.invoice_ids.filtered(lambda m: m.state == 'posted')
            if posted and order.currency_id.compare_amounts(order._ki_net_invoiced(), 0.0):
                raise UserError(self.env._(
                    "Order %s has posted invoices. Issue a credit note before cancelling.", order.name))
            order.invoice_ids.filtered(lambda m: m.state == 'draft').button_cancel()
        self.write({'state': 'cancelled', 'cancel_reason': reason})
        for order in self:
            order.message_post(body=self.env._("Order cancelled: %s", reason or '-'))
        return True

    def _ki_laundry_check_cancel_allowed(self):
        """Hook for channel modules (e.g. POS payments must be refunded first)."""
        return True

    def _ki_net_invoiced(self):
        self.ensure_one()
        total = 0.0
        for move in self.invoice_ids.filtered(lambda m: m.state == 'posted'):
            total += move.amount_total if move.move_type == 'out_invoice' else -move.amount_total
        return total

    def _ki_stop_and_return(self, reason, charge_policy, fee=0.0):
        """Stop processing and return garments. Charges become none / a fee / unchanged."""
        if not self._ki_is_manager():
            raise AccessError(self.env._("Only laundry managers can stop an order in process."))
        for order in self:
            if order.state not in order._ki_process_states():
                raise UserError(self.env._("Order %s is not in process.", order.name))
            order._ki_laundry_check_cancel_allowed()
            charge_lines = order.line_ids.filtered(lambda l: l.line_type != 'advance')
            if charge_policy != 'full':
                if charge_lines.filtered('qty_invoiced'):
                    raise UserError(self.env._(
                        "Order %s is already invoiced. Issue a credit note first, or keep the full charge.",
                        order.name))
                currency = order.currency_id
                target = 0.0 if charge_policy == 'none' else currency.round(min(max(fee, 0.0), order.amount_total))
                # The fee is billed on a single line: spreading it as a discount over many
                # lines loses cents to rounding (a 50.00 fee would become 49.99).
                base = charge_lines.filtered('price_subtotal').sorted('price_total')[-1:]
                ratio = base.price_total / base.price_subtotal if base else 1.0
                charge_lines.with_context(ki_laundry_system=True).write({'discount': 100.0, 'price_is_manual': True})
                if base and not currency.is_zero(target):
                    fee_line = self.env['ki.laundry.order.line'].with_context(ki_laundry_system=True).create({
                        'order_id': order.id,
                        'line_type': 'other',
                        'product_id': base.product_id.id,
                        'name': self.env._("Stop & Return fee"),
                        'product_uom_qty': 1.0,
                        'price_unit': currency.round(target / ratio),
                        'tax_ids': [Command.set(base.tax_ids.ids)],
                        'price_is_manual': True,
                        'sequence': 9999,
                    })
                    for _attempt in range(3):
                        diff = currency.round(target - order.amount_total)
                        if currency.is_zero(diff):
                            break
                        fee_line.price_unit = currency.round(fee_line.price_unit + diff / ratio) or (
                            fee_line.price_unit + (currency.rounding if diff > 0 else -currency.rounding))
            open_items = order.item_ids.filtered(lambda i: i.state in ('pending', 'in_process', 'rework'))
            open_items._ki_force_ready(self.env._("Order stopped"))
            order.write({'is_stopped': True, 'cancel_reason': reason})
            order.message_post(body=self.env._(
                "Processing stopped, garments to be returned. Reason: %(reason)s. Charge: %(charge)s",
                reason=reason or '-', charge=order.amount_total))
        self._ki_update_state_from_items()
        return True

    def _ki_state_from_items(self, items):
        """State matching the order's ``items`` (cancelled / lost excluded). Extended by channel modules."""
        self.ensure_one()
        delivered = items.filtered(lambda i: i.state == 'delivered')
        remaining = items - delivered
        waiting = remaining.filtered(lambda i: i.state in FINISHED_ITEM_STATES)
        if not remaining:
            return 'delivered'
        if len(waiting) == len(remaining):
            return 'ready'
        if waiting:
            return 'partially_ready'
        if delivered or remaining.filtered(
                lambda i: i.state in ('in_process', 'rework') or i.route_ids.filtered(lambda r: r.state != 'pending')):
            return 'in_process'
        return 'received'

    def _ki_update_state_from_items(self):
        now = fields.Datetime.now()
        became_ready = self.browse()
        became_delivered = self.browse()
        for order in self.filtered(lambda o: o.state in o._ki_process_states()):
            items = order.item_ids.filtered(lambda i: i.state not in ('cancelled', 'lost'))
            if not items:
                continue
            new_state = order._ki_state_from_items(items)
            if new_state == order.state:
                continue
            vals = {'state': new_state}
            if new_state == 'ready':
                if not order.date_ready:
                    vals['date_ready'] = now
                if not order.ready_notified:
                    vals['ready_notified'] = True
                    became_ready |= order
            if new_state == 'delivered':
                vals['date_delivered'] = now
                became_delivered |= order
            order.sudo().write(vals)
        became_ready._ki_send_mail('ready')
        became_delivered._ki_send_mail('delivered')

    # ------------------------------------------------------------------
    # Invoicing
    # ------------------------------------------------------------------

    def _ki_prepare_invoice_vals(self):
        self.ensure_one()
        partner = self.partner_invoice_id or self.partner_id
        return {
            'move_type': 'out_invoice',
            'partner_id': partner.id,
            'currency_id': self.currency_id.id,
            'company_id': self.company_id.id,
            'fiscal_position_id': self.fiscal_position_id.id,
            'invoice_payment_term_id': self.payment_term_id.id,
            'invoice_origin': self.name,
            'invoice_user_id': self.user_id.id,
            'narration': self.note,
            'invoice_line_ids': [],
        }

    def _ki_create_invoices(self, consolidate=False, advance_amount=0.0):
        """Create customer invoices for what remains to invoice.

        :param consolidate: one invoice per customer / currency / company for all orders.
        :param advance_amount: when set, invoice an advance of this amount on a single order instead.
        """
        for order in self:
            if order._ki_paid_elsewhere():
                raise UserError(self.env._(
                    "Order %s is paid through another channel and cannot be invoiced from here.", order.name))
            if order.state in ('draft', 'cancelled') and not order.is_stopped:
                raise UserError(self.env._("Receive order %s before invoicing it.", order.name))
        if advance_amount:
            self.ensure_one()
            return self._ki_create_advance_invoice(advance_amount)

        invoice_vals_list = []
        for order in self:
            lines = order.line_ids.filtered(
                lambda l: l.line_type != 'advance' and not float_is_zero(
                    l.qty_to_invoice, precision_rounding=l.product_uom_id.rounding or 0.01))
            if not lines:
                continue
            vals = order._ki_prepare_invoice_vals()
            line_vals = [line._ki_prepare_invoice_line(line.qty_to_invoice) for line in lines]
            for advance in order.line_ids.filtered(lambda l: l.line_type == 'advance' and l.qty_invoiced > 0):
                line_vals.append(advance._ki_prepare_invoice_line(-advance.qty_invoiced))
            vals['invoice_line_ids'] = [Command.create(v) for v in line_vals]
            invoice_vals_list.append(vals)
        if not invoice_vals_list:
            raise UserError(self.env._("There is nothing to invoice."))
        if consolidate:
            grouped = {}
            for vals in invoice_vals_list:
                key = (vals['company_id'], vals['partner_id'], vals['currency_id'], vals['fiscal_position_id'],
                       vals['invoice_payment_term_id'])
                if key in grouped:
                    grouped[key]['invoice_line_ids'] += vals['invoice_line_ids']
                    grouped[key]['invoice_origin'] += ', ' + vals['invoice_origin']
                else:
                    grouped[key] = vals
            invoice_vals_list = list(grouped.values())
        moves = self.env['account.move']
        for vals in invoice_vals_list:
            company = self.env['res.company'].browse(vals['company_id'])
            moves |= self.env['account.move'].sudo().with_company(company).with_context(
                default_move_type='out_invoice').create(vals)
        moves.filtered(lambda m: m.currency_id.compare_amounts(m.amount_total, 0.0) < 0).action_switch_move_type()
        self._ki_after_invoice(moves)
        return moves

    def _ki_create_advance_invoice(self, amount):
        self.ensure_one()
        if amount <= 0:
            raise UserError(self.env._("The advance amount must be positive."))
        remaining = self.amount_total - self._ki_net_invoiced()
        if self.currency_id.compare_amounts(amount, remaining) > 0:
            raise UserError(self.env._("The advance cannot exceed the amount left to invoice (%s).", remaining))
        product = self.company_id._ki_laundry_system_product('advance')
        line = self.env['ki.laundry.order.line'].with_context(ki_laundry_system=True).create({
            'order_id': self.id,
            'line_type': 'advance',
            'product_id': product.id,
            'name': self.env._("Advance payment - %s", self.name),
            'product_uom_qty': 0.0,
            'price_unit': amount,
            'price_is_manual': True,
            'sequence': 2000,
        })
        vals = self._ki_prepare_invoice_vals()
        vals['invoice_line_ids'] = [Command.create(line._ki_prepare_invoice_line(1.0))]
        move = self.env['account.move'].sudo().with_company(self.company_id).with_context(
            default_move_type='out_invoice').create(vals)
        self._ki_after_invoice(move)
        return move

    def _ki_after_invoice(self, moves):
        self.filtered(lambda o: not o.financial_path).write({'financial_path': 'invoice'})
        for order in self:
            order_moves = moves.filtered(lambda m: order in m.line_ids.ki_laundry_line_ids.order_id)
            if order_moves:
                order.message_post(body=self.env._(
                    "Invoice created: %s", ", ".join(order_moves.mapped('display_name'))))

    def action_view_invoices(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('account.action_move_out_invoice_type')
        invoices = self.invoice_ids
        if len(invoices) == 1:
            action['views'] = [(self.env.ref('account.view_move_form').id, 'form')]
            action['res_id'] = invoices.id
        else:
            action['domain'] = [('id', 'in', invoices.ids)]
        action['context'] = {'default_move_type': 'out_invoice'}
        return action

    def action_view_items(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'ki_laundry_management_base.action_laundry_order_item')
        action['domain'] = [('order_id', '=', self.id)]
        action['context'] = {'default_order_id': self.id, 'search_default_group_state': 0}
        return action

    # ------------------------------------------------------------------
    # Reports
    # ------------------------------------------------------------------

    def action_print_receipt(self):
        return self.env.ref('ki_laundry_management_base.action_report_laundry_receipt').report_action(self)

    def action_print_tags(self):
        items = self.item_ids.filtered(lambda i: i.state not in ('cancelled', 'lost'))
        if not items:
            raise UserError(self.env._("Receive the order first: tags are created when garments are received."))
        return self.env.ref('ki_laundry_management_base.action_report_laundry_tag').report_action(items)

    def _ki_receipt_groups(self):
        """Lines of the receipt grouped by intake (garment / load)."""
        self.ensure_one()
        groups = []
        for intake in self.intake_ids:
            groups.append({
                'label': intake._ki_label(),
                'services': ", ".join(intake.service_ids.mapped('name')),
                'addons': ", ".join(intake.addon_product_ids.mapped('name')),
                'quantity': intake._ki_display_quantity(),
                'amount': sum(intake.line_ids.mapped('price_total')),
            })
        charges = self.line_ids.filtered(lambda l: l.line_type not in ('service', 'addon', 'advance'))
        for line in charges:
            groups.append({
                'label': line.name, 'services': '', 'addons': '', 'quantity': '',
                'amount': line.price_total,
            })
        return groups

    # ------------------------------------------------------------------
    # Crons
    # ------------------------------------------------------------------

    @api.model
    def _ki_unclaimed_domain(self, company):
        """Ready orders waiting at the store (channel modules exclude home deliveries)."""
        return [('company_id', '=', company.id), ('state', '=', 'ready'), ('date_ready', '!=', False)]

    @api.model
    def _cron_send_reminders(self):
        for company in self.env['res.company'].search([]):
            days = company._ki_laundry_reminder_days()
            if not days:
                continue
            orders = self.search(self._ki_unclaimed_domain(company) + [('reminder_count', '<', len(days))])
            now = fields.Datetime.now()
            for order in orders:
                threshold = days[order.reminder_count]
                if order.date_ready + timedelta(days=threshold) <= now:
                    order.reminder_count += 1
                    order._ki_send_mail('reminder')

    @api.model
    def _cron_storage_fees(self):
        Line = self.env['ki.laundry.order.line'].with_context(ki_laundry_system=True)
        for company in self.env['res.company'].search([('ki_laundry_storage_fee_after_days', '>', 0)]):
            product = company._ki_laundry_system_product('storage', raise_if_missing=False)
            if not product:
                continue
            free_days = company.ki_laundry_storage_fee_after_days
            orders = self.search(self._ki_unclaimed_domain(company) + [
                ('date_ready', '<', fields.Datetime.now() - timedelta(days=free_days)),
                ('financial_path', 'in', [False, 'invoice']),
            ])
            for order in orders:
                days_over = (fields.Datetime.now() - order.date_ready).days - free_days
                if days_over <= 0:
                    continue
                line = order.line_ids.filtered(lambda l: l.line_type == 'storage')[:1]
                if line:
                    if line.qty_invoiced or line.product_uom_qty >= days_over:
                        continue
                    line.with_context(ki_laundry_system=True).write({'product_uom_qty': days_over})
                else:
                    Line.create({
                        'order_id': order.id,
                        'line_type': 'storage',
                        'product_id': product.id,
                        'name': self.env._("Storage fee (after %s free days)", free_days),
                        'product_uom_qty': days_over,
                        'sequence': 1500,
                    })
