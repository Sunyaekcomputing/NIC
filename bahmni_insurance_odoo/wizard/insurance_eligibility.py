from odoo import api, fields, models
from odoo.exceptions import UserError
from dateutil.parser import parse
import logging
_logger = logging.getLogger(__name__)

class InsuranceEligibility(models.TransientModel):
    _name = 'insurance.eligibility'
    _description = 'Insurance Eligibility'

    insuree_name = fields.Char(string="Insuree Name", readonly=1)
    nhis_number = fields.Char(string="NHIS Number", readonly=1)
    eligibility_line_item = fields.One2many('insurance.eligibility.line', 'eligibility_response_id', string="Eligibility Response Id")
    hospital = fields.Char(string="Hospital", readonly=1)
    district = fields.Char(string="District", readonly=1)
    copayment_value = fields.Float(string="Copayment Value", readonly=1)
    
    def get_insurance_details(self, partner_id):
        _logger.info("Inside Get Insurance Details")
        nhis_number = self.env['res.partner']._get_nhis_number(partner_id.id)
        _logger.info("NHIS Number:%s", nhis_number)
        if nhis_number:
            response = self.env['insurance.connect']._check_eligibilty(nhis_number)
            _logger.info("Eligibility Response:%s", response)
            hospital = response['hospital']
            district = response['district']
            copayment_value = response['coPaymentValue']
            elig_response = {
                'insuree_name': partner_id.name,
                'nhis_number': nhis_number,
                'hospital': hospital,
                'district': district,
                'copayment_value': copayment_value
            }
            elig_response = self.env['insurance.eligibility'].create(elig_response)
            _logger.info("Elig Response:%s", elig_response)
            if response['eligibilityBalance']:
                for elig_response_line in response['eligibilityBalance']:
                    raw_date = elig_response_line['validDate']
                    dt_obj = parse(raw_date)
                    _logger.info("Parse DateTime:%s", dt_obj)
                    # Only the date part
                    valid_date = dt_obj.date()
                    elig_response_line = {
                        'eligibility_response_id': elig_response.id,
                        'eligibility_balance': elig_response_line['benefitBalance'],
                        'category': elig_response_line['category'],
                        'valid_date': valid_date
                    }
                    elig_response_line_db = self.env['insurance.eligibility.line'].search([('eligibility_response_id', '=', elig_response.id)])
                    elig_response_line = self.env['insurance.eligibility.line'].create(elig_response_line)
                    self.env['insurance.eligibility'].update({
                        'eligibility_line_item': elig_response_line_db + elig_response_line
                    })
            return elig_response
        else:
            raise UserError("No Insuree Id. Please Update and Retry")
        
class InsuranceEligibilityLine(models.TransientModel):
    _name = 'insurance.eligibility.line'
    _description = 'Insurance Eligibiliy Line'
    
    eligibility_response_id = fields.Many2one('insurance.eligibility', string="Insurance Eligibility")
    eligibility_balance = fields.Float(string="Eligibility Balance")
    category = fields.Char(string="Category")
    valid_date = fields.Datetime(string="Valid Date")

        
