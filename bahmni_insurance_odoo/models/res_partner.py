from odoo import api, fields, models
import logging
_logger = logging.getLogger(__name__)

class ResPartner(models.Model):
    _inherit = 'res.partner'
    
    def _get_nhis_number(self, partner_id):
        _logger.info("Inside Get Nhis Number. Partner Id:%s", partner_id)
        attributes = self.env['res.partner.attributes'].search([
            ('partner_id', '=', partner_id),
            ('name', '=', 'NHIS Number')
        ])
        if attributes:
            return attributes.value
        



    