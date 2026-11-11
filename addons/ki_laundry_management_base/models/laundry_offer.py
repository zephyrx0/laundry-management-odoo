# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
#  Kalvyai | Laundry Management - Base
#  Copyright (c) 2026-Present Kalvyai (https://kalvyai.com)
#  License: OPL-1. See the LICENSE file.
# ----------------------------------------------------------------------------
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class LaundryOffer(models.Model):
    _name = 'ki.laundry.offer'
    _description = "Laundry Offer"
    _inherit = ['mail.thread']
    _order = 'date_start desc, id desc'
    _check_company_auto = True

    name = fields.Char(required=True, translate=True, tracking=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company, index=True)
    pricelist_id = fields.Many2one('product.pricelist', required=True, check_company=True, tracking=True,
                                   ondelete='cascade')
    service_ids = fields.Many2many(
        'product.template', 'ki_laundry_offer_service_rel', 'offer_id', 'product_tmpl_id',
        string="Services", required=True, domain="[('ki_laundry_is_service', '=', True)]")
    garment_ids = fields.Many2many(
        'ki.laundry.garment', 'ki_laundry_offer_garment_rel', 'offer_id', 'garment_id',
        string="Garments", help="Leave empty to apply the offer to every garment of the selected services.")
    discount = fields.Float(string="Discount (%)", required=True, default=10.0, tracking=True)
    date_start = fields.Datetime(string="Start", tracking=True)
    date_end = fields.Datetime(string="End", tracking=True)
    state = fields.Selection([('draft', "Draft"), ('active', "Active"), ('expired', "Expired")],
                             default='draft', required=True, readonly=True, tracking=True, copy=False)
    pricelist_item_ids = fields.One2many('product.pricelist.item', 'ki_laundry_offer_id', string="Pricelist Rules",
                                         readonly=True)
    rule_count = fields.Integer(compute='_compute_rule_count')

    @api.depends('pricelist_item_ids')
    def _compute_rule_count(self):
        for offer in self:
            offer.rule_count = len(offer.pricelist_item_ids)

    @api.constrains('discount', 'date_start', 'date_end')
    def _check_values(self):
        for offer in self:
            if not 0 < offer.discount <= 100:
                raise ValidationError(self.env._("The discount must be between 0 and 100%."))
            if offer.date_start and offer.date_end and offer.date_start >= offer.date_end:
                raise ValidationError(self.env._("The offer must end after it starts."))

    def write(self, vals):
        result = super().write(vals)
        if {'service_ids', 'garment_ids', 'discount', 'date_start', 'date_end', 'pricelist_id'} & set(vals):
            self.filtered(lambda o: o.state == 'active')._ki_rebuild_rules()
        return result

    def _ki_rebuild_rules(self):
        Item = self.env['product.pricelist.item'].sudo()
        for offer in self:
            offer.pricelist_item_ids.sudo().unlink()
            vals_list = []
            common = {
                'pricelist_id': offer.pricelist_id.id,
                'compute_price': 'percentage',
                'percent_price': offer.discount,
                'date_start': offer.date_start,
                'date_end': offer.date_end,
                'ki_laundry_offer_id': offer.id,
            }
            for service in offer.service_ids:
                if not offer.garment_ids or not service._ki_laundry_garment_line():
                    if offer.garment_ids and not service._ki_laundry_garment_line():
                        continue
                    vals_list.append(dict(common, applied_on='1_product', product_tmpl_id=service.id))
                    continue
                for variant in service.product_variant_ids:
                    if variant.ki_laundry_garment_id in offer.garment_ids:
                        vals_list.append(dict(common, applied_on='0_product_variant', product_id=variant.id,
                                              product_tmpl_id=service.id))
            if not vals_list:
                raise UserError(self.env._(
                    "Offer %s matches no service variant. Check the selected services and garments.", offer.name))
            Item.create(vals_list)

    def action_apply(self):
        if not self.env['res.groups']._is_feature_enabled('product.group_product_pricelist'):
            raise UserError(self.env._(
                "Offers are applied through pricelists. Enable 'Pricelists' in the Sales or Point of Sale "
                "settings first."))
        for offer in self:
            if offer.date_end and offer.date_end < fields.Datetime.now():
                raise UserError(self.env._("Offer %s has already ended.", offer.name))
        self._ki_rebuild_rules()
        self.write({'state': 'active'})
        return True

    def action_remove(self):
        self.pricelist_item_ids.sudo().unlink()
        self.write({'state': 'draft'})
        return True

    @api.ondelete(at_uninstall=False)
    def _unlink_rules(self):
        self.pricelist_item_ids.sudo().unlink()

    @api.model
    def _cron_expire_offers(self):
        self.search([('state', '=', 'active'), ('date_end', '!=', False),
                     ('date_end', '<', fields.Datetime.now())]).write({'state': 'expired'})
