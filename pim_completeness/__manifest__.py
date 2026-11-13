# Copyright 2026 Vertel AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "PIM Completeness",
    "summary": "Measure how complete product information is per channel and language",
    "version": "18.0.1.0.0",
    "category": "PIM",
    "license": "AGPL-3",
    "author": "Vertel AB,Odoo Community Association (OCA)",
    "website": "https://github.com/vertelab/odoo-pim",
    "depends": [
        "pim_channel",
    ],
    "data": [
        "security/pim_completeness_security.xml",
        "security/ir.model.access.csv",
        "data/ir_cron_data.xml",
        "views/pim_completeness_rule_views.xml",
        "views/pim_completeness_views.xml",
        "views/product_template_views.xml",
    ],
    "installable": True,
    "application": False,
}
