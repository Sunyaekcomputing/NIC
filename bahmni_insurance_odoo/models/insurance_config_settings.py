from odoo import api, models, fields
from odoo.exceptions import ValidationError, UserError
import logging
_logger = logging.getLogger(__name__)

class InsuranceConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    _name = 'insurance.config.settings'
    _descripton = 'Insurance Config Settings'

    username = fields.Char(string="Username", required=True)
    password = fields.Char(string="Password", required=True)
    base_url = fields.Char(string="Base Url")
    openmrs_username = fields.Char(string="User Name")
    openmrs_password = fields.Char(string="Password")
    openmrs_base_url = fields.Char(string="Base Url")
    insurance_journal = fields.Char(string="Insurance Journal")
    manually_setup_claim_code = fields.Boolean(string="Use default claim code", help="Use default claim code or set it up manually")
    claim_code_start_range = fields.Integer(string="Start Range", help="start value for claim code")
    claim_code_end_range = fields.Integer(string="End Range", help="End value for claim code")
    claim_code_next_val = fields.Integer(string="Next Value")
    manually_setup_ipd_number = fields.Boolean(string="Use default ipd number", help="Use default ipd number or set it up manually")
    ipd_number_start_range = fields.Integer(string="Start Range", help="start value for ipd number")
    ipd_number_end_range = fields.Integer(string="End Range", help="End value for ipd number")
    ipd_number_next_val = fields.Integer(string="Next Value")

    @api.model
    def get_values(self):
        res = super().get_values()
        param_obj = self.env['ir.config_parameter'].sudo()
        res.update(
            username = param_obj.get_param('insurance.config.settings.username', default=''),
            password = param_obj.get_param('insurance.config.settings.password', default=''),
            base_url = param_obj.get_param('insurance.config.settings.base_url', default=''),
            openmrs_username = param_obj.get_param('insurance.config.settings.openmrs_username', default=''),
            openmrs_password = param_obj.get_param('insurance.config.settings.openmrs_password', default=''),
            openmrs_base_url = param_obj.get_param('insurance.config.settings.openmrs_base_url', default=''),
            insurance_journal = param_obj.get_param('insurance.config.settings.insurance_journal', default=''),
            manually_setup_claim_code = param_obj.get_param('insurance.config.settings.manually_setup_claim_code', default=''),
            claim_code_start_range = param_obj.get_param('insurance.config.settings.claim_code_start_range', default=''),
            claim_code_end_range = param_obj.get_param('insurance.config.settings.claim_code_end_range', default=''),
            claim_code_next_val = param_obj.get_param('insurance.config.settings.claim_code_next_val', default=''),
            manually_setup_ipd_number = param_obj.get_param('insurance.config.settings.manually_setup_ipd_number', default=''),
            ipd_number_start_range = param_obj.get_param('insurance.config.settings.ipd_number_start_range', default=''),
            ipd_number_end_range = param_obj.get_param('insurance.config.settings.ipd_number_end_range', default=''),
            ipd_number_next_val = param_obj.get_param('insurance.config.settings.ipd_number_next_val', default='')
        )
        return res
    
    @api.model
    def set_values(self):
        super().set_values()
        param_obj = self.env['ir.config_parameter'].sudo()
        param_obj.set_param('insurance.config.settings.username', self.username)
        param_obj.set_param('insurance.config.settings.password', self.password)
        param_obj.set_param('insurance.config.settings.base_url', self.base_url)
        param_obj.set_param('insurance.config.settings.openmrs_username', self.openmrs_username)
        param_obj.set_param('insurance.config.settings.openmrs_password', self.openmrs_password)
        param_obj.set_param('insurance.config.settings.openmrs_base_url', self.openmrs_base_url)
        param_obj.set_param('insurance.config.settings.insurance_journal', self.insurance_journal)
        param_obj.set_param('insurance.config.settings.manually_setup_claim_code', self.manually_setup_claim_code)
        param_obj.set_param('insurance.config.settings.claim_code_start_range', self.claim_code_start_range)
        param_obj.set_param('insurance.config.settings.claim_code_end_range', self.claim_code_end_range)
        param_obj.set_param('insurance.config.settings.claim_code_next_val', self.claim_code_next_val)
        param_obj.set_param('insurance.config.settings.manually_setup_ipd_number', self.manually_setup_ipd_number)
        param_obj.set_param('insurance.config.settings.ipd_number_start_range', self.ipd_number_start_range)
        param_obj.set_param('insurance.config.settings.ipd_number_end_range', self.ipd_number_end_range)
        param_obj.set_param('insurance.config.settings.ipd_number_next_val', self.ipd_number_next_val)

    def action_test_connection(self):
        _logger.info("Action Test Connection")
        for rec in self:
            username = rec.username
            password = rec.password
            base_url = rec.base_url

            _logger.info("Username:%s", username)
            _logger.info("Password:%s", password)
            _logger.info("Base Url:%s", base_url)

            response = rec.env['insurance.connect'].authenticate(username, password, base_url)
            _logger.info("Response:%s", response)
            if response:
                raise UserError(response)
            else:
                return {
                    "type": "ir.actions.act_window",
                    "res_model": "insurance.config.settings",
                    "views": [(False, "form")],
                    "res_id": rec.id,
                    "target": "main",
                    "context": {"show_message": True}
                } 
    
    @api.constrains("manually_setup_claim_code", "claim_code_start_range", "manually_setup_ipd_number", "ipd_number_start_range")
    def validate_start_range(self):
        '''
            Skip Start Range validation if its not manual setup for claim code or ipd number
        '''
        for rec in self:
            if rec.manually_setup_claim_code:
                if rec.claim_code_start_range <= 0:
                    raise ValidationError("The Claim Code Start Range can't be lesser than or equal to 0")
                
            if rec.manually_setup_ipd_number:
                if rec.ipd_number_start_range <= 0:
                    raise ValidationError("The IPD Number Start Range can't be lesser than or equal to 0")
                
    @api.constrains("manually_setup_claim_code", "claim_code_end_range", "manually_setup_ipd_number", "ipd_number_end_range")
    def validate_end_range(self):
        '''
            Skip End Range validation if its not manual setup for claim code or ipd number
        '''
        for rec in self:
            if rec.manually_setup_claim_code:
                if rec.claim_code_end_range < rec.claim_code_start_range:
                    raise ValidationError("The Claim Code End Range can't be smaller than Start Range")
                
            if rec.manually_setup_ipd_number:
                if rec.ipd_number_end_range < rec.ipd_number_start_range:
                    raise ValidationError("The IPD Number End Range can't be smaller than Start Range")
        
    @api.constrains("manually_setup_claim_code", "claim_code_next_val", "manually_setup_ipd_number", "ipd_number_next_val")
    def validate_next_val(self):
        '''
            Skip Next Value validation if its not manual setup for claim code or IPD Number
        '''
        for rec in self:
            if rec.manually_setup_claim_code:
                if rec.claim_code_next_val < rec.claim_code_start_range:
                    raise ValidationError("The Claim Code Next Value can't be lesser than Start Range")
                
                if rec.claim_code_next_val > rec.claim_code_end_range:
                    raise ValidationError("The Claim Code Next Value can't be greater than End Range")
            
            if rec.manually_setup_ipd_number:
                if rec.ipd_number_next_val < rec.ipd_number_start_range:
                    raise ValidationError("The IPD Number Next Value can't be lesser than Start Range")
                
                if rec.ipd_number_next_val > rec.ipd_number_end_range:
                    raise ValidationError("The IPD Number Next Value can't be greater than End Range")
    
    def get_next_value(self):
        _logger.info("Inside get_next_value")
        param_obj = self.env['ir.config_parameter'].sudo()

        next_value = param_obj.get_param('insurance.config.settings.claim_code_next_val')
        _logger.info("Next Value = %s", next_value)

        next_value = int(next_value)

        next_value += 1

        param_obj.set_param('insurance.config.settings.claim_code_next_val', next_value)
        _logger.info("After update, next value = %s", next_value)

        return next_value
    
    def get_ipd_next_value(self):
        _logger.info("Inside get_ipd_next_value")
        param_obj = self.env['ir.config_parameter'].sudo()

        next_value = param_obj.get_param('insurance.config.settings.ipd_number_next_val')
        _logger.info("Next Value = %s", next_value)

        next_value = int(next_value)

        next_value += 1

        param_obj.set_param('insurance.config.settings.ipd_number_next_val', next_value)
        _logger.info("After update, next value = %s", next_value)

        return next_value


    
   
