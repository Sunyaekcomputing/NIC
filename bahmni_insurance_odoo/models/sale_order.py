from odoo import api, models, fields
from odoo.exceptions import ValidationError, UserError
import odoo.addons.decimal_precision as dp

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
                if sale_order.discount_type == "percent" or sale_order.discount_type == "amount":
                    _logger.info("########Entered#######")
                    discount_head_id = sale_order.env['account.account'].search([
                        ('code', '=', 1010001)
                    ]).id
                    if discount_head_id:
                        sale_order.discount_head = discount_head_id
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
                if sale_order.discount_type == "percent" or sale_order.discount_type == "amount":
                    _logger.info("########Entered#######")
                    discount_head_id = sale_order.env['account.account'].search([
                        ('code', '=', 1010002)
                    ])
                    if discount_head_id:
                        sale_order.discount_head = discount_head_id
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
                    
                    
            
        
