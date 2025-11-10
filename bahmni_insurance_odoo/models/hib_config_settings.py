from odoo import api, models, fields
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)

class Hib_Connect(models.Model):
    _name = 'hib.config.settings'
    _description = "Claim Document Username and Password"

    username = fields.Char(string="Username", help="Username of the health insurance board")
    password = fields.Char(string="Password", help="Password of the health insurance board")
    remote_user = fields.Char(string="Remote User", help="Remote User of the health insurance board")
    active = fields.Boolean(string="Is Active")