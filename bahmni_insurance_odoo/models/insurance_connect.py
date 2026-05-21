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

    def _get_capvalidation(self, nhis_number):
        _logger.info("Inside _get_capvalidation, NHIS Number:%s", nhis_number)
        try:
            insurance_connect_configurations = self.env['insurance.config.settings'].get_values()
            _logger.info("Insurance Connect Configurations:%s", insurance_connect_configurations)
            
            if not insurance_connect_configurations:
                raise UserError("Insurance Configurations Not Set")
            
            url = self.prepare_url(f"/capvalidation/{nhis_number}", insurance_connect_configurations)
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
            _logger.error("\n Processing event threw error:%s", err)

    def _submit_claims(self, claim_request):
        _logger.info("Inside _submit_claims")
        if claim_request is None:
            raise UserError("Nothing to claim")

        try:
            insurance_connect_configurations = self.env['insurance.config.settings'].get_values()
            _logger.info("Insurance Connect Configurations:%s", insurance_connect_configurations)
            
            if not insurance_connect_configurations:
                raise UserError("Insurance Configurations Not Set")
            
            url = self.prepare_url("/submit/claim", insurance_connect_configurations)
            _logger.info("Url:%s", url)

            # Convert the python objects into a json formatted string
            encoded_data = json.dumps(claim_request)
            _logger.info("Encoded Data=%s", encoded_data)

            http = urllib3.PoolManager()
            custom_headers = {'Content-Type': 'application/json'}
            headers = self.get_header(insurance_connect_configurations)
            _logger.info("Headers:%s", headers)
            custom_headers.update(headers)
            _logger.info("Custom Headers:%s", custom_headers)
            req = http.request('POST', url, headers=custom_headers, body=encoded_data)
            _logger.info("Request=%s", req)
            _logger.info("========= Response===============")
            if req.status == 200:
                _logger.info(req.status)
                # Convert the json string into python objects
                response = json.loads(req.data.decode('utf-8'))
                _logger.info(json.dumps(response))
                return response
            elif req.status == 503:
                _logger.error(req.data)
                raise UserError("Insurane Connect service is not availabe. Please contact system administrator")
            elif req.status == 401:
                _logger.error(req.data)
                raise UserError("Please check the credentials for insurance connect service and retry again")
            else:
                response = json.loads(req.data.decode('utf-8'))
                _logger.info(json.dumps(response))
                if response['operationOutComeException'] is None:
                    error_msg = "Claim submission failed, Please contact your application admin"
                else:
                    error_msg = response['operationOutComeException']
                raise UserError(error_msg)
        except Exception as err:
            _logger.error("\n Processing event threw error:%s", err)
            
    def response_processor(self, response):
        _logger.info("********Response********")
        _logger.info("Response Status %s", response.status)
        if response.status == 200:
            # Convert the json string into python objects
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
    
    def prepare_openmrs_url(self, end_point, openmrs_connect_configurations):
        return openmrs_connect_configurations['openmrs_base_url'] + end_point

    def get_header(self, insurance_connect_configurations):
        return urllib3.util.make_headers(basic_auth="%s:%s"%(insurance_connect_configurations['username'], insurance_connect_configurations['password']))
    
    def get_openmrs_header(self, openmrs_connect_configurations):
        return urllib3.util.make_headers(basic_auth="%s:%s"%(openmrs_connect_configurations['openmrs_username'], openmrs_connect_configurations['openmrs_password']))
