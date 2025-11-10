from odoo import api, models, fields
from odoo.exceptions import ValidationError, UserError
import odoo.addons.decimal_precision as dp
import requests
import base64
import logging
_logger = logging.getLogger(__name__)

class SaleOrderInherit(models.Model):
    _inherit = 'sale.order'
    _description = 'Inherit Sale Order Module'

    nhis_number = fields.Char(string="NHIS Number")
    insurance_status = fields.Boolean(string="Insurance Status", default=False)
    payment_type = fields.Selection([
        ('cash', 'CASH'),
        ('insurance', 'INSURANCE'),
        ('free', 'FREE')
    ], string="Payment Type", default="cash")
    external_visit_uuid = fields.Char(string="External Id", help="This field is used to store visit ID of bahmni api call")
    claim_id = fields.Char(string="Claim Id")
    partner_uuid = fields.Char(string="Customer UUID", store=True, readonly=True)
   
    @api.onchange('payment_type')
    def _change_payment_type(self):
        for sale_order in self:
            if sale_order.payment_type == "cash":
                if sale_order.discount_type == "percentage" or sale_order.discount_type == "fixed":
                    _logger.info(f"Payment Type: {sale_order.payment_type}")
                    discount_head_id = sale_order.env['account.account'].search([
                        ('code', '=', 450000)
                    ]).id
                    if discount_head_id:
                        sale_order.disc_acc_id = discount_head_id
                    else:
                        raise ValidationError("Discount head not found!!")
                for sale_order_line in sale_order.order_line:
                    product_template = sale_order.env['product.template'].search([
                        ('id', '=', sale_order_line.product_template_id.id)
                    ])
                    if product_template:
                        sale_order_line.price_unit = product_template.list_price
                    else:
                        raise ValidationError("Product Not Mapped!! Please Contact Admin.")
            elif sale_order.payment_type == "insurance":
                if sale_order.discount_type == "percentage" or sale_order.discount_type == "fixed":
                    _logger.info(f"Payment Type: {sale_order.payment_type}")
                    discount_head_id = sale_order.env['account.account'].search([
                        ('code', '=', '101105')
                    ])
                    if discount_head_id:
                        sale_order.disc_acc_id = discount_head_id
                    else:
                        raise ValidationError("Discount head not found!!")
                for sale_order_line in sale_order.order_line:
                    if sale_order_line.product_template_id:
                        _logger.info("Product Template Id---->%s", sale_order_line.product_template_id) 
                        insurance_odoo = self.env['insurance.odoo.product.map'].search([
                            ('odoo_product_id', '=', sale_order_line.product_template_id.id)
                        ]) 
                        if insurance_odoo:
                            sale_order_line.price_unit = insurance_odoo.insurance_product_price 
                        else:
                            raise ValidationError("Product Not Mapped!! Please Contact Admin.")
            else:
                pass

    def check_eligibility(self):
        _logger.info("Check Eligibility")
        for rec in self:
            if rec.company_id.copayment == "yes":
                if rec.nhis_number:
                    partner_id = rec.partner_id
                    _logger.info("Partner Id:%s", partner_id)
                    elig_response = self.env['insurance.eligibility'].get_insurance_details(partner_id)
                    _logger.info("Eligibilty Response:%s", elig_response)
                    discount_head_id = self.env['account.account'].search([('code', '=', '101105')]).id
                    _logger.info("Discount head Id:%s", discount_head_id)
                    if elig_response:
                        copayment_value = elig_response.copayment_value
                        _logger.info("Copayment Value:%s", copayment_value)
                        if copayment_value > 0:
                            self.discount_type = 'percentage'
                            _logger.info("Discount Type:%s", self.discount_type)
                            self.discount_percentage = copayment_value * 100
                            _logger.info("Discount Percentage:%s", self.discount_percentage)
                            self.discount = self.amount_untaxed * (self.discount_percentage / 100)
                            _logger.info("Discount Amount:%s", self.discount)
                            self.disc_acc_id = discount_head_id
                            _logger.info("Discount Account Id:%s", self.disc_acc_id)
                    else:
                        _logger.info("No Response from the IMIS Server")
                    return {
                        'type': 'ir.actions.act_window',
                        'name': 'Check Eligibilty',
                        'res_model': 'insurance.eligibility',
                        'view_type': 'form',
                        'view_mode': 'form',
                        'res_id': elig_response.id,
                        'view_id': self.env.ref('bahmni_insurance_odoo.insurance_check_eligibility_response_view', False).id,
                        'target': 'new'
                    }
                else:
                    _logger.info("No NHIS number")
                    raise UserError("No Insuree Id, Please update and retry !")   
            else:
                company_name = rec.company_id.name
                _logger.info(f"Copayment Not Applied for {company_name}")
                raise UserError("Copayment Not Applied for %s", company_name)
  
    def action_confirm(self):
        _logger.info("#####Action Confrim Inherit#####")
        """ Confirm the given quotation(s) and set their confirmation date.

        If the corresponding setting is enabled, also locks the Sale Order.

        :return: True
        :rtype: bool
        :raise: UserError if trying to confirm locked or cancelled SO's
        """
        if self._get_forbidden_state_confirm() & set(self.mapped('state')):
            raise UserError(_(
                "It is not allowed to confirm an order in the following states: %s",
                ", ".join(self._get_forbidden_state_confirm()),
            ))

        self.order_line._validate_analytic_distribution()

        for order in self:
            order.validate_taxes_on_sales_order()
            if order.partner_id in order.message_partner_ids:
                continue
            order.message_subscribe([order.partner_id.id])

        self.write(self._prepare_confirmation_values())

        # Context key 'default_name' is sometimes propagated up to here.
        # We don't need it and it creates issues in the creation of linked records.
        context = self._context.copy()
        context.pop('default_name', None)

        self.with_context(context)._action_confirm()

        if self[:1].create_uid.has_group('sale.group_auto_done_setting'):
            # Public user can confirm SO, so we check the group on any record creator.
            self.action_done()
        
        if self.payment_type == "insurance":
            for order in self:
                _logger.info("Sale Order Id:%s", order)
                self.action_invoice_create_commons(order)
        else:
            pass

        return True

    def action_invoice_create_commons(self, order):
        _logger.info("Inside action invoice create commons overwritten")
        for order in self:
            _logger.info("Sale Order Id:%s", order)
            self.env['insurance.claim']._create_claim(order)

    
            
class SaleOrderLineInherit(models.Model):
    _inherit = 'sale.order.line'
    _description = 'Sale Order Line Inherit'
    
    payment_type = fields.Selection([
        ('cash', 'CASH'),
        ('insurance', 'INSURANCE'),
        ('free', 'FREE')
    ], string="Payment Type", related="order_id.payment_type", readonly=False)
                    
    # @api.constrains('lot_id')
    # def _check_lot(self):
    #     for rec in self:
    #         if rec.order_id.shop_id == "pharmacy":
    #             if rec.product_id:
    #                 if not rec.lot_id:
    #                     _logger.info("Lot Id is required for Storable Produts")
    #                     raise ValidationError("Lot Id is required for Storable Produts")
                    
                    
            
        
