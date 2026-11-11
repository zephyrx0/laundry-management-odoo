# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
#  Kalvyai | Laundry Management - Base
#  Copyright (c) 2026-Present Kalvyai (https://kalvyai.com)
#  License: OPL-1. See the LICENSE file.
# ----------------------------------------------------------------------------
from odoo import fields, models


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    ki_laundry_line_ids = fields.Many2many(
        'ki.laundry.order.line', 'ki_laundry_line_invoice_rel', 'invoice_line_id', 'laundry_line_id',
        string="Laundry Lines", copy=False, readonly=True)

    def _copy_data_extend_business_fields(self, values):
        # Keep the link on credit notes / duplicated invoices so invoiced quantities stay correct.
        super()._copy_data_extend_business_fields(values)
        values['ki_laundry_line_ids'] = [(6, None, self.sudo().ki_laundry_line_ids.ids)]
