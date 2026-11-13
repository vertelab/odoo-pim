# Copyright 2026 Vertel AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models


class PimCompleteness(models.Model):
    _name = "pim.completeness"
    _description = "PIM Completeness Score"
    _order = "channel_id, product_tmpl_id, lang_id"

    product_tmpl_id = fields.Many2one(
        "product.template",
        required=True,
        ondelete="cascade",
        index=True,
    )
    channel_id = fields.Many2one(
        "pim.channel",
        required=True,
        ondelete="cascade",
        index=True,
    )
    lang_id = fields.Many2one(
        "res.lang",
        string="Language",
        required=True,
        ondelete="restrict",
    )
    percentage = fields.Float(
        help="Share of the weighted attributes in the rule that have a value.",
    )
    filled_count = fields.Integer()
    required_count = fields.Integer()
    inherited_count = fields.Integer(
        help="How many of the filled attributes inherit their value from the "
        "base value instead of having their own channel value.",
    )
    state = fields.Selection(
        selection=[
            ("ok", "Ready"),
            ("below_threshold", "Below Threshold"),
            ("no_rule", "No Rule"),
        ],
        default="no_rule",
        index=True,
    )
    rule_id = fields.Many2one(
        "pim.completeness.rule",
        ondelete="set null",
    )
    company_id = fields.Many2one(
        related="product_tmpl_id.company_id",
        store=True,
        index=True,
    )

    _sql_constraints = [
        (
            "product_channel_lang_uniq",
            "unique(product_tmpl_id, channel_id, lang_id)",
            "A product can only have one completeness score per channel and "
            "language.",
        ),
    ]

    # ------------------------------------------------------------------
    # Computation
    # ------------------------------------------------------------------

    @api.model
    def _compute_completeness(self, product, channel, lang):
        """Compute the completeness of a product for a channel and language.

        Returns a dict with percentage, filled_count, required_count,
        inherited_count, state and rule_id. The value resolution goes through
        ``product._pim_resolve_value()`` — the same path the channel view
        uses — so there is only one definition of "filled".
        """
        rule = self.env["pim.completeness.rule"]._get_rule_for_product(
            product, channel, lang
        )
        if not rule:
            return {
                "percentage": 0.0,
                "filled_count": 0,
                "required_count": 0,
                "inherited_count": 0,
                "state": "no_rule",
                "rule_id": False,
            }
        lines = rule.line_ids.filtered(lambda l: l.weight > 0)
        total_weight = sum(lines.mapped("weight"))
        filled_weight = 0.0
        filled = 0
        inherited = 0
        for line in lines:
            value, is_inherited = product._pim_resolve_value(
                line.attribute_id, channel, lang
            )
            if value:
                filled_weight += line.weight
                filled += 1
                if is_inherited:
                    inherited += 1
        percentage = (filled_weight / total_weight * 100.0) if total_weight else 0.0
        state = "ok" if percentage >= rule.threshold else "below_threshold"
        return {
            "percentage": percentage,
            "filled_count": filled,
            "required_count": len(lines),
            "inherited_count": inherited,
            "state": state,
            "rule_id": rule.id,
        }

    @api.model
    def _get_or_create(self, product, channel, lang):
        record = self.search(
            [
                ("product_tmpl_id", "=", product.id),
                ("channel_id", "=", channel.id),
                ("lang_id", "=", lang.id),
            ],
            limit=1,
        )
        return record

    @api.model
    def _update_for(self, product, channel, lang):
        """Recompute and store the score for one product/channel/language."""
        values = self._compute_completeness(product, channel, lang)
        record = self._get_or_create(product, channel, lang)
        if values["state"] == "no_rule":
            # No rule: do not keep a misleading 0 percent row.
            if record:
                record.unlink()
            return self.browse()
        if record:
            record.write(values)
            return record
        values.update(
            {
                "product_tmpl_id": product.id,
                "channel_id": channel.id,
                "lang_id": lang.id,
            }
        )
        return self.create(values)

    @api.model
    def _update_for_products(self, products):
        """Recompute every active channel and language for a recordset."""
        if not products:
            return
        channels = self.env["pim.channel"].search([])
        langs = self.env["res.lang"].search([("active", "=", True)])
        for product in products:
            for channel in channels:
                for lang in langs:
                    self._update_for(product, channel, lang)

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------

    @api.model
    def _get_missing_for(self, product, channel, lang):
        """Return the rule attributes that have no value for the product."""
        missing = self.env["product.attribute"]
        rule = self.env["pim.completeness.rule"]._get_rule_for_product(
            product, channel, lang
        )
        if not rule:
            return missing
        for line in rule.line_ids.filtered(lambda l: l.weight > 0):
            value, _inherited = product._pim_resolve_value(
                line.attribute_id, channel, lang
            )
            if not value:
                missing |= line.attribute_id
        return missing

    def _get_missing_attributes(self):
        """Return the rule attributes that have no value for this row."""
        self.ensure_one()
        return self._get_missing_for(
            self.product_tmpl_id, self.channel_id, self.lang_id
        )
