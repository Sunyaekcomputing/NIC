from odoo import api, fields, models
from odoo.exceptions import ValidationError, UserError

class ResCompany(models.Model):
    _inherit = 'res.company'

    hospital_type = fields.Selection([
        ('phc', 'PHC'),
        ('hospital', 'Hospital')
    ], string="Hospital Type", default="hospital")

    copayment = fields.Selection([
        ('yes', 'YES'),
        ('no', 'NO')
    ], string="Copayment", default="no")