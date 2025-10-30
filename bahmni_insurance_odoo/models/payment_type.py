from odoo import api, models, fields

class PaymentType(models.Model):
    _name = 'payment.types'
    _description = 'Payment Types'
    _rec_name = 'payment_type_key'

    payment_type_key = fields.Char(string="Payment Type Key")
    payment_type = fields.Char(string="Payment Type")