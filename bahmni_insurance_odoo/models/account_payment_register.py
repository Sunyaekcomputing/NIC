from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import logging
_logger = logging.getLogger(__name__)

class AccountPaymentRegisterInherit(models.TransientModel):
    _inherit = 'account.payment.register'
    _description = 'Account Payment Register Inherit'
        
    def action_create_payments(self):
        _logger.info("Inside Action Create Payment")
        payments = self._create_payments()

        if self._context.get('dont_redirect_to_payments'):
            _logger.info("Don't Redirect to payment")
            return True
        
        if self.env.user.has_group('bahmni_sale.group_redirect_to_payments_on_sale_confirm'):
            _logger.info("Group_redirect_to_payments_on_sale_confirm ")
            return True
        
        action = {
            'name': _('Payments'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.payment',
            'context': {'create': False},
        }
        if len(payments) == 1:
            action.update({
                'view_mode': 'form',
                'res_id': payments.id,
            })
        else:
            action.update({
                'view_mode': 'tree,form',
                'domain': [('id', 'in', payments.ids)],
            })
        return action
        

 