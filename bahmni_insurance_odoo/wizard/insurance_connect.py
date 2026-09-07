from odoo import api, fields,models
from odoo.exceptions import UserError
import urllib3
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
        _logger.debug("Request:%s", req)

        if req.status == 200:
            #Display dialogue box for successful
            ola = 1
        else:
            raise UserError("Connection Failed.")
        response = req.data
        _logger.info("Response:%s", response)
        
    def prepare_url(self, end_point, insurance_connect_configurations):
        return insurance_connect_configurations['base_url'] + end_point

    def get_header(self, insurance_connect_configurations):
        return urllib3.util.make_headers(basic_auth="%s:%s"%(insurance_connect_configurations['username'], insurance_connect_configurations['password']))