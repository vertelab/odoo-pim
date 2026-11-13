# Copyright 2026 Vertel AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class PimCompletenessRule(models.Model):
    _name = "pim.completeness.rule"
    _description = "PIM Completeness Rule"
    _order = "categ_id, channel_id, lang_id"
    _parent_store = False

    name = fields.Char(compute="_compute_name", store=True)
    categ_id = fields.Many2one(
        "product.category",
        string="Category",
        required=True,
        ondelete="cascade",
        help="The rule applies to products in this category and, unless a "
        "more specific rule exists, in its sub-categories.",
    )
    channel_id = fields.Many2one(
        "pim.channel",
        required=True,
        ondelete="cascade",
    )
    lang_id = fields.Many2one(
        "res.lang",
        string="Language",
        required=True,
        ondelete="restrict",
    )
    threshold = fields.Integer(
        default=100,
        help="A product at or above this percentage is considered ready for "
        "the channel.",
    )
    active = fields.Boolean(default=True)
    line_ids = fields.One2many(
        "pim.completeness.rule.line",
        "rule_id",
        string="Attributes",
    )
    company_id = fields.Many2one(
        related="channel_id.company_id",
        store=True,
    )

    _sql_constraints = [
        (
            "categ_channel_lang_uniq",
            "unique(categ_id, channel_id, lang_id)",
            "A category can only have one completeness rule per channel and "
            "language.",
        ),
    ]

    @api.constrains("threshold")
    def _check_threshold(self):
        for rule in self:
            if rule.threshold < 0 or rule.threshold > 100:
                raise ValidationError(
                    _("The threshold must be between 0 and 100 percent.")
                )

    @api.depends("categ_id", "channel_id", "lang_id")
    def _compute_name(self):
        for rule in self:
            parts = [
                rule.categ_id.display_name or "",
                rule.channel_id.display_name or "",
                rule.lang_id.name or "",
            ]
            rule.name = " / ".join(p for p in parts if p)

    @api.model
    def _get_rule_for(self, categ, channel, lang):
        """Return the rule applying to a category, walking up the tree.

        The nearest rule wins: a rule on the category itself, then on its
        parent, and so on. Returns an empty recordset when no rule exists,
        which the caller must treat as ``no_rule`` and never as 0 percent.
        """
        if not categ or not channel or not lang:
            return self.browse()
        cache = self.env.context.get("pim_rule_cache")
        key = (categ.id, channel.id, lang.id)
        if cache is not None and key in cache:
            return cache[key]
        # parent_path is like "1/4/9/"; walk from the category upwards.
        ids = []
        if categ.parent_path:
            ids = [int(x) for x in categ.parent_path.strip("/").split("/") if x]
        else:
            ids = [categ.id]
        rules = self.search(
            [
                ("categ_id", "in", ids),
                ("channel_id", "=", channel.id),
                ("lang_id", "=", lang.id),
            ]
        )
        by_categ = {rule.categ_id.id: rule for rule in rules}
        found = self.browse()
        for categ_id in reversed(ids):
            if categ_id in by_categ:
                found = by_categ[categ_id]
                break
        if cache is not None:
            cache[key] = found
        return found

    @api.model
    def _get_rule_for_product(self, product, channel, lang):
        return self._get_rule_for(product.categ_id, channel, lang)


class PimCompletenessRuleLine(models.Model):
    _name = "pim.completeness.rule.line"
    _description = "PIM Completeness Rule Line"
    _order = "rule_id, sequence, id"

    rule_id = fields.Many2one(
        "pim.completeness.rule",
        required=True,
        ondelete="cascade",
    )
    attribute_id = fields.Many2one(
        "product.attribute",
        required=True,
        ondelete="cascade",
    )
    weight = fields.Float(
        default=1.0,
        help="How much this attribute contributes. Weight 0 excludes the "
        "attribute from both the numerator and the denominator.",
    )
    sequence = fields.Integer(default=10)

    _sql_constraints = [
        (
            "rule_attribute_uniq",
            "unique(rule_id, attribute_id)",
            "An attribute can only appear once in a completeness rule.",
        ),
    ]

    @api.constrains("weight")
    def _check_weight(self):
        for line in self:
            if line.weight < 0:
                raise ValidationError(_("The weight cannot be negative."))
