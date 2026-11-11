# -*- coding: utf-8 -*-
# ============================================================================
#
#   Kalvyai | Laundry Management - Base
#
#   Company
#   -------
#   Author         : Kalvyai
#   Maintainer     : Kalvyai
#   Website        : https://kalvyai.com
#   Support        : support@kalvyai.com
#
#   Copyright (c) 2026-Present Kalvyai (https://kalvyai.com)
#   License: Other proprietary. See the LICENSE file.
#
# ============================================================================
{
    'name': (
        'Laundry & Dry Cleaning Management | Laundromat Orders, Garment Tags, Per-Kg Pricing'
    ),
    'version': '1.0.0',
    'category': 'Services/Laundry',
    'summary': (
        'Run a laundry, dry cleaning or laundromat business in Odoo: orders, pickup, garment '
        'barcode tags, workstation tracking, wash and fold, ironing, per-piece and per-kg pricing'
        ' and invoicing. laundry | laundry management | laundry software | laundry system | '
        'laundry app | laundry shop | laundry service | laundry business | dry cleaning | '
        'dry cleaner | dry cleaning software | laundromat | wash and fold | ironing | '
        'laundry pickup | laundry order | garment tag | garment barcode | clothes tracking | '
        'workstation tracking | laundry pricing | per kg pricing | per piece pricing | '
        'laundry invoice | due date'
    ),
    'description': """
Laundry Management (Base)
=========================
The core of a laundry or dry cleaning shop. The Point of Sale and Website
modules build on it (counter sales, online booking, home pickup and delivery).

* Garments and services with a simple price screen (per piece or per kg)
* Counter orders: receive garments, print the receipt and one tag per garment
* Station tracking: scan tags at each station (Wash, Iron, Pack...) until ready
* Clear dashboard: order flow, garments at each station, orders due today, sales
* Due dates from turnaround times, working hours and holidays
* Invoices, advances and double-invoicing protection
* Urgent surcharge, add-ons, seasonal offers, unclaimed reminders, storage fees
* E-mails when garments are received, ready and delivered
""",
    'author': 'Kalvyai',
    'maintainer': 'Kalvyai',
    'website': 'https://kalvyai.com',
    'support': 'support@kalvyai.com',
    'license': 'Other proprietary',
    'depends': ['mail', 'product', 'account', 'barcodes', 'resource'],
    'data': [
        'security/laundry_security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'data/product_data.xml',
        'data/laundry_process_step_data.xml',
        'data/mail_template_data.xml',
        'data/ir_cron_data.xml',
        'report/report_paperformat.xml',
        'report/report_laundry_order.xml',
        'report/report_laundry_receipt.xml',
        'report/report_laundry_tag.xml',
        'report/laundry_reports.xml',
        'wizard/laundry_intake_split_wizard_views.xml',
        'wizard/laundry_weigh_wizard_views.xml',
        'wizard/laundry_cancel_wizard_views.xml',
        'wizard/laundry_invoice_wizard_views.xml',
        'wizard/laundry_deliver_wizard_views.xml',
        'wizard/laundry_rework_wizard_views.xml',
        'views/laundry_client_actions.xml',
        'views/laundry_process_step_views.xml',
        'views/laundry_garment_views.xml',
        'views/product_template_views.xml',
        'views/laundry_order_views.xml',
        'views/laundry_order_item_views.xml',
        'views/laundry_offer_views.xml',
        'views/res_partner_views.xml',
        'views/account_move_views.xml',
        'views/res_config_settings_views.xml',
        'views/laundry_menus.xml',
    ],
    'demo': [
        'demo/laundry_demo.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'ki_laundry_management_base/static/src/scss/laundry_backend.scss',
            'ki_laundry_management_base/static/src/price_grid/*',
            'ki_laundry_management_base/static/src/workstation/*',
            'ki_laundry_management_base/static/src/dashboard/*',
        ],
    },
    'images': ['static/description/banner.gif'],
    'application': True,
    'installable': True,
    #'price': 9.99,
    #'currency': 'USD',
}
