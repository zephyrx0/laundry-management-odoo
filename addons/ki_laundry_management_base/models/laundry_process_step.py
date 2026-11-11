# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
#  Kalvyai | Laundry Management - Base
#  Copyright (c) 2026-Present Kalvyai (https://kalvyai.com)
#  License: OPL-1. See the LICENSE file.
# ----------------------------------------------------------------------------
from odoo import fields, models


class LaundryProcessStep(models.Model):
    _name = 'ki.laundry.process.step'
    _description = "Laundry Process Step"
    _order = 'sequence, id'

    name = fields.Char(required=True, translate=True)
    code = fields.Char()
    sequence = fields.Integer(
        required=True, default=50,
        help="Global position of the step. Routes of combined services are merged and sorted on it.",
    )
    step_type = fields.Selection(
        [('intake', "Intake / Inspection"), ('process', "Processing"), ('qc', "Quality Check"),
         ('pack', "Packing")],
        string="Type", default='process', required=True,
    )
    allow_skip = fields.Boolean(string="Can Be Skipped", help="Workers may skip this step without a manager.")
    color = fields.Integer()
    company_id = fields.Many2one('res.company', string="Company", index=True,
                                 help="Leave empty to share the step between companies.")
    active = fields.Boolean(default=True)
