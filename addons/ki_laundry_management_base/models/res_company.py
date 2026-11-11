# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
#  Kalvyai | Laundry Management - Base
#  Copyright (c) 2026-Present Kalvyai (https://kalvyai.com)
#  License: OPL-1. See the LICENSE file.
# ----------------------------------------------------------------------------
import re
from datetime import timedelta

import pytz

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

SYSTEM_PRODUCTS = {
    'urgent': ('ki_laundry_urgent_product_id', 'ki_laundry_management_base.product_laundry_urgent'),
    'advance': ('ki_laundry_advance_product_id', 'ki_laundry_management_base.product_laundry_advance'),
    'storage': ('ki_laundry_storage_product_id', 'ki_laundry_management_base.product_laundry_storage'),
}


class ResCompany(models.Model):
    _inherit = 'res.company'

    ki_laundry_calendar_id = fields.Many2one(
        'resource.calendar', string="Laundry Working Hours",
        help="Due dates falling outside working hours or on holidays move to the next working time.")
    ki_laundry_payment_policy = fields.Selection(
        [('prepaid', "Pay at Drop-off"), ('on_collection', "Pay at Collection"),
         ('advance', "Advance + Balance"), ('credit', "On Credit (Invoice)")],
        string="Default Payment Policy", default='on_collection')
    ki_laundry_advance_percent = fields.Float(string="Default Advance (%)", default=50.0)
    ki_laundry_urgent_product_id = fields.Many2one('product.product', string="Urgent Surcharge Product")
    ki_laundry_advance_product_id = fields.Many2one('product.product', string="Advance Product")
    ki_laundry_storage_product_id = fields.Many2one('product.product', string="Storage Fee Product")
    ki_laundry_receipt_layout = fields.Selection(
        [('grouped', "Grouped by garment"), ('detailed', "One line per service")],
        string="Receipt Layout", default='grouped')
    ki_laundry_require_scan_on_delivery = fields.Boolean(string="Scan Tags on Delivery")
    ki_laundry_reminder_days = fields.Char(
        string="Reminder Days", default="7,14",
        help="Days after an order is ready to remind the customer, e.g. 7,14,30. Empty to disable.")
    ki_laundry_storage_fee_after_days = fields.Integer(
        string="Storage Fee After (Days)", help="Charge a daily storage fee after this many days (0 = never).")
    ki_laundry_terms = fields.Html(string="Laundry Terms", translate=True, sanitize=True)
    ki_laundry_mail_received = fields.Boolean(string="Mail on Reception", default=True)
    ki_laundry_mail_ready = fields.Boolean(string="Mail when Ready", default=True)
    ki_laundry_mail_delivered = fields.Boolean(string="Mail on Delivery", default=True)
    ki_laundry_mail_reminder = fields.Boolean(string="Unclaimed Reminders", default=True)

    @api.constrains('ki_laundry_reminder_days', 'ki_laundry_advance_percent', 'ki_laundry_storage_fee_after_days')
    def _check_ki_laundry_settings(self):
        for company in self:
            if company.ki_laundry_reminder_days and not re.fullmatch(
                    r'\s*\d+\s*(,\s*\d+\s*)*', company.ki_laundry_reminder_days):
                raise ValidationError(self.env._("Reminder days must be a comma separated list of numbers."))
            if not 0 <= company.ki_laundry_advance_percent <= 100:
                raise ValidationError(self.env._("The advance percentage must be between 0 and 100."))
            if company.ki_laundry_storage_fee_after_days < 0:
                raise ValidationError(self.env._("Storage fee days cannot be negative."))

    def _ki_laundry_reminder_days(self):
        self.ensure_one()
        if not self.ki_laundry_mail_reminder or not self.ki_laundry_reminder_days:
            return []
        return sorted({int(day) for day in re.findall(r'\d+', self.ki_laundry_reminder_days) if int(day) > 0})

    def _ki_laundry_tz(self):
        self.ensure_one()
        tz = self.ki_laundry_calendar_id.tz or self.resource_calendar_id.tz or self.env.user.tz or 'UTC'
        return tz if tz in pytz.all_timezones_set else 'UTC'

    def _ki_laundry_plan(self, start, hours):
        """Due date ``hours`` after ``start``, moved to the next working time of the laundry calendar."""
        self.ensure_one()
        due = start + timedelta(hours=hours or 0.0)
        calendar = self.ki_laundry_calendar_id
        if not calendar:
            return due
        try:
            planned = calendar.plan_hours(0.0, due, compute_leaves=True)
        except Exception:  # noqa: BLE001 - never block an order on an exotic calendar configuration
            planned = False
        return planned or due

    def _ki_laundry_system_product(self, code, raise_if_missing=True):
        self.ensure_one()
        field_name, xmlid = SYSTEM_PRODUCTS[code]
        product = self[field_name] or self.env.ref(xmlid, raise_if_not_found=False)
        if product and not product.active:
            product = self.env['product.product']
        if not product and raise_if_missing:
            raise UserError(self.env._(
                "The laundry '%s' product is missing. Set it in Laundry > Configuration > Settings.", code))
        return product or self.env['product.product']
