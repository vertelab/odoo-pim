# Copyright 2026 Vertel AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCompletenessRule(TransactionCase):
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
        cls.categ_parent = cls.env["product.category"].create({"name": "Skor"})
        cls.categ_child = cls.env["product.category"].create(
            {"name": "Löparskor", "parent_id": cls.categ_parent.id}
        )
        cls.attr_a = cls.env["product.attribute"].create(
            {"name": "A", "create_variant": "no_variant"}
        )
        cls.attr_b = cls.env["product.attribute"].create(
            {"name": "B", "create_variant": "no_variant"}
        )
        cls.Rule = cls.env["pim.completeness.rule"]

    def _rule(self, categ, attrs=None, threshold=100):
        rule = self.Rule.create(
            {
                "categ_id": categ.id,
                "channel_id": self.channel.id,
                "lang_id": self.lang.id,
                "threshold": threshold,
            }
        )
        for attr in attrs or []:
            self.env["pim.completeness.rule.line"].create(
                {"rule_id": rule.id, "attribute_id": attr.id}
            )
        return rule

    def test_create_rule(self):
        rule = self._rule(self.categ_parent, [self.attr_a])
        self.assertEqual(rule.categ_id, self.categ_parent)
        self.assertEqual(rule.channel_id, self.channel)
        self.assertEqual(rule.lang_id, self.lang)
        self.assertEqual(rule.threshold, 100)
        self.assertEqual(len(rule.line_ids), 1)

    def test_rule_unique_per_categ_channel_lang(self):
        self._rule(self.categ_parent)
        with self.assertRaises(Exception):
            self._rule(self.categ_parent)

    def test_rule_line_unique_per_attribute(self):
        rule = self._rule(self.categ_parent, [self.attr_a])
        with self.assertRaises(Exception):
            self.env["pim.completeness.rule.line"].create(
                {"rule_id": rule.id, "attribute_id": self.attr_a.id}
            )

    def test_threshold_bounds(self):
        with self.assertRaises(ValidationError):
            self._rule(self.categ_parent, threshold=101)
        with self.assertRaises(ValidationError):
            self._rule(self.categ_parent, threshold=-1)

    def test_negative_weight_refused(self):
        rule = self._rule(self.categ_parent)
        with self.assertRaises(ValidationError):
            self.env["pim.completeness.rule.line"].create(
                {
                    "rule_id": rule.id,
                    "attribute_id": self.attr_a.id,
                    "weight": -1,
                }
            )

    def test_inherited_rule_from_parent_category(self):
        parent_rule = self._rule(self.categ_parent, [self.attr_a])
        found = self.Rule._get_rule_for(self.categ_child, self.channel, self.lang)
        self.assertEqual(found, parent_rule)

    def test_specific_rule_wins(self):
        self._rule(self.categ_parent, [self.attr_a])
        child_rule = self._rule(self.categ_child, [self.attr_b])
        found = self.Rule._get_rule_for(self.categ_child, self.channel, self.lang)
        self.assertEqual(found, child_rule)

    def test_no_rule_returns_empty(self):
        found = self.Rule._get_rule_for(self.categ_child, self.channel, self.lang)
        self.assertFalse(found)

    def test_rule_cache(self):
        self._rule(self.categ_parent, [self.attr_a])
        cache = {}
        env = self.env(context=dict(self.env.context, pim_rule_cache=cache))
        Rule = env["pim.completeness.rule"]
        # First lookup populates the cache; the next 99 must not query at all.
        Rule._get_rule_for(self.categ_child, self.channel, self.lang)
        self.assertTrue(cache)
        with self.assertQueryCount(0):
            for _i in range(99):
                Rule._get_rule_for(self.categ_child, self.channel, self.lang)
