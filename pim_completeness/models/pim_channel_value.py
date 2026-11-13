# Copyright 2026 Vertel AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models


class PimChannelValue(models.Model):
    _inherit = "pim.channel.value"

    def _pim_recompute_completeness(self):
        """Recompute completeness for the products touched by these rows."""
        if self.env.context.get("pim_no_completeness_recompute"):
            return
        products = self.mapped("product_tmpl_id")
        if products:
            self.env["pim.completeness"]._update_for_products(products)

    def create(self, vals_list):
        records = super().create(vals_list)
        records._pim_recompute_completeness()
        return records

    def write(self, vals):
        products = self.mapped("product_tmpl_id")
        result = super().write(vals)
        if products and not self.env.context.get("pim_no_completeness_recompute"):
            self.env["pim.completeness"]._update_for_products(products)
        return result

    def unlink(self):
        products = self.mapped("product_tmpl_id")
        result = super().unlink()
        if products and not self.env.context.get("pim_no_completeness_recompute"):
            self.env["pim.completeness"]._update_for_products(products)
        return result
