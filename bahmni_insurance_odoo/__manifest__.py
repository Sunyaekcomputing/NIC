{
    'name': "Bahmni Insurance Odoo",
    'version': '1.0',
    'summary': "Bahmni Insurance Odoo",
    'description': """
        Bahmni Insurance Odoo
    """,
    'author': "Rijan Maharjan",
    'website': "",
    'depends': ['sale', 'stock', 'purchase'],
    'data': [
        'security/insurance_security.xml',
        'security/ir.model.access.csv',
        # 'data/ir_cron.xml',
        'views/menu_view.xml',
        'views/sale_order_view.xml',
        'views/insurance_claim_view.xml',
        'views/payment_type_view.xml',
        'views/insurance_odoo_product_map_view.xml',
        'views/payment_journal_mapping_view.xml',
        'views/insurance_disease_code_view.xml',
        'views/product_template_view.xml',
        'views/insurance_config_settings_view.xml',
        # 'views/stock_lot_view.xml'
    ],
    'installable': True,
    'application': True,
    "sequence":-100,
}