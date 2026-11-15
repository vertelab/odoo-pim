# Copyright 2026 Vertel AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

# States that cannot be changed any more.
FINAL_STATES = ("approved", "rejected")


def normalize_value(value):
    """Normalise a value before comparing it with a stored one.

    An HTML editor round-trip changes whitespace and empty tags without
    changing what the reader sees. Comparing raw strings would report a
    conflict for every untouched field, so the comparison is done on the
    normalised form. The trade-off: a change that only touches whitespace is
    not reported as a conflict. That is deliberate — it is not a change a
    reviewer would act on.
    """
    if not value:
        return ""
    text = str(value)
    # Drop empty tags such as <p></p> or <br/> left behind by the editor.
    text = re.sub(r"<(\w+)[^>]*>\s*</\1>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<br\s*/?>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&nbsp;", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


class PimChangeProposal(models.Model):
    _name = "pim.change.proposal"
    _description = "PIM Change Proposal"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc, id desc"

    name = fields.Char(
        compute="_compute_name",
        store=True,
    )
    product_tmpl_id = fields.Many2one(
        "product.template",
        string="Product",
        required=True,
        ondelete="cascade",
        index=True,
    )
    attribute_id = fields.Many2one(
        "product.attribute",
        required=True,
        ondelete="cascade",
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
    old_value = fields.Text(
        help="The value that applied when the proposal was created.",
    )
    new_value = fields.Text(
        tracking=True,
    )
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("sent", "Sent"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
        ],
        default="draft",
        required=True,
        tracking=True,
        index=True,
    )
    proposed_by_id = fields.Many2one(
        "res.users",
        string="Proposed By",
        default=lambda self: self.env.user,
        required=True,
        readonly=True,
    )
    reviewed_by_id = fields.Many2one(
        "res.users",
        string="Reviewed By",
        readonly=True,
    )
    reviewed_on = fields.Datetime(
        string="Reviewed On",
        readonly=True,
    )
    comment = fields.Text(
        help="Required when rejecting: a rejection without a reason is not "
        "actionable for the author.",
    )
    conflict = fields.Boolean(
        readonly=True,
        help="The product value changed after this proposal was created.",
    )
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        related="product_tmpl_id.company_id",
        store=True,
        index=True,
    )

    @api.depends("product_tmpl_id", "attribute_id", "channel_id", "lang_id")
    def _compute_name(self):
        for proposal in self:
            parts = [
                proposal.product_tmpl_id.display_name or "",
                proposal.attribute_id.display_name or "",
                proposal.channel_id.display_name or "",
                proposal.lang_id.name or "",
            ]
            proposal.name = " / ".join(p for p in parts if p)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _ensure_editable(self):
        for proposal in self:
            if proposal.state in FINAL_STATES:
                raise UserError(
                    _(
                        "Proposal %(name)s is %(state)s and can no longer be "
                        "changed.",
                        name=proposal.name,
                        state=proposal.state,
                    )
                )

    def write(self, vals):
        # Only the transition fields may change on a final proposal; nothing
        # else may. The transition itself is allowed so that a reviewer can
        # move a sent proposal to approved or rejected.
        if any(
            key
            not in ("state", "reviewed_by_id", "reviewed_on", "conflict", "active")
            for key in vals
        ):
            self._ensure_editable()
        return super().write(vals)

    def action_send(self):
        self._ensure_editable()
        for proposal in self:
            if proposal.state != "draft":
                raise UserError(_("Only a draft can be sent."))
            proposal.state = "sent"
        return True

    def action_reset_draft(self):
        for proposal in self:
            if proposal.state != "sent":
                raise UserError(_("Only a sent proposal can be withdrawn."))
            if proposal.proposed_by_id != self.env.user:
                raise UserError(
                    _("Only the author can withdraw a proposal.")
                )
            proposal.state = "draft"
        return True

    def action_reject(self):
        for proposal in self:
            if not proposal.comment:
                raise ValidationError(
                    _("A rejection requires a reason in the comment field.")
                )
            if proposal.state in FINAL_STATES:
                raise UserError(_("This proposal is already settled."))
            proposal.write(
                {
                    "state": "rejected",
                    "reviewed_by_id": self.env.user.id,
                    "reviewed_on": fields.Datetime.now(),
                }
            )
        return True

    def action_approve(self):
        """Approve and write the value in one transaction.

        If the product value changed since the proposal was created the
        approval is refused until the reviewer confirms the overwrite.
        """
        for proposal in self:
            if proposal.state in FINAL_STATES:
                raise UserError(_("This proposal is already settled."))
            if proposal.state != "sent":
                raise UserError(_("Only a sent proposal can be approved."))
            policy = self.env["pim.change.policy"]._get_policy_for_product(
                proposal.product_tmpl_id, proposal.attribute_id, proposal.channel_id
            )
            if proposal.proposed_by_id == self.env.user:
                if not policy or not policy.allow_self_review:
                    raise UserError(
                        _(
                            "You cannot approve your own proposal, unless the "
                            "policy allows self review."
                        )
                    )
            is_self_review = proposal.proposed_by_id == self.env.user
            if policy and policy.review_group_id and not is_self_review:
                if self.env.user not in policy.review_group_id.users:
                    raise UserError(
                        _(
                            "You are not in the review group %(group)s.",
                            group=policy.review_group_id.display_name,
                        )
                    )
            current = proposal._get_current_value()
            if normalize_value(current) != normalize_value(proposal.old_value):
                proposal.conflict = True
                if not self.env.context.get("pim_confirm_overwrite"):
                    return proposal._open_conflict_wizard()
            proposal._apply()
            proposal.write(
                {
                    "state": "approved",
                    "reviewed_by_id": self.env.user.id,
                    "reviewed_on": fields.Datetime.now(),
                    "conflict": False,
                }
            )
        return True

    def _open_conflict_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Value changed since the proposal was created"),
            "res_model": "pim.change.confirm.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_proposal_id": self.id},
        }

    def action_approve_confirmed(self):
        """Approve despite a conflict, after the reviewer confirmed."""
        return self.with_context(pim_confirm_overwrite=True).action_approve()

    # ------------------------------------------------------------------
    # Writing the value
    # ------------------------------------------------------------------

    def _get_current_value(self):
        """Resolve the value the product has right now, in this channel.

        Runs as sudo: a reviewer may approve a change without holding the
        PIM Channel User group, and resolving the current value is a read the
        review itself requires. The write path is not affected.
        """
        self.ensure_one()
        value, _inherited = (
            self.product_tmpl_id.sudo()._pim_resolve_value(
                self.attribute_id, self.channel_id, self.lang_id
            )
        )
        return value

    def _apply(self):
        """Write the proposed value through pim_channel's single write path.

        Runs as sudo for the same reason as ``_get_current_value``: the
        reviewer's right to approve comes from the policy's review group, not
        from the channel enrichment group. The write still goes through
        pim_channel's method, so scoping and language handling are unchanged.
        """
        self.ensure_one()
        self.product_tmpl_id.sudo()._pim_write_channel_value(
            self.attribute_id,
            self.channel_id,
            self.lang_id,
            self.new_value,
        )
        return True

    # ------------------------------------------------------------------
    # Deletion
    # ------------------------------------------------------------------

    def unlink(self):
        settled = self.filtered(lambda p: p.state in FINAL_STATES)
        if settled:
            raise UserError(
                _(
                    "A settled proposal cannot be deleted: it is the record of "
                    "who changed what. Archive it instead."
                )
            )
        return super().unlink()

    # ------------------------------------------------------------------
    # Retention
    # ------------------------------------------------------------------

    @api.model
    def _cron_archive_settled(self):
        """Archive settled proposals older than the configured number of days."""
        days = int(
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("pim_change.archive_after_days", 365)
        )
        if days <= 0:
            return True
        limit = fields.Datetime.subtract(fields.Datetime.now(), days=days)
        settled = self.search(
            [
                ("state", "in", FINAL_STATES),
                ("write_date", "<", limit),
                ("active", "=", True),
            ]
        )
        settled.write({"active": False})
        return len(settled)
