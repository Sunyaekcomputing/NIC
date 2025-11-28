from odoo import api, models, fields

class PaymentJournalMapping(models.Model):
    _name = 'payment.journal.mapping'

    payment_type = fields.Selection(selection="_get_payment_type_data", string="Payment Type", default="cash")
    journal_id = fields.Many2one('account.journal', string="Journal", tracking=True)

    @api.model
    def _get_payment_type_data(self):
        resultData = []
        payment_type_ids = self.env['payment.types'].search([])
        if payment_type_ids:
            for pt in payment_type_ids:
                data = payment_type_ids.browse(pt.id)
                resultData.append((data.key, data.value))
        return resultData
