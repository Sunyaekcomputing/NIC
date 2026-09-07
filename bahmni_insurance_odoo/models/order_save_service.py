from odoo import api, models, fields
from odoo.exceptions import ValidationError, UserError
import logging
_logger = logging.getLogger(__name__)

class OrderSaveService(models.Model):
    _name = 'order.save.service'
    _inherit = 'order.save.service'

    def _get_insurance_cost(self, product_id):
        map_id = self.env['insurance.odoo.product.map'].search([
            ('odoo_product_id', '=', product_id)
        ], limit=10)
        _logger.info("Map Id=%s", map_id)
        if len(map_id) == 0:
            return product_id.lst_price 
        else:
            return map_id[0].insurance_product_price
            
    @api.model
    def create_orders(self, vals):
        _logger.info("Inside overridden create_orders")
        all_orders = super(OrderSaveService, self)._get_openerp_orders(vals)
        _logger.info("All Orders=%s", all_orders)
        if not all_orders:
            return ""
        
        visit_uuid = all_orders[0].get("visitId")
        _logger.info("Visit Uuid:%s", visit_uuid)
        encounter_uuid = vals.get("encounter_id")
        _logger.info("Encoutner Uuid:%s", encounter_uuid)
        
        super(OrderSaveService, self).create_orders(vals)

        # search sale order line based on encounter id
        sale_order_lines_in_db = self.env['sale.order.line'].search([('external_id', '=', encounter_uuid)])
        _logger.info("Sale Order Lines In DB=%s", sale_order_lines_in_db)

        customer_id = vals.get("customer_id")

        partner_id = self.env['res.partner'].search([('ref', '=', customer_id)]).id

        nhis_number = self.env['res.partner']._get_nhis_number(partner_id)
        _logger.info("NHIS Number=%s", nhis_number)

        if nhis_number:
            payment_type = 'insurance'
        else:
            payment_type = 'cash'
            
        _logger.info("Payment Type=%s", payment_type)

        if sale_order_lines_in_db:
            _logger.info("Sale order line found")
            sale_order = sale_order_lines_in_db[0].order_id
            _logger.info("Order Id=%s", sale_order)
            sale_order.update({
                'external_visit_uuid': visit_uuid,
                'payment_type': payment_type
            })
            
            for sale_order_line in sale_order_lines_in_db:
                if payment_type == 'insurance':
                    product_id = sale_order_line.product_id.id
                    insurance_cost = self._get_insurance_cost(product_id)
                    _logger.info("Insurance Cost=%s", insurance_cost)
                    sale_order_line.update({
                        'payment_type': payment_type,
                        'price_unit': insurance_cost
                    })
                elif payment_type == 'cash':
                    sale_order_line.update({
                        'payment_type': payment_type
                    })
                    discounted_percentage = 0.0
                    discount_head_id = sale_order.env['account.account'].search([
                        ('code', '=', 450000)
                    ]).id
                    if sale_order.shop_id.id == 1:
                        sale_order.update({
                            'discount_type': 'percentage',
                            'discount_percentage':discounted_percentage,
                            'disc_acc_id': discount_head_id
                        })

                    



            




