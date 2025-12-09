from odoo import api, models, fields
from odoo.exceptions import ValidationError
import logging
_logger = logging.getLogger(__name__)

class InsuranceClaim(models.Model):
    _name = 'insurance.claim'
    _description = 'Insurance Claim Module'
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
    claim_uuid = fields.Text(string="Claim UUID")
    insurance_claim_line = fields.One2many('insurance.claim.line', 'claim_id', string="Insurance Claim Line")
    attachment_ids = fields.Many2many('ir.attachment', string="Attachments")
    external_visit_uuid = fields.Char(string="External Visit Id", help="This field is used to store visit id of a patient")
    partner_uuid = fields.Char(string="Customer UUID", store=True, readonly=True)
    sale_orders = fields.Many2many('sale.order', string="Sale Orders")
    currency_id = fields.Many2one(related="sale_orders.currency_id", string="Currency", store=True, readonly=True)
    icd_code = fields.Many2many('insurance.disease.code', string="Diagnosis", store=True)

    def _create_claim(self, sale_order):
        _logger.info("Inside Create Claim overwritten")
        _logger.info("Sale Order Id:%s", sale_order)
        if sale_order and sale_order.payment_type in 'insurance':
            if not sale_order.nhis_number:
                raise ValidationError("Claim can't be created. NHIS Number is not present.")
        
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

            if not visit_uuid:
                _logger.info("Visit UUID is Empty")

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
            
            # To generate pdf report in the ir.attachment model
            _logger.info("Sale Order Name:%s", sale_order.name)
            account_move_id = self.env['account.move'].search([
                ('invoice_origin', '=', sale_order.name)
            ])
            _logger.info("Account Move Id:%s", account_move_id)
            claim_id = claim_in_db
            _logger.info("Claim Id:%s", claim_id)
            # self.env['account.move'].action_generate_attachment(account_move_id, claim_id)
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
            'total': sale_order_line.price_subtotal
        }
        _logger.info("Claim Line Item:%s", claim_line_item)

        claim_line_in_db = self.env['insurance.claim.line'].create(claim_line_item)
        _logger.info("Claim Line in DB:%s", claim_line_in_db)
            
class InsuranceClaimLine(models.Model):
    _name = 'insurance.claim.line'
    _description = 'Insurance Claim Line Module'

    claim_id = fields.Many2one('insurance.claim', string="Claim Id", required=True, ondelete="cascade", index=True, copy=False)
    product_id = fields.Many2one('product.product', string="Product", domain=[('sales_ok', '=', True)], ondelete="Restrict", required=True)
    imis_product = fields.Many2one('insurance.odoo.product.map', string="Insurance Item", change_default=True)
    imis_product_code = fields.Char(string="IMIS Product Code", change_default=True)
    product_qty = fields.Integer(string="Qty", requred=True)
    price_unit = fields.Float(string="Unit Price")
    total = fields.Monetary(string="Total Price", currency_field="currency_id")
    currency_id = fields.Many2one(related='claim_id.currency_id', string="Currency", readonly=True, required=True)
