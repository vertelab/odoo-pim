# Copyright 2026 Vertel AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, fields, models


class PimChangeConfirmWizard(models.TransientModel):
    _name = "pim.change.confirm.wizard"
    _description = "Confirm overwrite of a changed value"

    proposal_id = fields.Many2one(
        "pim.change.proposal",
        required=True,
        ondelete="cascade",
    )
    message = fields.Text(
        compute="_compute_message",
        readonly=True,
    )

    def _compute_message(self):
        for wizard in self:
            proposal = wizard.proposal_id
            wizard.message = _(
                "The product value changed after this proposal was created.\n\n"
                "Value when proposed: %(old)s\n"
                "Value now: %(now)s\n"
                "Proposed value: %(new)s\n\n"
                "Confirm to overwrite the current value.",
                old=proposal.old_value or _("(empty)"),
                now=proposal._get_current_value() or _("(empty)"),
                new=proposal.new_value or _("(empty)"),
            )

    def action_confirm(self):
        self.ensure_one()
        self.proposal_id.action_approve_confirmed()
        return {"type": "ir.actions.act_window_close"}
