# Copyright 2026 Vertel AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models


class PimChangePolicy(models.Model):
    _name = "pim.change.policy"
    _description = "PIM Change Policy"
    _order = "categ_id, channel_id, attribute_id"

    name = fields.Char(compute="_compute_name", store=True)
    categ_id = fields.Many2one(
        "product.category",
        string="Category",
        required=True,
        ondelete="cascade",
        help="The policy applies to products in this category and, unless a "
        "more specific policy exists, in its sub-categories.",
    )
    channel_id = fields.Many2one(
        "pim.channel",
        required=True,
        ondelete="cascade",
    )
    attribute_id = fields.Many2one(
        "product.attribute",
        required=True,
        ondelete="cascade",
    )
    review_group_id = fields.Many2one(
        "res.groups",
        string="Review Group",
        required=True,
        ondelete="restrict",
        help="Only users in this group may approve or reject proposals "
        "covered by the policy.",
    )
    allow_self_review = fields.Boolean(
        help="Let the person who proposed a change also approve it. Off by "
        "default: a review nobody else performs is not a review.",
    )
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        related="channel_id.company_id",
        store=True,
    )

    _sql_constraints = [
        (
            "categ_channel_attribute_uniq",
            "unique(categ_id, channel_id, attribute_id)",
            "A category can only have one change policy per attribute and "
            "channel.",
        ),
    ]

    @api.depends("categ_id", "channel_id", "attribute_id")
    def _compute_name(self):
        for policy in self:
            parts = [
                policy.categ_id.display_name or "",
                policy.channel_id.display_name or "",
                policy.attribute_id.display_name or "",
            ]
            policy.name = " / ".join(p for p in parts if p)

    @api.model
    def _get_policies_for_product(self, product, channel):
        """Return the nearest policy per attribute for a product and channel.

        A policy on a nearer category overrides one further up the tree, so
        the result holds at most one policy per attribute.
        """
        if not product.categ_id or not channel:
            return self.browse()
        policies = self.search(
            [
                ("channel_id", "=", channel.id),
                ("categ_id", "parent_of", product.categ_id.id),
            ]
        )
        by_attribute = {}
        for policy in policies:
            depth = len(policy.categ_id.parent_path or "")
            current = by_attribute.get(policy.attribute_id.id)
            if current is None or depth > current[0]:
                by_attribute[policy.attribute_id.id] = (depth, policy)
        return self.browse([p.id for _d, p in by_attribute.values()])

    @api.model
    def _get_policy_for(self, categ, attribute, channel):
        """Return the policy applying to a category, walking up the tree.

        The nearest policy wins. Returns an empty recordset when no policy
        exists, which means the change is written directly — the flow is
        opt-in.
        """
        if not categ or not attribute or not channel:
            return self.browse()
        cache = self.env.context.get("pim_policy_cache")
        key = (categ.id, attribute.id, channel.id)
        if cache is not None and key in cache:
            return cache[key]
        if categ.parent_path:
            ids = [
                int(x) for x in categ.parent_path.strip("/").split("/") if x
            ]
        else:
            ids = [categ.id]
        policies = self.search(
            [
                ("categ_id", "in", ids),
                ("attribute_id", "=", attribute.id),
                ("channel_id", "=", channel.id),
            ]
        )
        by_categ = {policy.categ_id.id: policy for policy in policies}
        found = self.browse()
        for categ_id in reversed(ids):
            if categ_id in by_categ:
                found = by_categ[categ_id]
                break
        if cache is not None:
            cache[key] = found
        return found

    @api.model
    def _get_policy_for_product(self, product, attribute, channel):
        return self._get_policy_for(product.categ_id, attribute, channel)
