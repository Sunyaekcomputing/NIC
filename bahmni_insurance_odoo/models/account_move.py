from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import base64
import logging
_logger = logging.getLogger(__name__)

class AccountMoveInherit(models.Model):
    _name = 'account.move'
    _inherit = 'account.move'

    move_payment_type = fields.Selection(string="Payment Type", related="order_id.payment_type", readonly=False)

    # @api.model
    # def _get_payment_type_data(self):
    #     returnData = []
    #     payment_type_ids = self.env['payment.types'].search([])
    #     if payment_type_ids:
    #         for pt in payment_type_ids:
    #             data = payment_type_ids.browse(pt.id)
    #             returnData.append((data.key, data.value))
    #     return returnData

    def action_register_payment(self):
        ''' Open the account.payment.register wizard to pay the selected journal entries.
        :return: An action opening the account.payment.register wizard.
        '''
        for rec in self:
            if rec.move_type == "out_invoice" or rec.move_type == "out_refund":
                _logger.info("If running")
                _logger.info("Move Type:%s", rec.move_type)
                payment_type = rec.move_payment_type
                if payment_type:
                    _logger.info("Payment Type:%s", payment_type)
                    journal_id = rec.env['payment.journal.mapping'].search([
                        ('payment_type', '=', payment_type)
                    ]).journal_id.id
                    _logger.info("Journal Id:%s", journal_id)
                    if not journal_id:
                        raise UserError("Please define a journal for this company")
            
                    return {
                        'name': _('Register Payment'),
                        'res_model': 'account.payment.register',
                        'view_mode': 'form',
                        'context': {
                            'active_model': 'account.move',
                            'active_ids': self.ids,
                            'default_journal_id': journal_id
                        },
                        'target': 'new',
                        'type': 'ir.actions.act_window',
                    }
            else:
                _logger.info("Else Running")
                _logger.info("Move Type:%s", rec.move_type)
                journal_id = rec.env['payment.journal.mapping'].search([
                    ('payment_type', '=', 'cash')
                    ]).journal_id.id
                _logger.info("Journal Id:%s", journal_id)
                if not journal_id:
                    raise UserError("Please define a journal for this company")
            
                return {
                    'name': _('Register Payment'),
                    'res_model': 'account.payment.register',
                    'view_mode': 'form',
                    'context': {
                        'active_model': 'account.move',
                        'active_ids': self.ids,
                        'default_journal_id': journal_id
                    },
                    'target': 'new',
                    'type': 'ir.actions.act_window',
                }

    def action_generate_attachment(self, account_id, claim_id):
        _logger.info("Inside action_generate_attachment")

        report_name = 'account.account_invoices' #default odoo report

        pdf = self.env['ir.actions.report']._render_qweb_pdf(
            report_name, 
            account_id.ids
        )[0]
        _logger.info("PDF:%s", pdf)

        b64_pdf = base64.b64encode(pdf)

        _logger.info("Encoded PDF:%s", b64_pdf)

        # Attachment Name
        attachment_name = account_id.name
        _logger.info("Attachment Name:%s", attachment_name)

        # Patient Information
        patient_information = f"{account_id.partner_id.name} {account_id.payment_reference}"
        _logger.info("Patient Info:%s", patient_information)

        # Create Attachment
        attachment_value = {
            'name': patient_information,
            'type': 'binary',
            'datas': b64_pdf,
            'store_fname': f"{attachment_name}.pdf",
            "res_model": account_id._name,
            "res_id": account_id.id,
            "mimetype": 'application/pdf'
        }
        _logger.info("Attachment Value:%s", attachment_value)

        attachment = self.env['ir.attachment'].create(attachment_value)
  
        _logger.info("Created Attachment Id:%s", attachment.id)

        # Add to insurance claim line
        claim = self.env['insurance.claim'].browse(claim_id.id)
        _logger.info("Claim Id:%s", claim)
        claim.write({
            'attachment_ids': [(4, attachment.id)]
        })
        _logger.info("Attachment added to the insurance claim line")        
        