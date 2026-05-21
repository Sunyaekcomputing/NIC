from odoo import api, models, fields, _
from odoo.exceptions import ValidationError, UserError, AccessError
import odoo.addons.decimal_precision as dp
from itertools import groupby
from odoo.fields import Command
import requests
import logging
_logger = logging.getLogger(__name__)

class SaleOrderInherit(models.Model):
    _inherit = 'sale.order'
    _description = 'Inherit Sale Order Module'

    nhis_number = fields.Char(string="NHIS Number", compute="_get_insurance_details")
    insurance_status = fields.Boolean(string="Insurance Status", default=False, compute="_get_insurance_details")
    payment_type = fields.Selection(selection="_get_payment_type_data", string="Payment Type", default="cash")
    external_visit_uuid = fields.Char(string="External Id", help="This field is used to store visit ID of bahmni api call")
    claim_id = fields.Char(string="Claim Id", compute="_get_insurance_details")
    partner_uuid = fields.Char(string="Customer UUID", store=True, readonly=True)
    is_apply_copayment_checked = fields.Integer(string="Is Apply Copayment Checked", store=True)
    visit_type = fields.Char(string="Visit Type", store=True)
    
    @api.onchange('partner_id')
    def _get_insurance_details(self):
        _logger.info("Inside _get_insurance_details")
        for sale_order in self:
            partner_id = sale_order.partner_id.id
            _logger.info("Partner Id=%s",partner_id)
            if partner_id:
                nhis_number = self.env['res.partner']._get_nhis_number(partner_id)
                insurance_status = self.env['res.partner']._get_nhis_status(partner_id)
                _logger.info("Insurance Status=%s", insurance_status)                   
                claim_id = self.env['res.partner']._get_claim_id(partner_id)
                sale_order.nhis_number = nhis_number
                if insurance_status == 'true':
                    sale_order.insurance_status = True
                else:
                    sale_order.insurance_status = False
                sale_order.claim_id = claim_id

    @api.onchange('shop_id')
    def add_discount_for_pharmacy(self):
        _logger.info("Inside add_discount_for_pharmacy")
        for sale_order in self:
            shop_id = sale_order.shop_id.id
            if shop_id == 1:
                if sale_order.payment_type == "cash":
                    sale_order.discount_type = 'percentage'
                    sale_order.discount_percentage = 0.0
                    discount_head_id = sale_order.env['account.account'].search([
                        ('code', '=', 450000)
                    ]).id
                    sale_order.disc_acc_id = discount_head_id
                else:
                    sale_order.discount_type = 'none'
            else:
                sale_order.discount_type = 'none'
            
    @api.model
    def _get_payment_type_data(self):
        returnData = []
        payment_type_ids = self.env['payment.types'].search([])
        if payment_type_ids:
            for pt in payment_type_ids:
                data = payment_type_ids.browse(pt.id)
                returnData.append((data.key, data.value))
        return returnData
    
    def _get_insurance_cost(self, product_id):
        _logger.info("Inside _get_insurance_cost")
        _logger.info("Product Id=%s", product_id)
        map_id = self.env['insurance.odoo.product.map'].search([
            ('odoo_product_id', '=', product_id)
        ])
        _logger.info("Map Id=%s", map_id) 
        if len(map_id) == 0:
            return 1777.17
        else:
            return map_id[0].insurance_product_price 

    @api.onchange('payment_type')
    def _change_payment_type(self):
        _logger.info("Inside _change_payment_type")
        has_error = False
        error_products = ""
        counter = 1
        for sale_order in self:
            shop_id = sale_order.shop_id.id
            if shop_id == 1:
                if sale_order.payment_type == "cash":
                    sale_order.discount_type == 'percentage'
                    sale_order.discount_percentage = 0.0
                    discount_head_id = sale_order.env['account.account'].search([
                        ('code', '=', 450000)
                    ]).id
                    sale_order.disc_acc_id = discount_head_id
                else:
                    sale_order.discount_type = 'none'
            else:
                sale_order.discount_type = 'none'

            for sale_order_line in sale_order.order_line:
                product_id = sale_order_line.product_id
                if sale_order.payment_type == "insurance":
                    if self.nhis_number:
                        insurance_cost = self._get_insurance_cost(product_id.id)
                        if insurance_cost == 1777.17:
                            has_error = True
                            if product_id.name not in error_products:
                                error_products += error_products + "\n" + str(counter) + ". " + str(product_id.name)
                                counter += 1
                            sale_order_line.update({
                                'payment_type': sale_order.payment_type,
                            })
                        else:
                            sale_order_line.update({
                                'payment_type': sale_order.payment_type,
                                'price_unit': insurance_cost
                            })
                    else:
                        sale_order.payment_type = 'cash'
                        return {
                            'warning': {
                            'title': 'Warning !!',
                            'message': 'Payment type \'Insurance\' can be selected only for patient with the valid insurance id',
                        }}
                else:
                    sale_order_line.update({
                        'payment_type': sale_order.payment_type,
                        'price_unit': product_id.lst_price
                    })
        if has_error == True:
            return {
                'warning': {
                    'title': 'Warning !!',
                    'message': 'All product in the list are not available for insurance claim. Please contact admin.\nProducts are :\n' + str(error_products) 
                }
            }
                            
    def cap_validation(self):
        _logger.info("Cap Validation")
        for rec in self:
            partner_id = rec.partner_id
            _logger.info("Partner Id:%s", partner_id)
            capvalidation_response = self.env['insurance.capvalidation'].get_cap_validation(partner_id)
            _logger.info("Capvalidation Response:%s", capvalidation_response)

            for line in rec.order_line:
                if line.product_id:
                    imis_mapped_row = self.env['insurance.odoo.product.map'].search([
                        ('odoo_product_id', '=', line.product_id.id),
                        ('is_active', '=', 'True')
                    ])
                    _logger.info("IMIS Mapped Row Id:%s", imis_mapped_row)
                    if imis_mapped_row:
                        if capvalidation_response:
                            _logger.info("Entered into if capvalidation response")
                            for cap_data in capvalidation_response:
                                if imis_mapped_row.item_code == cap_data['code']:
                                    _logger.info("Item Code matched with the IMIS Server")
                                    line.insurance_remain_qty = cap_data['qty_remain']
                                    _logger.info("Insurance Remaining Qty:%s", line.insurance_remain_qty)
                                    break
                                else:
                                    _logger.info("Item Code doesn't matched with the IMIS Server") 
                                    if line.product_id.id == imis_mapped_row.odoo_product_id.id:
                                        line.insurance_remain_qty = imis_mapped_row.capping_number
                        else:
                            _logger.info("Entered into else capvalidaiton response")
                            if line.product_id.id == imis_mapped_row.odoo_product_id.id:
                                line.insurance_remain_qty = imis_mapped_row.capping_number
                    else:
                        _logger.info(f"No Product Mapping Found For {line.product_id}")

    def check_eligibility(self):
        _logger.info("Check Eligibility")
        visit_data = self._get_visit_data()
        _logger.info("Visit Data=%s", visit_data)
        if visit_data:
            self.external_visit_uuid = visit_data.get('uuid')
            visit_type = visit_data.get("visitType").lower()
            self.visit_type = visit_type
            _logger.info("Visit Type=%s", self.visit_type)
            if self.visit_type == 'opd' or self.visit_type == 'emergency':
                self.care_setting = 'opd'
            else:
                self.care_setting = 'ipd'
            _logger.info("Care Setting=%s", self.care_setting)
        else:
            _logger.info("No Visit Data")
        
        self.cap_validation()
        
        if self.company_id.copayment == "yes":
            self.is_apply_copayment_checked = 1
            if self.nhis_number:
                if self.visit_type not in ["emergency"]:
                    partner_id = self.partner_id
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
                    _logger.info(f"Copayment Not Allowed For Visit Type:{self.visit_type}")
            else:
                _logger.info("No NHIS number")
                raise UserError("No Insuree Id, Please update and retry !")   
        else:
            company_name = self.company_id.name
            _logger.info(f"Copayment Not Applied for {company_name}")
            raise UserError("Copayment Not Applied for %s", company_name)
            
    def _get_visit_data(self):
        _logger.info("Inside _get_visit_data")
        openmrs_connect_configurations = self.env['insurance.config.settings'].get_values()
        _logger.info("Openmrs Configuration=%s", openmrs_connect_configurations)
        if not openmrs_connect_configurations:
            raise UserError("OpenMRS Configuration Not Set!!")
        
        insurance_connect = self.env['insurance.connect']
        
        if self.payment_type not in ['cash']:
            partner_uuid = self.partner_id.uuid
            url = insurance_connect.prepare_openmrs_url("/openmrs/ws/rest/v1/visit?includeInactive=false&patient={}".format(partner_uuid), openmrs_connect_configurations)
            _logger.info("Url=%s", url)

            custom_headers = {
                'Content-Type': 'application/json'
            }
            headers = insurance_connect.get_openmrs_header(openmrs_connect_configurations)
            custom_headers.update(headers)
            response = requests.get(url, headers=custom_headers, verify=False)
            _logger.info("Response=%s", response)

            if response.status_code == 200:
                resp = response.json()
                _logger.info("Resp=%s", resp)
                visit_uuid = response.json()["results"][0]["uuid"]
                _logger.info("Visit Uuid=%s", visit_uuid)
                visit_url = insurance_connect.prepare_openmrs_url("/openmrs/ws/rest/v1/bahmnicore/visit/summary?visitUuid={}".format(visit_uuid), openmrs_connect_configurations)
                _logger.info("Visit Url=%s", visit_url)
                custom_headers = {
                    'Content-Type': 'application/json'
                }
                headers = insurance_connect.get_openmrs_header(openmrs_connect_configurations)
                custom_headers.update(headers)
                visit_response = requests.get(visit_url, headers=custom_headers, verify=False)
                if visit_response.status_code == 200:
                    visit_data = visit_response.json()
                    return visit_data
            elif response.status_code == 401:
                _logger.info("Please Check Credentials for Openmrs Connect Configuration and Try Again")
                raise UserError("Please Check Credentials for Openmrs Connect Configuration and Try Again")

    def action_confirm(self):
        _logger.info("Inside overridden action_confirm")
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
        
        if self.payment_type == "insurance":
            if self.nhis_number:
                if self.is_apply_copayment_checked == 1:
                    _logger.info("Apply Copayment Button Clicked:%s", self.is_apply_copayment_checked)
                    for line in self.order_line:
                        if line.product_id:
                            _logger.info("Product Name:%s", line.product_id.name)
                            imis_mapped_row = self.env['insurance.odoo.product.map'].search([
                                ('odoo_product_id', '=', line.product_id.id),
                                ('is_active', '=', 't')
                            ])
                            _logger.info("IMIS Mapped Row Id:%s", imis_mapped_row)
                            if imis_mapped_row:
                                if imis_mapped_row.cap_validation == "yes":
                                    _logger.info("Cap Validation:%s", imis_mapped_row.cap_validation)
                                    if line.product_id.detailed_type == "product":
                                        _logger.info("****Stockable Product****")
                                        if line.insurance_remain_qty > 0:
                                            if line.product_uom_qty > line.insurance_remain_qty:
                                                _logger.info("Only %s quantity left for the product '%s'"%(line.insurance_remain_qty, line.product_id.name))
                                                raise ValidationError("Only %s quantity left for the product '%s'"%(line.insurance_remain_qty, line.product_id.name))
                                            else:
                                                _logger.info("Stockable Produce Else Running")
                                                pass
                                        else:
                                            _logger.info("%s quantity left for the product '%s'"%(line.insurance_remain_qty, line.product_id.name))
                                            raise ValidationError("%s quantity left for the product '%s'"%(line.insurance_remain_qty, line.product_id.name))
                                    else:
                                        _logger.info("****Service****")
                                        if line.insurance_remain_qty > 0:
                                            if line.product_uom_qty > line.insurance_remain_qty:
                                                _logger.info("Only %s quantity left for the test '%s'"%(line.insurance_remain_qty, line.product_id.name))
                                                raise ValidationError("Only %s quantity left for the test '%s'"%(line.insurance_remain_qty, line.product_id.name))
                                            else:
                                                _logger.info("Service Else Running")
                                                pass
                                        else:
                                            raise ValidationError("%s quantity left for the test '%s'"%(line.insurance_remain_qty, line.product_id.name))
                                elif imis_mapped_row.cap_validation == "no":
                                    _logger.info("Cap Validation:%s", imis_mapped_row.cap_validation)
                                    if line.product_id.detailed_type == "product":
                                        _logger.info("****Stockable Product****")
                                        if line.product_uom_qty > line.insurance_remain_qty:
                                            _logger.info("The capping quantity for the product '%s' is only %s"%(line.product_id.name, line.insurance_remain_qty))
                                            raise ValidationError("The capping quantity for the product '%s' is only %s"%(line.product_id.name, line.insurance_remain_qty))
                                        else:
                                            _logger.info("Stockable Produce Else Running")
                                            pass 
                                    else:
                                        _logger.info("****Service****")
                                        if line.product_uom_qty > line.insurance_remain_qty:
                                            _logger.info("The capping quantity for the test '%s' is only %s"%(line.product_id.name, line.insurance_remain_qty))
                                            raise ValidationError("The capping quantity for the test '%s' is only %s"%(line.product_id.name, line.insurance_remain_qty))
                                        else:
                                            _logger.info("Service Else Running")
                                            pass  
                                elif imis_mapped_row.cap_validation == "tmc":
                                    _logger.info("Cap Validation:%s", imis_mapped_row.cap_validation)
                                    if line.product_id.detailed_type == "service":
                                        _logger.info("****Service****")
                                        if line.product_uom_qty > line.insurance_remain_qty:
                                            _logger.info("Only %s quantity left for the test '%s'"%(line.insurance_remain_qty, line.product_id.name))
                                            raise ValidationError("Only %s quantity left for the test '%s'"%(line.insurance_remain_qty, line.product_id.name))
                                        else:
                                            _logger.info("Service Else Running")
                                            pass
                                elif imis_mapped_row.cap_validation == "oyc":
                                    _logger.info("Cap Validation:%s", imis_mapped_row.cap_validation)
                                    if line.product_id.detailed_type == "service":
                                        _logger.info("****Service****")
                                        if line.product_uom_qty > line.insurance_remain_qty:
                                            _logger.info("Only %s quantity left for the test '%s'"%(line.insurance_remain_qty, line.product_id.name))
                                            raise ValidationError("Only %s quantity left for the test '%s'"%(line.insurance_remain_qty, line.product_id.name))
                                        else:
                                            _logger.info("Service Else Running")
                                            pass
                                else:
                                    _logger.info("Cap Validation:%s", imis_mapped_row.cap_validation)
                                    pass
                            else:
                                raise UserError("No Product Mapping Found For"%(line.product_id.name))
                        else:
                            raise UserError("Product Not Added !!")
                else:
                    _logger.info("Apply Copayment Button must be clicked when the payment type is insurance")
                    raise UserError("Apply Copayment Button must be clicked when the payment type is insurance")
            else:
                _logger.info("NHIS Number cannot be Null!")
                raise UserError("NHIS Number cannot be Null!")
        else:
            _logger.info("#####Else#####")
            _logger.info("Payment Type:%s", self.payment_type)
            self.is_apply_copayment_checked = 1

        if self[:1].create_uid.has_group('sale.group_auto_done_setting'):
            # Public user can confirm SO, so we check the group on any record creator.
            self.action_done()
        
        for line in self.order_line:
            if line.display_type in ('line_section', 'line_note'):
               continue
            if line.product_uom_qty <=0:
               raise UserError("Quantity for %s is %s. Please update the quantity or remove the product line."%(line.product_id.name,line.product_uom_qty))
            if line.product_id.tracking == 'lot' and not line.lot_id:
               raise UserError("Kindly choose batch no for %s to proceed further."%(line.product_id.name))
            if 1 < self.order_line.search_count([('lot_id', '=', line.lot_id.id),('order_id', '=', self.id)]) and line.lot_id:
              raise UserError("%s Duplicate batch no is not allowed. Kindly change the batch no to proceed further."%(line.lot_id.name))
            if line.product_uom_qty > line.lot_id.product_qty and line.lot_id:
              raise UserError("Insufficient batch(%s) quantity for %s and available quantity is %s"\
                            %(line.lot_id.name, line.product_id.name, line.lot_id.product_qty))
        
        self.validate_delivery()

        for order in self:
            warehouse = order.warehouse_id
            if order.picking_ids and bool(self.env['ir.config_parameter'].sudo().get_param('bahmni_sale.is_delivery_automated')):
                for picking in self.picking_ids:
                    picking.immediate_transfer = True
                    for move in picking.move_ids:
                        move.quantity_done = move.product_uom_qty
                    picking._autoconfirm_picking()
                    picking.action_set_quantities_to_reservation()
                    picking.action_confirm()
                    for move_line in picking.move_ids_without_package:
                        move_line.quantity_done = move_line.product_uom_qty
                    picking._action_done()
                    for mv_line in picking.move_ids.mapped('move_line_ids'):
                        if not mv_line.qty_done and mv_line.reserved_qty or mv_line.reserved_uom_qty:
                            mv_line.qty_done = mv_line.reserved_qty or mv_line.reserved_uom_qty

        payment_type = self.payment_type
        if payment_type:
            _logger.info("Payment Type:%s", payment_type)
            journal_id = self.env['payment.journal.mapping'].search([
                ('payment_type', '=', payment_type)
            ]).journal_id.id
            _logger.info("Journal Id:%s", journal_id)

            if not journal_id:
                raise UserError("Please define a journal for this company")
        else:
            raise UserError("Please add a payment type")
        
        if bool(self.env['ir.config_parameter'].sudo().get_param('bahmni_sale.is_invoice_automated')):
            create_invoices = self._create_invoices()
            _logger.info("****Created Invoices*****")
            _logger.info("Account Invoice Id:%s", create_invoices)
            self.action_invoice_create_commons(self)
            
            if self.env.user.has_group('bahmni_sale.group_redirect_to_payments_on_sale_confirm'):
                _logger.info("Inside bahmni_sale.group_redirect_to_payments_on_sale_confirm")
                action = {
                    'name': _('Payments'),
                    'type': 'ir.actions.act_window',
                    'res_model': 'account.payment.register',
                    'context': {
                        'active_model': 'account.move',
                        'active_ids': create_invoices.ids,
                        'default_journal_id': journal_id,
                    },
                    'view_mode': 'form',
                    'target': 'new'
                }
                _logger.info("Action:%s", action)
                return action
        return True
    
    def _prepare_invoice(self):
        _logger.info("Inside overridden _prepare_invoice")
        self.ensure_one()
        
        amount_total = self.amount_untaxed + self.amount_tax
        if self.discount_percentage:
            tot_discount = amount_total * self.discount_percentage / 100
        else:
            tot_discount = self.discount

        '''
            Check payment type
            If payment type is cash then default journal i.e. cash
            If payment type is insurance then use insurance journal
        '''
        payment_type = self.payment_type
        if payment_type:
            _logger.info("Payment Type:%s", payment_type)
            journal_id = self.env['invoice.journal.mapping'].search([
                ('payment_type', '=', payment_type)
            ], limit=1).journal_id.id
            _logger.info("Journal Id:%s", journal_id)

            if not journal_id:
                raise UserError("Please define a journal for this company")
        else:
            raise UserError("Please add a payment type")
            
        invoice_vals = (self._prepare_invoice_commons(tot_discount, journal_id, payment_type))
        _logger.debug("Invoice Vals:%s", invoice_vals)
        return invoice_vals

    def _prepare_invoice_commons(self, tot_discount, journal_id, payment_type):
        _logger.info("Inside _prepare_invoice_commons")
        invoice_vals = {
            'ref': self.client_order_ref or '',
            'move_type': 'out_invoice',
            'partner_id': self.partner_invoice_id.id,
            'partner_shipping_id': self.partner_shipping_id.id,
            'currency_id': self.pricelist_id.currency_id.id,
            'narration': self.note,
            'invoice_payment_term_id': self.payment_term_id.id,
            'fiscal_position_id': self.fiscal_position_id.id or self.partner_invoice_id.property_account_position_id.id,
            'company_id': self.company_id.id,
            'user_id': self.user_id and self.user_id.id,
            'team_id': self.team_id.id,
            'invoice_line_ids': [],
            'invoice_origin': self.name,
            'payment_reference': self.reference,
            'discount_type': self.discount_type,
            'discount_percentage': self.discount_percentage,
            'disc_acc_id': self.disc_acc_id.id,
            'discount': tot_discount,
            'round_off_amount': self.round_off_amount,
            'order_id': self.id,
            'amount_total': self.amount_total,
            'journal_id': journal_id,
            'move_payment_type': payment_type,
            'nhis_number': self.nhis_number,
            'claim_id': self.claim_id 
        }
        return invoice_vals

    def action_invoice_create_commons(self, order):
        _logger.info("Inside action_invoice_create_commons")
        for order in self:
            _logger.info("Sale Order Id:%s", order)
            self.env['insurance.claim']._create_claim(order)
class SaleOrderLineInherit(models.Model):
    _inherit = 'sale.order.line'
    _description = 'Sale Order Line Inherit'
    
    payment_type = fields.Selection(selection="_get_payment_type_data", string="Payment Type", related="order_id.payment_type", readonly=False)
    insurance_remain_qty = fields.Integer(string="Ins Rem Qty", readonly=True)

    @api.model
    def _get_payment_type_data(self):
        returnData = []
        payment_type_ids = self.env['payment.types'].search([])
        if payment_type_ids:
            for pt in payment_type_ids:
                data = payment_type_ids.browse(pt.id)
                returnData.append((data.key, data.value))
        return returnData
    # @api.constrains('lot_id')
    # def _check_lot(self):
    #     for rec in self:
    #         if rec.order_id.shop_id == "pharmacy":
    #             if rec.product_id:
    #                 if not rec.lot_id:
    #                     _logger.info("Lot Id is required for Storable Produts")
    #                     raise ValidationError("Lot Id is required for Storable Produts")
    
    @api.onchange('product_id')
    def _onchange_shop_id(self):
        if not self.order_id.shop_id:
            return {}

        shop_id = self.order_id.shop_id.id

        products = self.env['product.product'].search([
            ('shop_id', '=', shop_id)
        ])

        return {
            'domain': {
                'product_id': [('id', 'in', products.ids)]
            }
        }

                    
                    
            
        