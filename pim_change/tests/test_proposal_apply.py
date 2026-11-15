# Copyright 2026 Vertel AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from ..models.pim_change_proposal import normalize_value


@tagged("post_install", "-at_install")
class TestProposalApply(TransactionCase):
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
        cls.attr_scoped = cls.env["product.attribute"].create(
            {
                "name": "Lång beskrivning",
                "display_type": "radio",
                "create_variant": "no_variant",
                "value_ids": [(0, 0, {"name": "A"}), (0, 0, {"name": "B"})],
            }
        )
        cls.attr_plain = cls.env["product.attribute"].create(
            {
                "name": "Artikelnummer",
                "display_type": "radio",
                "create_variant": "no_variant",
                "value_ids": [(0, 0, {"name": "X"}), (0, 0, {"name": "Y"})],
            }
        )
        cls.env["pim.attribute.scope"].create(
            {
                "attribute_id": cls.attr_scoped.id,
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
                            "attribute_id": attr.id,
                            "value_ids": [(6, 0, attr.value_ids.ids)],
                        },
                    )
                    for attr in (cls.attr_scoped, cls.attr_plain)
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
                "login": "reviewer_apply",
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
        cls.Proposal = cls.env["pim.change.proposal"]

    def _proposal(self, attr, new_value, old_value=""):
        proposal = self.Proposal.create(
            {
                "product_tmpl_id": self.product.id,
                "attribute_id": attr.id,
                "channel_id": self.channel.id,
                "lang_id": self.lang.id,
                "old_value": old_value,
                "new_value": new_value,
            }
        )
        proposal.action_send()
        return proposal

    def test_apply_scoped_attribute_writes_channel_value(self):
        proposal = self._proposal(self.attr_scoped, "A")
        proposal.with_user(self.reviewer).action_approve()
        row = self.env["pim.channel.value"].search(
            [
                ("product_tmpl_id", "=", self.product.id),
                ("attribute_id", "=", self.attr_scoped.id),
                ("channel_id", "=", self.channel.id),
            ]
        )
        self.assertTrue(row)
        self.assertEqual(row.value_m2o_id.name, "A")

    def test_apply_unscoped_attribute_writes_base_value(self):
        proposal = self._proposal(self.attr_plain, "X")
        proposal.with_user(self.reviewer).action_approve()
        self.assertFalse(
            self.env["pim.channel.value"].search(
                [
                    ("product_tmpl_id", "=", self.product.id),
                    ("attribute_id", "=", self.attr_plain.id),
                ]
            )
        )
        self.assertEqual(
            self.product._pim_get_base_value(self.attr_plain).name, "X"
        )

    def test_apply_does_not_touch_other_channels(self):
        proposal = self._proposal(self.attr_scoped, "A")
        proposal.with_user(self.reviewer).action_approve()
        other = self.env["pim.channel"].create(
            {"name": "Katalog", "code": "katalog", "lang_id": self.lang.id}
        )
        self.assertFalse(
            self.env["pim.channel.value"].search(
                [
                    ("product_tmpl_id", "=", self.product.id),
                    ("channel_id", "=", other.id),
                ]
            )
        )

    def test_apply_is_atomic(self):
        """A failing write leaves the proposal sent and the product untouched."""
        proposal = self._proposal(self.attr_scoped, "A")
        before = self.env["pim.channel.value"].search_count(
            [("product_tmpl_id", "=", self.product.id)]
        )
        # An invalid option makes pim_channel's write raise, which is a real
        # failure inside the write path rather than a monkey-patched one.
        proposal.new_value = "finns-inte"
        with self.assertRaises(Exception):
            proposal.with_user(self.reviewer).action_approve()
        self.assertEqual(proposal.state, "sent")
        self.assertEqual(
            self.env["pim.channel.value"].search_count(
                [("product_tmpl_id", "=", self.product.id)]
            ),
            before,
        )

    def test_conflict_detected(self):
        proposal = self._proposal(self.attr_scoped, "B", old_value="")
        # Someone else writes a value directly.
        self.product._pim_write_channel_value(
            self.attr_scoped, self.channel, self.lang, "A"
        )
        action = proposal.with_user(self.reviewer).action_approve()
        self.assertTrue(proposal.conflict)
        self.assertEqual(proposal.state, "sent")
        self.assertEqual(action.get("res_model"), "pim.change.confirm.wizard")

    def test_conflict_confirmed_writes(self):
        proposal = self._proposal(self.attr_scoped, "B", old_value="")
        self.product._pim_write_channel_value(
            self.attr_scoped, self.channel, self.lang, "A"
        )
        proposal.with_user(self.reviewer).action_approve_confirmed()
        self.assertEqual(proposal.state, "approved")
        row = self.env["pim.channel.value"].search(
            [
                ("product_tmpl_id", "=", self.product.id),
                ("attribute_id", "=", self.attr_scoped.id),
            ]
        )
        self.assertEqual(row.value_m2o_id.name, "B")

    def test_no_conflict_writes_directly(self):
        proposal = self._proposal(self.attr_scoped, "A", old_value="")
        proposal.with_user(self.reviewer).action_approve()
        self.assertEqual(proposal.state, "approved")
        self.assertFalse(proposal.conflict)

    def test_html_normalization_avoids_false_conflict(self):
        self.assertEqual(
            normalize_value("<p>Hej</p>"), normalize_value("Hej")
        )
        self.assertEqual(
            normalize_value("<p>Hej</p><p></p>"), normalize_value("  Hej ")
        )
        self.assertEqual(
            normalize_value("Hej<br/>"), normalize_value("Hej")
        )

    def test_html_normalization_still_detects_real_change(self):
        self.assertNotEqual(
            normalize_value("<p>Hej</p>"), normalize_value("<p>Hejdå</p>")
        )

    def test_reviewed_by_and_on_are_recorded(self):
        proposal = self._proposal(self.attr_scoped, "A")
        proposal.with_user(self.reviewer).action_approve()
        self.assertEqual(proposal.reviewed_by_id, self.reviewer)
        self.assertTrue(proposal.reviewed_on)

    def test_completeness_updated_after_approval(self):
        if "pim.completeness" not in self.env.registry.models:
            self.skipTest("pim_completeness is not installed")
        rule = self.env["pim.completeness.rule"].create(
            {
                "categ_id": self.categ.id,
                "channel_id": self.channel.id,
                "lang_id": self.lang.id,
                "threshold": 100,
            }
        )
        self.env["pim.completeness.rule.line"].create(
            {"rule_id": rule.id, "attribute_id": self.attr_scoped.id}
        )
        proposal = self._proposal(self.attr_scoped, "A")
        before = self.env["pim.completeness"].search(
            [
                ("product_tmpl_id", "=", self.product.id),
                ("channel_id", "=", self.channel.id),
            ]
        )
        proposal.with_user(self.reviewer).action_approve()
        after = self.env["pim.completeness"].search(
            [
                ("product_tmpl_id", "=", self.product.id),
                ("channel_id", "=", self.channel.id),
            ]
        )
        self.assertGreater(after.percentage, before.percentage if before else 0.0)
