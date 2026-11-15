# Copyright 2026 Vertel AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "PIM Change",
    "summary": "Field level change proposals with review before the value is written",
    "version": "18.0.1.0.0",
    "category": "PIM",
    "license": "AGPL-3",
    "author": "Vertel AB,Odoo Community Association (OCA)",
    "website": "https://github.com/vertelab/odoo-pim",
    "depends": [
        "pim_channel",
        "mail",
    ],
    "data": [
        "security/pim_change_security.xml",
        "security/ir.model.access.csv",
        "security/pim_change_rules.xml",
        "data/ir_cron_data.xml",
        "wizards/pim_change_confirm_wizard_views.xml",
        "views/pim_change_policy_views.xml",
        "views/pim_change_proposal_views.xml",
        "views/product_template_views.xml",
    ],
    "installable": True,
    "application": False,
}
