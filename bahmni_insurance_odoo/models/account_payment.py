from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

class AccountPaymentInherit(models.Model):
    _inherit = 'account.payment'
    _description = 'Account Payment Inherit'

    move_ref = fields.Char(string="Invoice Number", related="move_id.ref", store=False)

