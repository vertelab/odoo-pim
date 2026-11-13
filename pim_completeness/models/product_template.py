# Copyright 2026 Vertel AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ProductTemplate(models.Model):
    _inherit = "product.template"

    pim_completeness_percentage = fields.Float(
        string="Completeness",
        compute="_compute_pim_completeness",
        search="_search_pim_completeness_state",
        store=False,
        help="Completeness for the channel and language in the context. "
        "Empty when no channel is selected: a completeness value without a "
        "channel is meaningless.",
    )
    pim_completeness_state = fields.Selection(
        selection=[
            ("ok", "Ready"),
            ("below_threshold", "Below Threshold"),
            ("no_rule", "No Rule"),
            ("no_channel", "No Channel"),
        ],
        compute="_compute_pim_completeness",
        search="_search_pim_completeness_state",
        store=False,
    )
    pim_completeness_filled = fields.Integer(
        compute="_compute_pim_completeness",
        store=False,
    )
    pim_completeness_required = fields.Integer(
        compute="_compute_pim_completeness",
        store=False,
    )
    pim_completeness_inherited = fields.Integer(
        compute="_compute_pim_completeness",
        store=False,
    )
    pim_completeness_missing = fields.Char(
        string="Missing Attributes",
        compute="_compute_pim_completeness",
        store=False,
    )

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    @api.model
    def _search_pim_completeness_state(self, operator, value):
        """Search hook for the computed completeness fields.

        Filtering on a computed, non-stored field has to become a subquery on
        ``pim.completeness``. The channel and language come from the context,
        exactly as they do for the computed value itself.
        """
        channel = self._pim_get_channel()
        if not channel:
            raise UserError(
                _("Filtering on completeness requires a channel in the context.")
            )
        lang = self._pim_get_lang()
        Completeness = self.env["pim.completeness"]
        if operator in ("!=", "<>"):
            value = "ok" if value == "below_threshold" else "below_threshold"
            operator = "="
        if operator != "=":
            raise UserError(
                _("Completeness can only be filtered with = or !=.")
            )
        if value == "no_rule":
            # Products whose category has no rule in this channel.
            ruled = Completeness.search(
                [
                    ("channel_id", "=", channel.id),
                    ("lang_id", "=", lang.id),
                ]
            ).mapped("product_tmpl_id")
            return [("id", "not in", ruled.ids)]
        rows = Completeness.search(
            [
                ("channel_id", "=", channel.id),
                ("lang_id", "=", lang.id),
                ("state", "=", value),
            ]
        )
        return [("id", "in", rows.mapped("product_tmpl_id").ids)]

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------

    def _pim_completeness_row(self, channel, lang):
        self.ensure_one()
        return self.env["pim.completeness"].search(
            [
                ("product_tmpl_id", "=", self.id),
                ("channel_id", "=", channel.id),
                ("lang_id", "=", lang.id),
            ],
            limit=1,
        )

    @api.depends("categ_id")
    @api.depends_context("pim_channel_id", "lang")
    def _compute_pim_completeness(self):
        Completeness = self.env["pim.completeness"]
        channel = self._pim_get_channel()
        lang = self._pim_get_lang()
        for product in self:
            if not channel:
                product.pim_completeness_percentage = 0.0
                product.pim_completeness_state = "no_channel"
                product.pim_completeness_filled = 0
                product.pim_completeness_required = 0
                product.pim_completeness_inherited = 0
                product.pim_completeness_missing = False
                continue
            row = product._pim_completeness_row(channel, lang)
            if row:
                values = {
                    "percentage": row.percentage,
                    "filled_count": row.filled_count,
                    "required_count": row.required_count,
                    "inherited_count": row.inherited_count,
                    "state": row.state,
                }
                missing = row._get_missing_attributes()
            else:
                # No stored row: either no rule, or the score was never
                # computed. Compute on the fly so the UI is never stale.
                values = Completeness._compute_completeness(
                    product, channel, lang
                )
                missing = (
                    Completeness._get_missing_for(product, channel, lang)
                    if values["state"] != "no_rule"
                    else self.env["product.attribute"]
                )
            product.pim_completeness_percentage = values["percentage"]
            product.pim_completeness_state = values["state"]
            product.pim_completeness_filled = values["filled_count"]
            product.pim_completeness_required = values["required_count"]
            product.pim_completeness_inherited = values["inherited_count"]
            product.pim_completeness_missing = (
                ", ".join(missing.mapped("name")) if missing else False
            )

    # ------------------------------------------------------------------
    # Recompute
    # ------------------------------------------------------------------

    def _recompute_completeness(self):
        """Recompute completeness for this recordset, all channels/languages."""
        self.env["pim.completeness"]._update_for_products(self)
        return True

    def action_recompute_completeness(self):
        """Batch recompute. Selection comes from the context."""
        categ_id = self.env.context.get("pim_recompute_categ_id")
        channel_id = self.env.context.get("pim_recompute_channel_id")
        products = self
        if not products:
            domain = []
            if categ_id:
                domain.append(("categ_id", "child_of", categ_id))
            products = self.search(domain)
        if channel_id:
            channel = self.env["pim.channel"].browse(channel_id).exists()
            if not channel:
                raise UserError(_("Unknown channel."))
            langs = self.env["res.lang"].search([("active", "=", True)])
            for product in products:
                for lang in langs:
                    self.env["pim.completeness"]._update_for(
                        product, channel, lang
                    )
        else:
            products._recompute_completeness()
        return True

    @api.model
    def _cron_recompute_below_threshold(self):
        """Safety net: recompute scores that are below their threshold."""
        rows = self.env["pim.completeness"].search(
            [("state", "=", "below_threshold")]
        )
        for row in rows:
            self.env["pim.completeness"]._update_for(
                row.product_tmpl_id, row.channel_id, row.lang_id
            )
        return True
