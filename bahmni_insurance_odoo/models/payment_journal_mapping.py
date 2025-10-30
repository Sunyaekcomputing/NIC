from odoo import api, models, fields

class PaymentJournalMapping(models.Model):
    _name = 'payment.journal.mapping'

    payment_type = fields.Many2one('payment.types', string="Payment Type")
    journal_ids = fields.Many2one('account.journal', string="Journal")