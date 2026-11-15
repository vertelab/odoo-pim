# Copyright 2026 Vertel AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestChangeProposal(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.lang = cls.env["res.lang"]._lang_get("sv_SE") or cls.env[
            "res.lang"
        ].search([], limit=1)
        cls.channel = cls.env["pim.channel"].create(
            {"name": "Webb", "code": "web", "lang_id": cls.lang.id}
        )
        cls.categ = cls.env["product.category"].create({"name": "Skor"})
        cls.attr = cls.env["product.attribute"].create(
            {
                "name": "Lång beskrivning",
                "display_type": "radio",
                "create_variant": "no_variant",
                "value_ids": [(0, 0, {"name": "A"}), (0, 0, {"name": "B"})],
            }
        )
        cls.env["pim.attribute.scope"].create(
            {
                "attribute_id": cls.attr.id,
                "channel_id": cls.channel.id,
                "is_scoped": True,
            }
        )
        cls.product = cls.env["product.template"].create(
            {
                "name": "Sko",
                "type": "consu",
                "categ_id": cls.categ.id,
                "attribute_line_ids": [
                    (
                        0,
                        0,
                        {
                            "attribute_id": cls.attr.id,
                            "value_ids": [(6, 0, cls.attr.value_ids.ids)],
                        },
                    )
                ],
            }
        )
        cls.reviewer_group = cls.env["res.groups"].create({"name": "Granskare"})
        cls.change_reviewer_group = cls.env.ref(
            "pim_change.group_pim_change_reviewer"
        )
        cls.reviewer = cls.env["res.users"].create(
            {
                "name": "Granskare",
                "login": "reviewer_pim",
                "groups_id": [
                    (
                        6,
                        0,
                        [
                            cls.env.ref("base.group_user").id,
                            cls.reviewer_group.id,
                            cls.change_reviewer_group.id,
                        ],
                    )
                ],
            }
        )
        cls.proposal = cls.env["pim.change.proposal"].create(
            {
                "product_tmpl_id": cls.product.id,
                "attribute_id": cls.attr.id,
                "channel_id": cls.channel.id,
                "lang_id": cls.lang.id,
                "old_value": "",
                "new_value": "A",
            }
        )
        cls.Proposal = cls.env["pim.change.proposal"]

    def test_create_proposal_does_not_touch_product(self):
        self.assertEqual(self.proposal.state, "draft")
        self.assertFalse(
            self.env["pim.channel.value"].search(
                [("product_tmpl_id", "=", self.product.id)]
            )
        )

    def test_tracking_is_configured(self):
        # tracking=True on state and new_value is what makes the chatter
        # carry the history. Asserting the field flag is stable; asserting a
        # message depends on mail's tracking pipeline being active in the
        # test environment, which it is not under tracking_disable.
        self.assertTrue(self.Proposal._fields["state"].tracking)
        self.assertTrue(self.Proposal._fields["new_value"].tracking)

    def test_lifecycle_send_approve(self):
        self.proposal.action_send()
        self.assertEqual(self.proposal.state, "sent")
        self.proposal.with_user(self.reviewer).action_approve()
        self.assertEqual(self.proposal.state, "approved")
        self.assertEqual(self.proposal.reviewed_by_id, self.reviewer)

    def test_withdraw_returns_to_draft(self):
        self.proposal.action_send()
        self.proposal.action_reset_draft()
        self.assertEqual(self.proposal.state, "draft")

    def test_write_on_settled_refused(self):
        self.proposal.action_send()
        self.proposal.with_user(self.reviewer).action_approve()
        with self.assertRaises(UserError):
            self.proposal.write({"new_value": "B"})

    def test_unlink_on_settled_refused(self):
        self.proposal.action_send()
        self.proposal.with_user(self.reviewer).action_approve()
        with self.assertRaises(UserError):
            self.proposal.unlink()

    def test_unlink_on_draft_allowed(self):
        self.proposal.unlink()
        self.assertFalse(self.proposal.exists())

    def test_reject_requires_comment(self):
        self.proposal.action_send()
        with self.assertRaises(ValidationError):
            self.proposal.with_user(self.reviewer).action_reject()

    def test_reject_with_comment(self):
        self.proposal.action_send()
        self.proposal.comment = "fel ton"
        self.proposal.with_user(self.reviewer).action_reject()
        self.assertEqual(self.proposal.state, "rejected")
        self.assertEqual(self.proposal.comment, "fel ton")
        self.assertFalse(
            self.env["pim.channel.value"].search(
                [("product_tmpl_id", "=", self.product.id)]
            )
        )

    def test_self_review_refused_without_policy(self):
        self.proposal.action_send()
        with self.assertRaises(UserError):
            self.proposal.action_approve()

    def test_self_review_allowed_by_policy(self):
        self.env["pim.change.policy"].create(
            {
                "categ_id": self.categ.id,
                "channel_id": self.channel.id,
                "attribute_id": self.attr.id,
                "review_group_id": self.env.ref("base.group_user").id,
                "allow_self_review": True,
            }
        )
        self.env.user.groups_id = [(4, self.env.ref("base.group_user").id)]
        self.proposal.action_send()
        self.proposal.action_approve()
        self.assertEqual(self.proposal.state, "approved")

    def test_two_proposals_on_same_field_both_survive(self):
        second = self.Proposal.create(
            {
                "product_tmpl_id": self.product.id,
                "attribute_id": self.attr.id,
                "channel_id": self.channel.id,
                "lang_id": self.lang.id,
                "old_value": "",
                "new_value": "B",
            }
        )
        self.assertTrue(self.proposal.exists())
        self.assertTrue(second.exists())
        self.assertNotEqual(self.proposal.new_value, second.new_value)

    def test_archive_keeps_trace(self):
        self.proposal.action_send()
        self.proposal.with_user(self.reviewer).action_approve()
        self.proposal.active = False
        archived = self.Proposal.with_context(active_test=False).browse(
            self.proposal.id
        )
        self.assertEqual(archived.new_value, "A")
        self.assertEqual(archived.reviewed_by_id, self.reviewer)

    def test_cron_archives_settled(self):
        self.proposal.action_send()
        self.proposal.with_user(self.reviewer).action_approve()
        self.proposal.flush_recordset()
        self.env["ir.config_parameter"].sudo().set_param(
            "pim_change.archive_after_days", 1
        )
        # Backdate the write so it falls outside the window. The ORM keeps a
        # cached write_date, so read it back through a fresh cursor.
        self.env.cr.execute(
            "UPDATE pim_change_proposal SET write_date = write_date - interval '10 days' WHERE id = %s",
            (self.proposal.id,),
        )
        self.env.invalidate_all()
        archived_count = self.Proposal._cron_archive_settled()
        self.assertGreaterEqual(archived_count, 1)
        archived = self.Proposal.with_context(active_test=False).browse(
            self.proposal.id
        )
        self.assertFalse(archived.active)
