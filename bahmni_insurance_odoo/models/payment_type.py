from odoo import api, models, fields

class PaymentType(models.Model):
    _name = 'payment.types'
    _description = 'Payment Types'

    key = fields.Char(string="Payment Type Key")
    value = fields.Char(string="Payment Type")

    @api.model
    def name_get(self):
        result = []
        for rec in self:
            record_name = rec.value
            result.append((rec.id, record_name))
        return result
