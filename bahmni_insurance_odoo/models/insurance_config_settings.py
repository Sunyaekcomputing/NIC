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
    
    @api.model
    def get_values(self):
        res = super().get_values()
        param_obj = self.env['ir.config_parameter'].sudo()
        res.update(
            username = param_obj.get_param('insurance.config.settings.username', default=''),
            password = param_obj.get_param('insurance.config.settings.password', default=''),
            base_url = param_obj.get_param('insurance.config.settings.base_url', default='')
        )
        return res
    
    @api.model
    def get_insurance_journal(self):
        res = super().get_values()
        param_obj = self.env['ir.config_parameter'].sudo()
        res.update(
            insurance_journal = param_obj.get_param('insurance.config.settings.insurance_journal', default='')
        )

    def set_values(self):
        super().set_values()
        param_obj = self.env['ir.config_parameter'].sudo()
        param_obj.set_param('insurance.config.settings.username', self.username)
        param_obj.set_param('insurance.config.settings.password', self.password)
        param_obj.set_param('insurance.config.settings.base_url', self.base_url)
        param_obj.set_param('insurance.config.settings.insurance_journal', self.insurance_journal)

    def action_test_connection(self):
        _logger.info("Action Test Connection")
        username = ""
        password = ""
        base_url = ""
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


    
   
