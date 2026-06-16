from odoo import api, models, fields
from odoo.exceptions import ValidationError, UserError
import requests
import pdfkit
import base64
import json
import logging
_logger = logging.getLogger(__name__)

class InsuranceClaim(models.Model):
    _name = 'insurance.claim'
    _description = 'Insurance Claims'
    _order = "id desc"

    claim_code = fields.Char(string="Claim Code")
    claim_manager_id = fields.Many2one('res.users', string="Claims Manager", tracking=True)
    claimed_date = fields.Datetime(string="Creation Date", help="Claim Date")
    partner_id = fields.Many2one('res.partner', string="Insuree", required=True, tracking=True)
    nhis_number = fields.Char(string="NHIS Number")
    nmc_number = fields.Char(string="NMC Number")
    care_setting = fields.Selection([
        ('opd', 'OPD'),
        ('ipd', 'IPD')
    ])
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('entered', 'Entered'),
        ('uploaded', 'Uploaded'),
        ('submitted', 'Submitted'),
        ('checked', 'Checked'),
        ('valuated', 'Valuated'),
        ('rejected', 'Rejected')
    ], string="State", default="draft")
    claim_uuid = fields.Char(string="Claim UUID", store=True, readonly=True)
    insurance_claim_line = fields.One2many('insurance.claim.line', 'claim_id', string="Insurance Claim Line", copy=True)
    attachment_ids = fields.Many2many('ir.attachment', string="Attachments", copy=True)
    external_visit_uuid = fields.Char(string="External Visit Id", help="This field is used to store visit id of a patient", readonly=True)
    visit_type = fields.Char(string="Visit Type", store=True, readonly=True)
    partner_uuid = fields.Char(string="Customer UUID", store=True, readonly=True)
    sale_orders = fields.Many2many('sale.order', string="Sale Orders")
    currency_id = fields.Many2one(related="sale_orders.currency_id", string="Currency", store=True, readonly=True)
    icd_code = fields.Many2many('insurance.disease.code', string="Diagnosis", store=True, copy=True)
    insurance_claim_history = fields.One2many('insurance.claim.history', 'claim_id', string="Claim Lines", copy=True)
    claim_comments = fields.Text(string="Claim Comments")
    rejection_reason = fields.Text(string="Rejection Reason")
    claimed_amount_total = fields.Monetary(string="Total Claimed Amount", store=True, readonly=True, compute="_claimed_amount_all")
    code = fields.Integer(string="Critical Illness Code")
    amount_approved_total = fields.Monetary(string="Total Approved Amount", store=True, readonly=True, compute="_claimed_amount_all")
    generated_claim_code = fields.Char(string="Generated Claim Code", store=True, readonly=True)
    claim_explanation = fields.Text(string="Explanation", store=True)

    def _create_claim(self, sale_order):
        '''
            Create/Update claims
        '''
        _logger.info("Inside _create_claim")
        _logger.info("Sale Order Id:%s", sale_order)
        if sale_order and sale_order.payment_type in 'insurance':
            '''
                Create and save claims
            '''
            if not sale_order.nhis_number:
                raise ValidationError("Claim can't be created. NHIS Number is not present.")
            
            insurance_sale_order_lines = sale_order.order_line.filtered(lambda r : r.payment_type == 'insurance')
            if not insurance_sale_order_lines:
                raise UserError("No Sales order line marked as Insurance Payment type")
            
            nmc_value = ""
            if sale_order.provider_name:
                nmc = sale_order.provider_name.split("_")
                if len(nmc) > 1:
                    nmc_value = nmc[1]
                    _logger.info("NMC Value:%s", nmc_value)
                else:
                    _logger.info("Invalid NMC Number")
            else:
                _logger.info("Provider Number is Empty")

            visit_uuid = sale_order.external_visit_uuid
            _logger.info("Visit UUID:%s", visit_uuid)

            claim_in_db = self.env['insurance.claim'].search([('external_visit_uuid', '=', visit_uuid), ('care_setting', '=', 'ipd'), ('state', '=', 'draft')])
            _logger.info("Claim in db=%s", claim_in_db)

            if claim_in_db:
                '''Update existing claim'''
                _logger.info("About to edit claim")
                ''' Update contents of claim only if claim is partial or insurance'''
                
                ''' Update contents of claim line only if payment type is insurance'''
                ''' Check whether a given product has a line item, if yes add quantity, if no add line item'''
                ''' Check whether a patient has a claim, if yes then add new order item on same claim line'''
                if claim_in_db.state in ['confirmed','submitted']:
                    raise UserError("Claim in %s state. Claim should be in draft state to be editable. So new items can't be added"%(claim_in_db.state))
            
                if sale_order.id not in claim_in_db.sale_orders.ids:
                    _logger.info("New Sale Order ID:%s", sale_order.id)
                    claim_in_db.update({'sale_orders': claim_in_db.sale_orders + sale_order})
            else:
                '''Create new claim'''
                _logger.info("About to Create new claim")
                insurance_sale_order_lines = sale_order.order_line.filtered(lambda r : r.payment_type == 'insurance')
                if not insurance_sale_order_lines:
                    raise UserError("No Sales order line marked as Insurance Payment type")

            insurance_number = sale_order.nhis_number
            claim_code = sale_order.claim_id

            claim = {
                'nhis_number': insurance_number,
                'claim_code': claim_code,
                'claim_manager_id': sale_order.user_id.id,
                'claimed_date': sale_order.create_date,
                'partner_id': sale_order.partner_id.id,
                'state': 'draft',
                'partner_uuid': sale_order.partner_uuid,
                'currency_id': sale_order.currency_id.id,
                'sale_orders': sale_order,
                'external_visit_uuid': visit_uuid,
                'visit_type': sale_order.visit_type,
                'care_setting': sale_order.care_setting,
                'nmc_number': nmc_value
            }
            _logger.info("Claim:%s", claim)
            claim_in_db = self.env['insurance.claim'].search([('external_visit_uuid', '=', visit_uuid), ('care_setting', '=', 'ipd'), ('state', '=', 'draft')])
            _logger.info("Existing IPD Claim Id:%s", claim_in_db)
            # Create a insurance claim
            if len(claim_in_db) == 0:
                _logger.info("*****Creating New Claim*****")
                claim_in_db = self.env['insurance.claim'].create(claim)
                _logger.info("Claim in db:%s", claim_in_db)

            # If care setting is "ipd" then adding new sales order
            _logger.info("New Sale Order Id:%s", sale_order)
            _logger.info("Old Sale Order Id:%s", claim_in_db.sale_orders)

            claim_in_db.update({
                'sale_orders': claim_in_db.sale_orders + sale_order
            })
            _logger.info("New Claim with added sale order:%s", claim_in_db)

            try:
                # Create a insurance claim line
                self._create_claim_line(claim_in_db, sale_order)

                insurance_claim_lines = self.env['insurance.claim.line'].search([
                    ('claim_id', '=', claim_in_db.id)
                ])

                _logger.info("Insurance Claim Line:%s", insurance_claim_lines)
                
                # Update 'insurance claim line' id in the insurance claim model
                if insurance_claim_lines:
                    claim_in_db.update({
                        'insurance_claim_line': insurance_claim_lines
                    })
                else:
                    _logger.info("No Claim Line Item Present")
                    raise ValidationError("No Claim Line Item Present")
                
                # Add history
                self._add_history(claim_in_db)

                 # To generate pdf report in the ir.attachment model
                _logger.info("Sale Order Name:%s", sale_order.name)
                account_move_id = self.env['account.move'].search([
                    ('invoice_origin', '=', sale_order.name)
                ])
                _logger.info("Account Move Id:%s", account_move_id)
                claim_id = claim_in_db
                _logger.info("Claim Id:%s", claim_id)
                self.env['account.move'].action_generate_attachment(account_move_id, claim_id)
                    
            except Exception as err:
                _logger.info("\n Error generating claim draft:%s", err)
                raise UserError(err)
        else:
            _logger.info("Payment Type:%s", sale_order.payment_type)
       
    def _create_claim_line(self, claim, sale_order):
        _logger.info("Inside _create_claim_line")
        insurance_sale_order_lines = sale_order.order_line.filtered(lambda l: l.payment_type == 'insurance')
        _logger.info("Insurance Sale Order Lines:%s", insurance_sale_order_lines)

        if not insurance_sale_order_lines:
            _logger.info("No sale order line found for insurance payment type")
            raise ValidationError("No sale order line found for insurance payment type")
        
        for sale_order_line in insurance_sale_order_lines:
            _logger.info("Inside insurance sale order line loop")
            imis_mapped_row = self.env['insurance.odoo.product.map'].search([
                ('odoo_product_id', '=', sale_order_line.product_id.id), 
                ('is_active', '=', True)
            ])
            _logger.info("IMIS Mapped Row:%s", imis_mapped_row)

            if not imis_mapped_row:
                raise ValidationError("IMIS Mapping not found for product:%s", sale_order_line.product_id.name)
            
            if len(imis_mapped_row) > 1:
                raise ValidationError("Multiple IMIS Mapping found for product:%s", sale_order_line.produt_id.name)
        
            #Check if a product is already present. If yes update the quantity.
            insurance_claim_line = claim.insurance_claim_line.filtered(lambda r: r.imis_product_code == imis_mapped_row.item_code)
            _logger.info("Insurance Claim Line:%s", insurance_claim_line)

            if insurance_claim_line:
                _logger.info("Insurance Claim Line Quantity:%s", insurance_claim_line.product_qty)
                insurance_claim_line.update({
                    'product_qty': insurance_claim_line.product_qty + sale_order_line.product_uom_qty
                })
                _logger.info("Insurance Claim Line After Adding Quantity:%s", insurance_claim_line.product_qty)
            else:
                self.create_new_claim_line(claim, sale_order_line, imis_mapped_row)

    def create_new_claim_line(self, claim, sale_order_line, imis_mapped_row):
        _logger.info("Inside create_new_claim_line")
        claim_line_item = {
            'claim_id': claim.id,
            'product_id': sale_order_line.product_id.id,
            'product_qty': sale_order_line.product_uom_qty,
            'imis_product': imis_mapped_row.id,
            'imis_product_code': imis_mapped_row.item_code,
            'price_unit': imis_mapped_row.insurance_product_price,
            'currency_id': claim.currency_id,
            'total_price': sale_order_line.price_subtotal
        }
        _logger.info("Claim Line Item:%s", claim_line_item)

        claim_line_in_db = self.env['insurance.claim.line'].create(claim_line_item)
        _logger.info("Claim Line in DB:%s", claim_line_in_db)

    def _add_history(self, claim_in_db):
        _logger.info("Inside _add_history")
        claim_history_line = self.env['insurance.claim.history']._add_claim_history(claim_in_db)
        claim_history = self.env['insurance.claim.history'].search([('claim_id', '=', claim_in_db.id)])
        _logger.info("Claim History=%s", claim_history)
        if claim_history:
            claim_in_db.update({
                'insurance_claim_history': claim_history
            })

    def action_retrieve_diagnosis(self):
        openmrs_connect_configurations = self.env['insurance.config.settings'].get_values()
        _logger.info("Openmrs Configuration=%s", openmrs_connect_configurations)
        if not openmrs_connect_configurations:
            raise UserError("OpenMRS Configuration Not Set!!")
        
        insurance_connect = self.env['insurance.connect']

        partner_uuid = self.partner_uuid
        _logger.info("Partner Uuid=%s", partner_uuid)
        external_visit_uuid = self.external_visit_uuid
        _logger.info("External Visit Uuid=%s", external_visit_uuid)

        url = insurance_connect.prepare_openmrs_url("/openmrs/ws/rest/v1/bahmnicore/diagnosis/search?patientUuid={}&visitUuid={}".format(partner_uuid, external_visit_uuid), openmrs_connect_configurations)
        _logger.info("URL=%s", url)
        custom_headers = {
            'Content-Type': 'application/json'
        }
        headers = insurance_connect.get_openmrs_header(openmrs_connect_configurations)
        custom_headers.update(headers)
        response = requests.get(url, headers=custom_headers, verify=False)
        _logger.info("Response=%s", response)

        if response.status_code == 200:
            resp = response.json()
            _logger.info("Resp=%s", resp)

            icd_codes_to_add = []

            for diagnosis in resp:
                mappings = diagnosis.get("codedAnswer", {}).get("mappings", [])
                for mapping in mappings:
                    if mapping.get("source") == 'ICD-11-WHO':
                        name = mapping.get("name")
                        code = mapping.get("code")
                        _logger.info("Name=%s", name)
                        _logger.info("Code=%s", code)

                        # search or create ICD code record
                        insurance_disease_code = self.env['insurance.disease.code'].search([('icd_code', '=', code)], limit=1)
                        _logger.info("Insurance Disease Code=%s", insurance_disease_code)

                        if not insurance_disease_code:
                            insurance_disease_code = self.env['insurance.disease.code'].create({
                                'diagnosis': name,
                                'icd_code': code
                            })
                        icd_codes_to_add.append(insurance_disease_code.id)
            # Update the many2many field
            if icd_codes_to_add:
                self.icd_code = [(4, icd_id) for icd_id in icd_codes_to_add]   

    def get_server_ip(self):
        _logger.info("Inside get_server_ip")
        openmrs_connect_configurations = self.env['insurance.config.settings'].get_values()
        _logger.info("Openmrs Configuration=%s", openmrs_connect_configurations)
        if not openmrs_connect_configurations:
            raise UserError("OpenMRS Configuration Not Set!!")
        return openmrs_connect_configurations['openmrs_base_url']

    def convert_url_to_pdf(self, url):
        _logger.info("Inside convert_url_to_pdf")
        # Use pdfkit to convert the URL content to a PDF
        pdf_content = pdfkit.from_url(url, False)

        # Create an attachment with the PDF content
        attachment = self.env['ir.attachment'].create({
            'name': 'patient-summary.pdf',
            'type': 'binary',
            'datas': base64.b64encode(pdf_content),
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/pdf'
        })
        # Return the attachment ID or any other result as needed
        return attachment.id

    def generate_opd_one_pager(self):
        _logger.info("Inside generate_opd_one_pager")
        ip_address = self.get_server_ip()
        _logger.info("Ip Address=%s", ip_address)
        for record in self:
            partner_uuid = record.partner_uuid
            external_visit_uuid = record.external_visit_uuid
            url = "{}:4433/onepager/?patient={}&visit={}".format(ip_address, partner_uuid, external_visit_uuid)
            _logger.info("URL=%s", url)
            attachment_id = record.convert_url_to_pdf(url)
            # Append the newly generated attachment ID to the existing ones
            record.attachment_ids = [(4, attachment_id)]

    def action_confirm(self):
        _logger.info("Inside action_confirm")

        # Check if state is draft or rejected
        for claim in self:
            _logger.info(claim)
            _logger.info("Claim State=%s", claim.state)

            previous_claim = self.env['insurance.claim'].search([
                ('nhis_number', '=', self.nhis_number),
                ('external_visit_uuid', '=', self.external_visit_uuid),
                ('id', '<', claim.id),
            ], order='id asc', limit=1)

            _logger.info("Previous Claim=%s", previous_claim)
            _logger.info("Generated Claim Code=%s", previous_claim.generated_claim_code)

            if claim.state in ('draft', 'rejected'):
                claim.update({
                    'state': 'confirmed',
                    'claim_code': previous_claim.generated_claim_code if previous_claim.generated_claim_code else ''
                })

                self._add_history(claim)

                # Validate and then confirm
                for claim_line in claim.insurance_claim_line:
                    _logger.info(claim_line)
                    if not claim_line.imis_product_code:
                        raise UserError("%s has not been mapped. Please map the product and retry again."%(claim_line.product_id.name))

    @api.depends('insurance_claim_line.total_price')      
    def _claimed_amount_all(self):
        _logger.info("Inside _claimed_amount_all")
        for claim in self:
            claimed_amount_total = 0.0
            for line in claim.insurance_claim_line:
                claimed_amount_total += line.total_price
            
            claim.claimed_amount_total = claimed_amount_total
            _logger.info("Claimed Amount Total=%s", claim.claimed_amount_total)

    def _get_visit_data(self):
        _logger.info("Inside _get_visit_data")
        openmrs_connect_configurations = self.env['insurance.config.settings'].get_values()
        _logger.info("Openmrs Configuration=%s", openmrs_connect_configurations)
        if not openmrs_connect_configurations:
            raise UserError("OpenMRS Configuration Not Set!!")
        
        insurance_connect = self.env['insurance.connect']
        partner_uuid = self.partner_id.uuid
        url = insurance_connect.prepare_openmrs_url("/openmrs/ws/rest/v1/visit?includeInactive=false&patient={}".format(partner_uuid), openmrs_connect_configurations)
        _logger.error(url)
        
        custom_headers = {'Content-Type': 'application/json'}
        headers = insurance_connect.get_openmrs_header(openmrs_connect_configurations)
        
        custom_headers.update(headers)   
                    
        response = requests.get(url, headers=custom_headers, verify=False)
        _logger.info("Response=%s",response)
        if response.status_code == 200:
            resp = response.json()
            _logger.info("Resp=%s", resp)
            visit_uuid = response.json()["results"][0]["uuid"]
            _logger.info("URL: %s", visit_uuid)
            visit_url = insurance_connect.prepare_openmrs_url("/openmrs/ws/rest/v1/bahmnicore/visit/summary?visitUuid={}".format(visit_uuid), openmrs_connect_configurations)
            _logger.error(visit_url)
            custom_headers = {'Content-Type': 'application/json'}
            headers = insurance_connect.get_openmrs_header(openmrs_connect_configurations)
            custom_headers.update(headers)   
            visit_response = requests.get(visit_url, headers=custom_headers, verify=False)
            if visit_response.status_code == 200:
                data = visit_response.json()
                _logger.debug("Data=%s", data)
                return data
        else:
            _logger.info(response.status_code)
            raise UserError("Sales order doesn't have partner uuid")

    def action_claim_submit(self):
        _logger.info("Inside action_claim_submit")
        visit_data = self._get_visit_data()
        _logger.info("Visit Data=%s",visit_data) 
        visit_uuid = visit_data.get('uuid')
        _logger.info("Visit UUID=%s", visit_uuid)

        visit_type = visit_data.get('visitType')
        _logger.info("lower visit type=%s", visit_type)

        if visit_type.lower() == 'ipd':
            _logger.info("Visit Type=%s", visit_type)
            admission_details = visit_data.get('admissionDetails')
            if admission_details is not None:
                start_date_time = admission_details.get('date')
                _logger.info("Start Date Time=%s", start_date_time)
            else:
                raise ValidationError("Start Date is NULL")

            discharge_details = visit_data.get('dischargeDetails')
            if discharge_details is not None:
                end_date_time = discharge_details.get('date')
                _logger.info("End Date Time=%s", end_date_time)
            else:
                raise ValidationError("End Date is NULL")
        else:
            _logger.info("Visit Type=%s", visit_type)
            # Convert to timestamp (seconds -> milliseconds)
            start_date_time = int(self.create_date.timestamp() * 1000)
            _logger.info("Long Start Datetime=%s", start_date_time)
            end_date_time = start_date_time
            _logger.info("Long End Datetime=%s", end_date_time)

        visit_type_mapping = {
            'OPD': 'O',
            'IPD': 'O',
            'EMERGENCY': 'E',
        }

        # Mapping the visit type
        mapped_visit_type = visit_type_mapping.get(visit_type)
        _logger.info("Mapped Visit Type=%s", mapped_visit_type)
        
        # Check if state is draft or rejected
        try:
            for claim in self:
                if claim.state == "confirmed":
                    claim.update({
                        'claim_code': claim.claim_code,
                        'state': 'submitted',
                        'claimed_date': fields.Datetime.now()
                    })
                    
                    _logger.info("Claim State:%s", claim.state)
                    _logger.info("Claim Date=%s", claim.claimed_date)
                    _logger.info("Claim Code:%s", claim.claim_code)

                    care_setting_mapping = {
                        'opd': 'O',
                        'ipd': 'I'
                    }

                    care_type = claim.care_setting
                    _logger.info("Care Type=%s", care_type)

                    # Mapping the care setting
                    mapped_care_setting = care_setting_mapping.get(care_type)
                    _logger.info("Mapped Care Setting=%s", mapped_care_setting)
                    
                    self._add_history(claim)

                    claim_request = {
                        'patientUUID': claim.partner_uuid,
                        'visitUUID': claim.external_visit_uuid,
                        'claimId': claim.claim_code,
                        'insureeId': claim.nhis_number,
                        'total': claim.claimed_amount_total,
                        'item': [],
                        'diagnosis': [],
                        "information": [],
                        'visit': {
                            'startDate': start_date_time,
                            'endDate': end_date_time,
                            'visitType': mapped_visit_type,
                            'visitUUID': claim.external_visit_uuid
                        },
                        'nmc': claim.nmc_number,
                        'careType': mapped_care_setting,
                        'extension': [
                            {
                                'code': claim.code if claim.code else 'HIB-3500'
                            }
                        ]
                    }
                    # Prepare claim line item
                    sequence = 1
                    for claim_line in claim.insurance_claim_line:
                        if claim_line.imis_product_code:
                            claim_line.claim_sequence = sequence

                            if claim_line.product_id.product_tmpl_id.detailed_type == 'service':
                                category = 'service'
                            else:
                                category = 'product'
                            
                            claim_request['item'].append({
                                'category': category,
                                'quantity': claim_line.product_qty,
                                'sequence': sequence,
                                'code': claim_line.imis_product_code,
                                'unitPrice': claim_line.price_unit
                            })
                            sequence += 1
                    
                    sequence = 1
                    for claim_diagnosis in claim.icd_code:
                        if claim_diagnosis:
                            claim_request['diagnosis'].append({
                                'icdCode': claim_diagnosis.icd_code,
                                'diagnosis': claim_diagnosis.diagnosis,
                                'sequence': sequence
                            })
                            sequence += 1
                    _logger.info("Claim Request=%s", claim_request)

                    sequence = 1
                    if claim.claim_explanation:
                        claim_request['information'].append({
                            'category': "explanation",
                            'sequence': sequence,
                            'valueString': claim.claim_explanation
                        })
                    
                    _logger.info(claim_request)

                    if not claim_request['diagnosis']:
                        for line in claim.insurance_claim_line:
                            if line.imis_product_code == 'OPD01' or line.imis_product_code == 'ER01':
                                _logger.info("Diagnosis not required")
                            else:
                                raise UserError("Diagnosis cannot be empty")
                            
                    if not claim_request['nmc']:
                        for line in claim.insurance_claim_line:
                            if line.imis_product_code == 'OPD01' or line.imis_product_code == 'ER01':
                                _logger.info("NMC Number not required")
                            else:
                                raise UserError("NMC Number cannot be empty")
            
            _logger.info("SUBMIT CLAIM")
            # Submit claim for processing
            response = self.env['insurance.connect']._submit_claims(claim_request)
            _logger.info("Response=%s", response)

            if response:
                self.update_claim_from_claim_response(claim, response)

        except Exception as err:
            _logger.error(err)
            raise UserError(err)
        
    def action_refund(self):
        _logger.info("Action Refund Button Clicked!!")
        for claim in self:
            for claim_line in claim.insurance_claim_line:
                if claim_line.product_id.type == "product":
                    type = "item"
                    _logger.info("Type:%s", type)
                elif claim_line.product_id.type == "service":
                    type = "service"
                    _logger.info("Type:%s", type)

                refund_request = { 
                    "claimId": claim.claim_code,
                    "type": type,
                    "codes":[]
                }
            for claim_line in claim.insurance_claim_line:
                if claim_line.imis_product_code:
                    refund_request["codes"].append(claim_line.imis_product_code)
            
            _logger.info("Refund Request---->%s", refund_request)

            response = self.env['insurance.connect']._submit_refund(refund_request)
            _logger.info("Response=%s", response)
            if response is None:
                raise ValidationError("Nothing To Refund!! Check Claim Status in IMIS!!")
            else:
                raise ValidationError("Message: " + str(response.get('message') + "\nTotal Refunded Amount: " + str(response.get('refunded'))) )
            
    def update_claim_from_claim_response(self, claim, response):
        _logger.info("Inside update_claim_from_claim_response")
        claim.claim_uuid = response['claimUUID']
        claim.amount_approved_total = response['approvedTotal']
        claim.rejection_reason = response['rejectionReason']
        claim.state = response['claimStatus']
        claim.generated_claim_code = response['generatedClaimCode']

        _logger.info("Claim Uuid=%s", claim.claim_uuid)
        _logger.info("Claim State=%s", claim.state)
        _logger.info("Generated Claim Code=%s", claim.generated_claim_code)
        _logger.info("Claim=%s", claim)
        _logger.info("Response=%s", response)

        for claim_response_line in response['claimLineItems']:
            _logger.info(json.dumps(claim_response_line))
            claim_line = self.env['insurance.claim.line'].search([('claim_sequence', '=', claim_response_line['sequence']), ('claim_id', '=', claim.id)])
            _logger.info(claim_response_line['sequence'])
            if claim_line:
                claim_line.state = claim_response_line['status']
                claim_line.rejection_reason = claim_response_line['rejectedReason']
                claim_line.amount_approved = claim_response_line['totalApproved']
                claim_line.quantity_approved = claim_response_line['quantityApproved']
            else:
                _logger.info("////ELSE RUNNING/////")
                claim.rejection_reason = claim_response_line['rejectedReason']
                _logger.info("Rejection Reason:%s",claim.rejection_reason) 
        
class InsuranceClaimLine(models.Model):
    _name = 'insurance.claim.line'
    _description = 'Insurance Claim Line Items'

    claim_id = fields.Many2one('insurance.claim', string="Claim Id", required=True, ondelete="cascade", index=True, copy=False)
    product_id = fields.Many2one('product.product', string="Product", domain=[('sale_ok', '=', True)], ondelete="Restrict", required=True)
    imis_product = fields.Many2one('insurance.odoo.product.map', string="Insurance Item", change_default=True)
    imis_product_code = fields.Char(string="IMIS Product Code", change_default=True)
    product_qty = fields.Integer(string="Qty", requred=True)
    price_unit = fields.Float(string="Unit Price")
    total_price = fields.Monetary(string="Total Price", currency_field="currency_id")
    currency_id = fields.Many2one(related='claim_id.currency_id', string="Currency", readonly=True, required=True)
    claim_sequence = fields.Integer(string="Claim Sequence", readonly=True)
    amount_approved = fields.Monetary(string='Approved amount', store=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('passed', 'Passed'),
        ('rejected', 'Rejected')
    ], string='Claim Status', readonly=True, store=True)
    rejection_reason = fields.Text(string="Rejection Reason")
    quantity_approved = fields.Integer(string='Quantity Approved', store=True)

class InsuranceClaimHistory(models.Model):
    _name = 'insurance.claim.history'
    _description = 'Insurance Claim History'

    claim_id = fields.Many2one('insurance.claim', string="Claim Id", required=True, ondelete="cascade", index=True, copy=False)
    partner_id = fields.Many2one(related="claim_id.partner_id", string="Insuree", readonly=True, index=True, tracking=True)
    claim_manager_id = fields.Many2one(related="claim_id.claim_manager_id", store=True, string="Claims Manager", readonly=True)
    claim_code = fields.Char(string="Claim Code", store=True)
    claim_status = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('entered', 'Entered'),
        ('uploaded', 'Uploaded'),
        ('submitted', 'Submitted'),
        ('checked', 'Checked'),
        ('valuated', 'Valuated'),
        ('rejected', 'Rejected'),
        ('processed', 'Processed'),
        ('passed', 'Passed')
    ], string="Claim Status", default="draft")
    claim_comments = fields.Text(string="Claim Comments")
    rejection_reason = fields.Text(string="Rejection Reasons")

    @api.model
    def _add_claim_history(self, claim):
        _logger.info("Inside _add_claim_history")
        claim_history = {
            'claim_id': claim.id,
            'partner_id': claim.partner_id.id,
            'claim_manager_id': claim.claim_manager_id.id,
            'claim_code': claim.claim_code,
            'claim_status': claim.state,
            'claim_comments': claim.claim_comments,
            'rejection_reason': claim.rejection_reason
        }
        _logger.info(claim_history)
        return self.env['insurance.claim.history'].create(claim_history)



