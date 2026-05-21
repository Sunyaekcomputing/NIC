from odoo import api, fields, models
import logging
_logger = logging.getLogger(__name__)

class ResPartner(models.Model):
    _inherit = 'res.partner'

    birth_date = fields.Date(string="Date of Birth")
    gender = fields.Selection([
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other')
    ], string="Gender")

    def name_get(self):
        res = []
        for partner in self:
            name = partner.name or ''
            if partner.ref:
                name += ' [' + partner.ref + ']'
            res.append((partner.id, name))
        return res
    
    def _get_nhis_number(self, partner_id):
        _logger.info("Inside _get_nhis_number")
        attributes = self.env['res.partner.attributes'].search([
            ('partner_id', '=', partner_id),
            ('name', '=', 'NHIS Number')
        ])
        if attributes:
            return attributes.value
        
    def _get_nhis_status(self, partner_id):
        _logger.info("Inside _get_nhis_status")
        attributes = self.env['res.partner.attributes'].search([
            ('partner_id', '=', partner_id),
            ('name', '=', 'NHIS Member Active')
        ])
        if attributes:
            return attributes.value
    
    def _get_claim_id(self, partner_id):
        _logger.info("Inside _get_claim_id")
        attributes = self.env['res.partner.attributes'].search([
            ('partner_id', '=', partner_id),
            ('name', '=', 'Claim Code')
        ])
        if attributes:
            return attributes.value
        



    