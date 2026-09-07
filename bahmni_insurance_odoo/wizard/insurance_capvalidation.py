from odoo import api, fields, models
from odoo.exceptions import UserError
import logging  
_logger = logging.getLogger(__name__)

class InsuranceCapvalidation(models.TransientModel):
    _name = 'insurance.capvalidation'
    _description = 'Insurance Capvalidation'

    nhis_number = fields.Char(string="NHIS Number")
    code = fields.Char(string="Code")
    name = fields.Char(string="Name")
    cap_qty_peroid = fields.Integer(string="Cap Quantity")
    cap_qrst_peroid = fields.Integer(string="Cap Peroid")
    type = fields.Char(string="Product Type")
    qty_used = fields.Float(string="Quantity Used")
    qty_remain = fields.Float(string="Remaining Quantity")

    def get_cap_validation(self, partner_id):
        _logger.info("Inside Get Cap Validation")
        nhis_number = self.env['res.partner']._get_nhis_number(partner_id.id)
        _logger.info("NHIS Number:%s", nhis_number)
        cap_data_list = []
        if nhis_number:
            response = self.env['insurance.connect']._get_capvalidation(nhis_number)
            _logger.info("Response:%s", response)
            if response:
                for res in response:
                    cap_validation_data = {
                        'nhis_number': res['nhisId'],
                        'code': res['code'],
                        'name': res['name'],
                        'cap_qty_peroid': res['capQtyPeroid'], # Cap Quantity in number
                        'cap_qrst_peroid': res['capQrstPeroid'], # Cap peroid in days
                        'type': res['itemServ'],
                        'qty_used': res['qtyUsed'], # used quantity in number
                        'qty_remain': res['qtyRemain'] # remaining quantity in number
                    }
                    self.env['insurance.capvalidation'].create(cap_validation_data)
                    cap_data_list.append(cap_validation_data)
                return cap_data_list      
            else:
                _logger.info("No response from the IMIS Server")
        else:
            raise UserError("No Isuree Id. Please Update and Retry")
