# Copyright 2026 Vertel AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    pim_pending_proposal_count = fields.Integer(
        string="Pending Proposals",
        compute="_compute_pim_pending_proposal_count",
    )
    pim_pending_proposal_channel_count = fields.Integer(
        string="Pending Proposals in Channel",
        compute="_compute_pim_pending_proposal_count",
    )
    pim_review_attribute_ids = fields.Many2many(
        "product.attribute",
        string="Attributes Requiring Review",
        compute="_compute_pim_review_attribute_ids",
        help="Attributes that require review in the selected channel.",
    )

    def _pim_field_requires_review(self, attribute, channel):
        """Return the policy that requires review, or empty when none does."""
        self.ensure_one()
        if not channel:
            return self.env["pim.change.policy"].browse()
        return self.env["pim.change.policy"]._get_policy_for_product(
            self, attribute, channel
        )

    @api.depends("categ_id")
    @api.depends_context("pim_channel_id")
    def _compute_pim_pending_proposal_count(self):
        Proposal = self.env["pim.change.proposal"]
        channel = self._pim_get_channel()
        for product in self:
            pending = Proposal.search(
                [
                    ("product_tmpl_id", "=", product.id),
                    ("state", "=", "sent"),
                ]
            )
            product.pim_pending_proposal_count = len(pending)
            if channel:
                product.pim_pending_proposal_channel_count = len(
                    pending.filtered(lambda p: p.channel_id == channel)
                )
            else:
                product.pim_pending_proposal_channel_count = 0

    @api.depends("categ_id")
    @api.depends_context("pim_channel_id")
    def _compute_pim_review_attribute_ids(self):
        Policy = self.env["pim.change.policy"]
        channel = self._pim_get_channel()
        for product in self:
            if not channel:
                product.pim_review_attribute_ids = [(5, 0, 0)]
                continue
            policies = Policy._get_policies_for_product(product, channel)
            product.pim_review_attribute_ids = [
                (6, 0, policies.attribute_id.ids)
            ]

    def action_pim_propose_change(self):
        """Open a proposal for the attribute given in the context."""
        self.ensure_one()
        channel = self._pim_get_channel()
        lang = self._pim_get_lang()
        attribute_id = self.env.context.get("pim_attribute_id")
        attribute = self.env["product.attribute"].browse(attribute_id).exists()
        if not channel or not attribute:
            return False
        current, _inherited = self._pim_resolve_value(attribute, channel, lang)
        proposal = self.env["pim.change.proposal"].create(
            {
                "product_tmpl_id": self.id,
                "attribute_id": attribute.id,
                "channel_id": channel.id,
                "lang_id": lang.id,
                "old_value": current or "",
                "new_value": self.env.context.get("pim_new_value") or "",
            }
        )
        return {
            "type": "ir.actions.act_window",
            "res_model": "pim.change.proposal",
            "res_id": proposal.id,
            "view_mode": "form",
            "target": "current",
        }
