from odoo import api, models, fields
from datetime import datetime, timedelta
import logging
_logger = logging.getLogger(__name__)

class StockLotInherit(models.Model):
    _inherit = 'stock.lot'
    _description = 'Inherit Inventory Module'

    expiration_date = fields.Datetime(string='Expiration Date', compute='_check_the_date', store=True, readonly=False, help='This is the date on which the goods with this Serial Number may become dangerous and must not be consumed.')
    expired_state = fields.Char(string="Expiration Status", default="NOTEXPIRED", store=True, compute="_check_the_date")
    is_active = fields.Boolean(string="Active", default=True)

    @api.depends('expiration_date')
    def _check_the_date(self):
        current_date = datetime.now().date()
        _logger.info("Current Date---->%s", current_date)
        new_date = current_date + timedelta(days=30)
        _logger.info("New Date---->%s", new_date)
        for rec in self:
            expiration_date = rec.expiration_date.date()
            _logger.info("Expiration Date---->%s", expiration_date)
            if expiration_date <= current_date:
                rec.expired_state = "EXPIRED"
            elif expiration_date > current_date and expiration_date <= new_date:
                rec.expired_state = "TOEXPIRED"
            else:
                rec.expired_state = "NOTEXPIRED"

    def lotCheckFunction(self):
        self.env.cr.execute("update stock_lot set expired_state = 'EXPIRED' where expiration_date <= now();")
        self.env.cr.execute("update stock_lot set expired_state = 'TOEXPIRED' where expiration_date > now() and expiration_date <= (now() + interval '30 days');")
        self.env.cr.execute("update stock_lot set expired_state = 'NOTEXPIRED' where expiration_date > (now() + interval '30 days');")


