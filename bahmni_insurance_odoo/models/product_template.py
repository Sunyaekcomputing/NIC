from odoo import api, models, fields

class ProductTemplate(models.Model):
    _inherit='product.template'
    _description = 'Product Template Inherit'

    shop_id = fields.Selection([
        ('registration', 'Registration'),
        ('pharmacy', 'Pharmacy')
    ], string="Selling Department")