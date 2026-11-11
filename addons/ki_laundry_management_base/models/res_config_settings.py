# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
#  Kalvyai | Laundry Management - Base
#  Copyright (c) 2026-Present Kalvyai (https://kalvyai.com)
#  License: OPL-1. See the LICENSE file.
# ----------------------------------------------------------------------------
from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    ki_laundry_calendar_id = fields.Many2one(related='company_id.ki_laundry_calendar_id', readonly=False)
    ki_laundry_payment_policy = fields.Selection(related='company_id.ki_laundry_payment_policy', readonly=False)
    ki_laundry_advance_percent = fields.Float(related='company_id.ki_laundry_advance_percent', readonly=False)
    ki_laundry_urgent_product_id = fields.Many2one(related='company_id.ki_laundry_urgent_product_id', readonly=False)
    ki_laundry_advance_product_id = fields.Many2one(related='company_id.ki_laundry_advance_product_id',
                                                    readonly=False)
    ki_laundry_storage_product_id = fields.Many2one(related='company_id.ki_laundry_storage_product_id',
                                                    readonly=False)
    ki_laundry_receipt_layout = fields.Selection(related='company_id.ki_laundry_receipt_layout', readonly=False)
    ki_laundry_require_scan_on_delivery = fields.Boolean(
        related='company_id.ki_laundry_require_scan_on_delivery', readonly=False)
    ki_laundry_reminder_days = fields.Char(related='company_id.ki_laundry_reminder_days', readonly=False)
    ki_laundry_storage_fee_after_days = fields.Integer(
        related='company_id.ki_laundry_storage_fee_after_days', readonly=False)
    # Storage fee is on when free days > 0: the toggle only drives that number.
    ki_laundry_storage_fee = fields.Boolean(
        string="Storage Fee", compute='_compute_ki_laundry_storage_fee', readonly=False)
    ki_laundry_terms = fields.Html(related='company_id.ki_laundry_terms', readonly=False)
    ki_laundry_mail_received = fields.Boolean(related='company_id.ki_laundry_mail_received', readonly=False)
    ki_laundry_mail_ready = fields.Boolean(related='company_id.ki_laundry_mail_ready', readonly=False)
    ki_laundry_mail_delivered = fields.Boolean(related='company_id.ki_laundry_mail_delivered', readonly=False)
    ki_laundry_mail_reminder = fields.Boolean(related='company_id.ki_laundry_mail_reminder', readonly=False)

    @api.depends('ki_laundry_storage_fee_after_days')
    def _compute_ki_laundry_storage_fee(self):
        for settings in self:
            settings.ki_laundry_storage_fee = settings.ki_laundry_storage_fee_after_days > 0

    @api.onchange('ki_laundry_storage_fee')
    def _onchange_ki_laundry_storage_fee(self):
        if not self.ki_laundry_storage_fee:
            self.ki_laundry_storage_fee_after_days = 0
        elif not self.ki_laundry_storage_fee_after_days:
            self.ki_laundry_storage_fee_after_days = 30
