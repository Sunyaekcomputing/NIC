from odoo import api, models, fields, _
from odoo.exceptions import ValidationError, UserError
import odoo.addons.decimal_precision as dp
import logging
_logger = logging.getLogger(__name__)

class SaleOrderInherit(models.Model):
    _inherit = 'sale.order'
    _description = 'Inherit Sale Order Module'

    nhis_number = fields.Char(string="NHIS Number")
    insurance_status = fields.Boolean(string="Insurance Status", default=False)
    payment_type = fields.Selection(selection="_get_payment_type_data", string="Payment Type", default="cash")
    external_visit_uuid = fields.Char(string="External Id", help="This field is used to store visit ID of bahmni api call")
    claim_id = fields.Char(string="Claim Id")
    partner_uuid = fields.Char(string="Customer UUID", store=True, readonly=True)
    is_apply_copayment_checked = fields.Integer(string="Is Apply Copayment Checked", store=True)
    
    @api.model
    def _get_payment_type_data(self):
        returnData = []
        payment_type_ids = self.env['payment.types'].search([])
        if payment_type_ids:
            for pt in payment_type_ids:
                data = payment_type_ids.browse(pt.id)
                returnData.append((data.key, data.value))
        return returnData

    @api.onchange('payment_type')
    def _change_payment_type(self):
        for sale_order in self:
            if sale_order.payment_type == "cash":
                if sale_order.discount_type == "percentage" or sale_order.discount_type == "fixed":
                    _logger.info(f"Payment Type: {sale_order.payment_type}")
                    discount_head_id = sale_order.env['account.account'].search([
                        ('code', '=', 450000)
                    ]).id
                    if discount_head_id:
                        sale_order.disc_acc_id = discount_head_id
                    else:
                        raise UserError("Discount head not found!!")
                for sale_order_line in sale_order.order_line:
                    product_template = sale_order.env['product.template'].search([
                        ('id', '=', sale_order_line.product_template_id.id)
                    ])
                    if product_template:
                        sale_order_line.price_unit = product_template.list_price
                    else:
                        raise UserError("Product Not Mapped!! Please Contact Admin.")
            elif sale_order.payment_type == "insurance":
                if sale_order.discount_type == "percentage" or sale_order.discount_type == "fixed":
                    _logger.info(f"Payment Type: {sale_order.payment_type}")
                    discount_head_id = sale_order.env['account.account'].search([
                        ('code', '=', '101105')
                    ])
                    if discount_head_id:
                        sale_order.disc_acc_id = discount_head_id
                    else:
                        raise UserError("Discount head not found!!")
                for sale_order_line in sale_order.order_line:
                    if sale_order_line.product_template_id:
                        _logger.info("Product Template Id---->%s", sale_order_line.product_template_id) 
                        insurance_odoo = self.env['insurance.odoo.product.map'].search([
                            ('odoo_product_id', '=', sale_order_line.product_template_id.id)
                        ]) 
                        if insurance_odoo:
                            sale_order_line.price_unit = insurance_odoo.insurance_product_price 
                        else:
                            raise UserError("Product Not Mapped!! Please Contact Admin.")
            else:
                pass

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
                else:
                    _logger.info("No product added in the sale order line")

    def check_eligibility(self):
        _logger.info("Check Eligibility")
        self.cap_validation()
        for rec in self:
            if rec.company_id.copayment == "yes":
                self.is_apply_copayment_checked = 1
                if rec.nhis_number:
                    partner_id = rec.partner_id
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
                    _logger.info("No NHIS number")
                    raise UserError("No Insuree Id, Please update and retry !")   
            else:
                company_name = rec.company_id.name
                _logger.info(f"Copayment Not Applied for {company_name}")
                raise UserError("Copayment Not Applied for %s", company_name)
            
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

        # Getting Id for Insurance Journal
        # insurance_connect_configurations = self.env['insurance.config.settings'].get_values()
        # _logger.info("Insurance Connect Configurations:%s", insurance_connect_configurations)
        # insurance_journal_name = insurance_connect_configurations['insurance_journal']
        # _logger.info("Insurance Journal Name:%s", insurance_journal_name)
        # insurance_journal_id = self.env['account.account'].search([
        #     ('name', 'ilike', insurance_journal_name)
        # ])
        # _logger.info("Insurance Journal Account Id:%s", insurance_journal_id)
        for rec in self:
            _logger.info("Sale Order Id:%s", rec)
            payment_type = rec.payment_type
            if payment_type:
                _logger.info("Payment Type:%s", payment_type)
                journal_id = rec.env['payment.journal.mapping'].search([
                    ('payment_type', '=', payment_type)
                ]).journal_id.id
                _logger.info("Journal Id:%s", journal_id)

                if not journal_id:
                    raise UserError("Please define a journal for this company")
            else:
                raise UserError("Please add a payment type")

            if bool(rec.env['ir.config_parameter'].sudo().get_param('bahmni_sale.is_invoice_automated')):
                create_invoices = rec._create_invoices()
                _logger.info("****Created Invoices*****")
                _logger.info("Account Invoice Id:%s", create_invoices)
                self.action_invoice_create_commons(rec)
                
                """Pass lot/serial number value from sale order to stock picking model"""
                for sale_order in self:
                    pickings = sale_order.picking_ids.filtered(
                        lambda p: p.picking_type_code == "outgoing" and p.state not in ['done', 'cancel']
                    )
                    _logger.info("Picking Id:%s", pickings)

                    for picking in pickings: #stock.picking
                        for move in picking.move_ids_without_package: #stock.move
                            for ml in move.move_line_ids: #stock.move.line
                                sale_line = sale_order.order_line.filtered(lambda l: l.product_id == move.product_id and l.lot_id == ml.lot_id)
                                if not sale_line:
                                    _logger.warning("No matching sale line found for product %s in %s", move.product_id.display_name, sale_order.name)
                                    continue
                        
                                matched_line = sale_line[0]
                                _logger.info("Matched Line:%s", matched_line)
                                ml.qty_done = matched_line.product_uom_qty
                                _logger.info("Updated qty done=%s for product:%s lot:%s", ml.qty_done, move.product_id.display_name, ml.lot_id.display_name)

                        # Validate the picking once all moves are updated
                        picking.button_validate()
                        _logger.info("Picking %s validated for Sale Order %s", picking.name, sale_order.name)

                if rec.env.user.has_group('bahmni_sale.group_redirect_to_payments_on_sale_confirm'):
                    _logger.info("Inside bahmni_sale.group_redirect_to_payments_on_sale_confirm")
                    action = {
                        'name': _('Payments'),
                        'type': 'ir.actions.act_window',
                        'res_model': 'account.payment.register',
                        'context': {
                            'active_model': 'account.move',
                            'active_ids': create_invoices.id,
                            'default_journal_id': journal_id,
                        },
                        'view_mode': 'form',
                        'target': 'new'
                    }
                    _logger.info("Action:%s", action)
                    return action
        return True
    
    def action_invoice_create_commons(self, order):
        _logger.info("Inside action invoice create commons overwritten")
        for order in self:
            _logger.info("Sale Order Id:%s", order)
            self.env['insurance.claim']._create_claim(order)

    def _prepare_invoice(self):
        _logger.info("Inside _prepare_invoice")
        res = super(SaleOrderInherit, self)._prepare_invoice()
        res['nhis_number'] = self.nhis_number
        res['claim_id'] = self.claim_id
        return res

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

                    
                    
            
        