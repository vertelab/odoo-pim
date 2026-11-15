# Copyright 2026 Vertel AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestChangePolicy(TransactionCase):
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
        cls.channel_other = cls.env["pim.channel"].create(
            {"name": "Katalog", "code": "katalog", "lang_id": cls.lang.id}
        )
        cls.categ_parent = cls.env["product.category"].create({"name": "Skor"})
        cls.categ_child = cls.env["product.category"].create(
            {"name": "Löparskor", "parent_id": cls.categ_parent.id}
        )
        cls.attr = cls.env["product.attribute"].create(
            {
                "name": "Lång beskrivning",
                "create_variant": "no_variant",
                "value_ids": [(0, 0, {"name": "A"}), (0, 0, {"name": "B"})],
            }
        )
        cls.group = cls.env["res.groups"].create({"name": "Granskare"})
        cls.Policy = cls.env["pim.change.policy"]

    def _policy(self, categ, channel=None, attribute=None, **kwargs):
        vals = {
            "categ_id": categ.id,
            "channel_id": (channel or self.channel).id,
            "attribute_id": (attribute or self.attr).id,
            "review_group_id": self.group.id,
        }
        vals.update(kwargs)
        return self.Policy.create(vals)

    def test_create_policy(self):
        policy = self._policy(self.categ_parent)
        self.assertEqual(policy.categ_id, self.categ_parent)
        self.assertEqual(policy.channel_id, self.channel)
        self.assertEqual(policy.attribute_id, self.attr)
        self.assertEqual(policy.review_group_id, self.group)
        self.assertFalse(policy.allow_self_review)
        self.assertTrue(policy.active)

    def test_policy_unique(self):
        self._policy(self.categ_parent)
        with self.assertRaises(Exception):
            self._policy(self.categ_parent)

    def test_policy_inherited_from_parent_category(self):
        parent_policy = self._policy(self.categ_parent)
        found = self.Policy._get_policy_for(
            self.categ_child, self.attr, self.channel
        )
        self.assertEqual(found, parent_policy)

    def test_specific_policy_wins(self):
        self._policy(self.categ_parent)
        child_policy = self._policy(self.categ_child)
        found = self.Policy._get_policy_for(
            self.categ_child, self.attr, self.channel
        )
        self.assertEqual(found, child_policy)

    def test_no_policy_is_opt_in(self):
        found = self.Policy._get_policy_for(
            self.categ_child, self.attr, self.channel
        )
        self.assertFalse(found)

    def test_policy_is_per_channel(self):
        self._policy(self.categ_parent)
        found = self.Policy._get_policy_for(
            self.categ_child, self.attr, self.channel_other
        )
        self.assertFalse(found)

    def test_policy_cache(self):
        self._policy(self.categ_parent)
        cache = {}
        env = self.env(context=dict(self.env.context, pim_policy_cache=cache))
        Policy = env["pim.change.policy"]
        Policy._get_policy_for(self.categ_child, self.attr, self.channel)
        self.assertTrue(cache)
        with self.assertQueryCount(0):
            for _i in range(99):
                Policy._get_policy_for(
                    self.categ_child, self.attr, self.channel
                )

    def test_policies_for_product_nearest_wins(self):
        attr_b = self.env["product.attribute"].create(
            {"name": "B", "create_variant": "no_variant"}
        )
        self._policy(self.categ_parent, attribute=self.attr)
        self._policy(self.categ_parent, attribute=attr_b)
        self._policy(self.categ_child, attribute=self.attr)
        product = self.env["product.template"].create(
            {"name": "Löpare", "type": "consu", "categ_id": self.categ_child.id}
        )
        policies = self.Policy._get_policies_for_product(product, self.channel)
        self.assertEqual(len(policies), 2)
        self.assertEqual(policies.attribute_id, self.attr | attr_b)
