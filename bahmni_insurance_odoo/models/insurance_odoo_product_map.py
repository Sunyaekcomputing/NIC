from odoo import api, models, fields

class InsuranceOdooProductMap(models.Model):
    _name = 'insurance.odoo.product.map'
    _description = 'Insurance Odoo Product Map'

    item_code = fields.Char(string="Item Code", required=True)
    insurance_product_name = fields.Char(string="Insurance Product Name")
    insurance_product_price = fields.Float(string="Insurance Product Price")
    odoo_product_id = fields.Many2one('product.product', string="Odoo Product")
    valid_from = fields.Date(string="Valid From")
    valid_to = fields.Date(string="Valid To")
    cap_validation = fields.Selection([
        ('yes', 'Yes'),
        ('no', 'No'),
        ('tmc', 'Three Months Capping'),
        ('oyc', 'One Year Capping')
    ], string="Medicine For Cap Validation")
    capping_number = fields.Integer(string="Capping Number(Per Visit)")
    is_active = fields.Boolean(string="Is Active", default=True)
