from odoo import api, fields,models
from odoo.exceptions import UserError
import urllib3
import json
import logging 
_logger = logging.getLogger(__name__)

class InsuranceConnect(models.TransientModel):
    _name = 'insurance.connect'

    @api.model
    def authenticate(self, username, password, base_url):
        _logger.info("Inside Authenticate")
        insurance_connect_configurations = {
            'username': username,
            'password': password,
            'base_url': base_url
        }
        
        url = self.prepare_url("/request/authenticate", insurance_connect_configurations)
        _logger.info("Url:%s", url)
        http = urllib3.PoolManager()
        req = http.request('GET', url, headers=self.get_header(insurance_connect_configurations))
        _logger.info("Request:%s", req)

        if req.status == 200:
            # #Display dialogue box for successful
            # ola = 1
            response = req.data
            _logger.info("Response:%s", response)
        else:
            raise UserError("Connection Failed.")
    
    def _check_eligibilty(self, nhis_number):
        _logger.info("Inside _check_eligibility, NHIS Number:%s", nhis_number)
        try:
            insurance_connect_configurations = self.env['insurance.config.settings'].get_values()
            _logger.info("Insurance Connect Configurations:%s", insurance_connect_configurations)
            if not insurance_connect_configurations:
                raise UserError("Insurance Configuration Not Set")
            
            url = self.prepare_url("/check/eligibility/%s", insurance_connect_configurations)
            url = url%(nhis_number)
            _logger.info("Url:%s", url)
            http = urllib3.PoolManager()
            custom_headers = {'Content-Type': 'application/json'}
            headers = self.get_header(insurance_connect_configurations)
            _logger.info("Headers:%s", headers)
            custom_headers.update(headers)
            _logger.info("Custom Headers:%s", custom_headers)
            req = http.request('GET', url, headers=custom_headers)
            _logger.info("Request:%s", req)
            return self.response_processor(req)
        except Exception as err:
            _logger.error("\n Processing event threw error: %s", err)
            
    def response_processor(self, response):
        _logger.info("********Response********")
        _logger.info("Response Status %s", response.status)
        if response.status == 200:
            response = json.loads(response.data.decode('utf-8'))
            _logger.info(json.dumps(response))
            return response
        elif response.status == 503:
            _logger.error(response.data)
            raise UserError("Insurane Connect service is not availabe. Please contact system administrator")
        elif response.status == 401:
            _logger.error(response.data)
            raise UserError("Please check the credentials for insurance connect service and retry again")
        else:
            _logger.error("\n Failed Request to Insurance Connect:%s", response.data)
            raise UserError("Failed Request to Insurance Connect")
    
    def prepare_url(self, end_point, insurance_connect_configurations):
        return insurance_connect_configurations['base_url'] + end_point

    def get_header(self, insurance_connect_configurations):
        return urllib3.util.make_headers(basic_auth="%s:%s"%(insurance_connect_configurations['username'], insurance_connect_configurations['password']))
    