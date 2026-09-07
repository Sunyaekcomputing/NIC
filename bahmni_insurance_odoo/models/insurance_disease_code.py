from odoo import api, models, fields

class InsuranceDiseaseCode(models.Model):
    _name = 'insurance.disease.code'
    _description = 'Insurance Disease Code'

    icd_code = fields.Char(string="ICD Code")
    diagnosis = fields.Char(string="Diagnosis")
    is_active = fields.Boolean(string="Active", default=True)