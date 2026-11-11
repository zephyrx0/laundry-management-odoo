# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
#  Kalvyai | Laundry Management - Base
#  Copyright (c) 2026-Present Kalvyai (https://kalvyai.com)
#  License: OPL-1. See the LICENSE file.
# ----------------------------------------------------------------------------
from datetime import datetime, time, timedelta

from odoo import api, fields, models

OPEN_ITEM_STATES = ['pending', 'in_process', 'rework']
CLOSED_ORDER_STATES = ['delivered', 'cancelled']
PERIODS = ('today', 'week', 'month', 'year')


class LaundryDashboard(models.AbstractModel):
    """Data provider of the Laundry dashboard.

    The page shows key figures, the order flow, the work waiting at each
    station, the orders due today and the sales trend. The POS and Website
    modules extend ``_ki_dashboard_kpis`` / ``_ki_dashboard_sections``
    (calling super) and register a matching JS section, so their figures
    only show when they are installed.
    """
    _name = 'ki.laundry.dashboard'
    _description = "Laundry Dashboard"

    @api.model
    def get_data(self, period='week'):
        if period not in PERIODS:
            period = 'week'
        date_from, date_to = self._ki_period_bounds(period)
        user = self.env.user
        access = {
            'worker': user.has_group('ki_laundry_management_base.group_laundry_worker'),
            'user': user.has_group('ki_laundry_management_base.group_laundry_user'),
            'manager': user.has_group('ki_laundry_management_base.group_laundry_manager'),
        }
        company = self.env.company
        data = {
            'period': period,
            'access': access,
            'currency': {
                'id': company.currency_id.id,
                'symbol': company.currency_id.symbol,
                'position': company.currency_id.position,
                'digits': company.currency_id.decimal_places,
            },
            'kpis': self._ki_dashboard_kpis(date_from, date_to, access),
            'pipeline': self._ki_dashboard_pipeline(date_from, date_to),
            'steps': self._ki_dashboard_steps(),
            'due': self._ki_dashboard_due(),
            'sections': self._ki_dashboard_sections(date_from, date_to, access),
        }
        if access['user']:
            data['trend'] = self._ki_dashboard_trend(date_from, date_to, period)
            data['services'] = self._ki_dashboard_services(date_from, date_to)
        return data

    # ------------------------------------------------------------------
    # Dates
    # ------------------------------------------------------------------

    @api.model
    def _ki_period_bounds(self, period):
        """UTC bounds of the period, computed in the user's timezone."""
        today = fields.Date.context_today(self)
        if period == 'today':
            start = today
        elif period == 'week':
            start = today - timedelta(days=6)
        elif period == 'month':
            start = today - timedelta(days=29)
        else:
            start = today.replace(day=1, month=1)
        return self._ki_to_utc(start), self._ki_to_utc(today + timedelta(days=1))

    @api.model
    def _ki_to_utc(self, day):
        return self._ki_local_to_utc(datetime.combine(day, time.min))

    @api.model
    def _ki_local_to_utc(self, local_dt):
        """Naive local datetime (user timezone) -> naive UTC datetime."""
        offset = fields.Datetime.context_timestamp(self, local_dt).utcoffset() or timedelta()
        return local_dt - offset

    # ------------------------------------------------------------------
    # Blocks
    # ------------------------------------------------------------------

    @api.model
    def _ki_card(self, key, label, value, model, domain, icon, tone, money=False, hint=''):
        """A clickable figure: ``domain`` on ``model`` opens the records behind it."""
        return {'key': key, 'label': label, 'value': value, 'model': model, 'domain': domain,
                'icon': icon, 'tone': tone, 'money': money, 'hint': hint}

    @api.model
    def _ki_dashboard_kpis(self, date_from, date_to, access):
        """The 4 key figures at the top. Override with super() to add some."""
        _ = self.env._
        Order = self.env['ki.laundry.order']
        order = 'ki.laundry.order'
        period = [('date_order', '>=', date_from), ('date_order', '<', date_to)]
        ready = [('state', '=', 'ready')]
        late = [('is_late', '=', True)]
        kpis = []
        if access['user']:
            billed = period + [('state', 'not in', ['draft', 'cancelled'])]
            revenue = Order._read_group(billed, aggregates=['amount_untaxed:sum'])[0][0] or 0.0
            kpis += [
                self._ki_card('revenue', _("Revenue"), revenue, order, billed, 'fa-money', 'success',
                              money=True, hint=_("untaxed")),
                self._ki_card('orders', _("Orders"), Order.search_count(period + [('state', '!=', 'cancelled')]),
                              order, period + [('state', '!=', 'cancelled')], 'fa-shopping-basket', 'primary'),
            ]
        else:
            Item = self.env['ki.laundry.order.item']
            open_items = [('state', 'in', OPEN_ITEM_STATES)]
            kpis += [
                self._ki_card('items', _("Garments in Process"), Item.search_count(open_items),
                              'ki.laundry.order.item', open_items, 'fa-refresh', 'primary'),
                self._ki_card('urgent', _("Urgent Garments"),
                              Item.search_count(open_items + [('is_urgent', '=', True)]),
                              'ki.laundry.order.item', open_items + [('is_urgent', '=', True)], 'fa-bolt', 'warning'),
            ]
        kpis += [
            self._ki_card('ready', _("Ready to Collect"), Order.search_count(ready), order, ready,
                          'fa-check-circle', 'info'),
            self._ki_card('late', _("Late Orders"), Order.search_count(late), order, late,
                          'fa-clock-o', 'danger'),
        ]
        return kpis

    @api.model
    def _ki_dashboard_pipeline(self, date_from, date_to):
        """Open orders at each stage of the flow, then orders delivered in the period."""
        _ = self.env._
        Order = self.env['ki.laundry.order']
        counts = dict(Order._read_group([('state', 'not in', CLOSED_ORDER_STATES)], ['state'], ['__count']))
        state_labels = dict(Order._fields['state']._description_selection(self.env))
        stages = []
        for state in Order._ki_pre_receive_states():
            stages.append({'key': state, 'label': state_labels.get(state, state), 'states': [state]})
        stages += [
            {'key': 'received', 'label': _("Received"), 'states': ['received']},
            {'key': 'in_process', 'label': _("In Process"), 'states': ['in_process', 'partially_ready']},
            {'key': 'ready', 'label': _("Ready"), 'states': ['ready']},
        ]
        pipeline = [{
            'key': stage['key'],
            'label': stage['label'],
            'count': sum(counts.get(s, 0) for s in stage['states']),
            'domain': [('state', 'in', stage['states'])],
        } for stage in stages]
        delivered = [('state', '=', 'delivered'), ('date_delivered', '>=', date_from), ('date_delivered', '<', date_to)]
        pipeline.append({'key': 'delivered', 'label': _("Delivered"), 'count': Order.search_count(delivered),
                         'domain': delivered})
        return pipeline

    @api.model
    def _ki_dashboard_steps(self):
        """Garments waiting at each process station."""
        Item = self.env['ki.laundry.order.item']
        open_domain = [('state', 'in', OPEN_ITEM_STATES)]
        groups = Item._read_group(open_domain + [('current_step_id', '!=', False)],
                                  groupby=['current_step_id'], aggregates=['__count'])
        groups = sorted(groups, key=lambda g: (g[0].sequence, g[0].id))
        return [{
            'id': step.id,
            'name': step.display_name,
            'count': count,
            'domain': open_domain + [('current_step_id', '=', step.id)],
        } for step, count in groups]

    @api.model
    def _ki_dashboard_due(self, limit=8):
        """Open orders due before the end of today, the most urgent first."""
        today_end = self._ki_to_utc(fields.Date.context_today(self) + timedelta(days=1))
        Order = self.env['ki.laundry.order']
        domain = [('state', 'not in', CLOSED_ORDER_STATES + ['draft']), ('date_due', '<', today_end)]
        orders = Order.search(domain, order='date_due, id', limit=limit)
        state_labels = dict(Order._fields['state']._description_selection(self.env))
        return {
            'count': Order.search_count(domain),
            'domain': domain,
            'orders': [{
                'id': order.id,
                'name': order.name,
                'customer': order.partner_id.display_name,
                'date_due': fields.Datetime.to_string(order.date_due),
                'state': order.state,
                'state_label': state_labels.get(order.state, order.state),
                'is_late': order.is_late,
                'is_urgent': order.is_urgent,
                'items_ready': order.item_ready_count,
                'items': order.item_count,
            } for order in orders],
        }

    @api.model
    def _ki_dashboard_trend(self, date_from, date_to, period):
        Order = self.env['ki.laundry.order']
        billed = [('date_order', '>=', date_from), ('date_order', '<', date_to),
                  ('state', 'not in', ['draft', 'cancelled'])]
        interval = {'today': 'hour', 'week': 'day', 'month': 'day', 'year': 'month'}[period]
        groups = Order._read_group(billed, groupby=[f'date_order:{interval}'], aggregates=['amount_untaxed:sum'])
        return [{'label': self._ki_format_bucket(bucket, interval), 'amount': amount or 0.0}
                for bucket, amount in groups]

    @api.model
    def _ki_format_bucket(self, bucket, interval):
        if not bucket:
            return ''
        if interval == 'hour':
            return fields.Datetime.context_timestamp(self, bucket).strftime('%H:00')
        if interval == 'day':
            return bucket.strftime('%d %b')
        return bucket.strftime('%b %Y')

    @api.model
    def _ki_dashboard_services(self, date_from, date_to, limit=5):
        """Best selling services of the period."""
        Line = self.env['ki.laundry.order.line']
        domain = [('order_id.date_order', '>=', date_from), ('order_id.date_order', '<', date_to),
                  ('state', 'not in', ['draft', 'cancelled']), ('line_type', '=', 'service')]
        groups = Line._read_group(domain, groupby=['product_tmpl_id'], aggregates=['price_subtotal:sum'],
                                  order='price_subtotal:sum desc', limit=limit)
        return [{
            'name': service.display_name,
            'amount': amount or 0.0,
            'domain': domain + [('product_tmpl_id', '=', service.id)],
        } for service, amount in groups if service]

    @api.model
    def _ki_dashboard_sections(self, date_from, date_to, access):
        """Extra sections ``{key: data}`` added by other modules (POS, Website). Empty here."""
        return {}
