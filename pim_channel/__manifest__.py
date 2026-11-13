# Copyright 2026 Vertel AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "PIM Channel",
    "summary": "Channel scoping of product attributes with explicit fallback",
    "version": "18.0.1.0.2",
    "category": "PIM",
    "license": "AGPL-3",
    "author": "Vertel AB,Odoo Community Association (OCA)",
    "website": "https://github.com/vertelab/odoo-pim",
    "depends": [
        "product",
        "mail",
    ],
    "data": [
        "security/pim_channel_security.xml",
        "security/ir.model.access.csv",
        "views/pim_channel_views.xml",
        "views/pim_attribute_scope_views.xml",
        "views/product_template_views.xml",
    ],
    "installable": True,
    "application": True,
}
