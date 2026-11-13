# Copyright 2026 Vertel AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCompletenessScore(TransactionCase):
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
        cls.attrs = cls.env["product.attribute"]
        for name in ("A", "B", "C", "D"):
            cls.attrs |= cls.env["product.attribute"].create(
                {
                    "name": name,
                    "create_variant": "no_variant",
                    "value_ids": [(0, 0, {"name": f"{name}1"})],
                }
            )
        cls.attr_a, cls.attr_b, cls.attr_c, cls.attr_d = cls.attrs
        for attr in cls.attrs:
            cls.env["pim.attribute.scope"].create(
                {
                    "attribute_id": attr.id,
                    "channel_id": cls.channel.id,
                    "is_scoped": True,
                }
            )
        cls.product = cls.env["product.template"].create(
            {
                "name": "Testprodukt",
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
                    for attr in cls.attrs
                ],
            }
        )
        cls.Completeness = cls.env["pim.completeness"]

    def _rule(self, attrs_weights, threshold=100):
        rule = self.env["pim.completeness.rule"].create(
            {
                "categ_id": self.categ.id,
                "channel_id": self.channel.id,
                "lang_id": self.lang.id,
                "threshold": threshold,
            }
        )
        for attr, weight in attrs_weights:
            self.env["pim.completeness.rule.line"].create(
                {
                    "rule_id": rule.id,
                    "attribute_id": attr.id,
                    "weight": weight,
                }
            )
        return rule

    def _fill(self, attr, value=None):
        self.product._pim_write_channel_value(
            attr,
            self.channel,
            self.lang,
            value or attr.value_ids[:1].name,
        )

    def test_all_filled(self):
        self._rule([(a, 1) for a in self.attrs])
        for attr in self.attrs:
            self._fill(attr)
        values = self.Completeness._compute_completeness(
            self.product, self.channel, self.lang
        )
        self.assertEqual(values["percentage"], 100.0)
        self.assertEqual(values["filled_count"], 4)
        self.assertEqual(values["required_count"], 4)
        self.assertEqual(values["state"], "ok")

    def test_nothing_filled(self):
        self._rule([(a, 1) for a in self.attrs])
        values = self.Completeness._compute_completeness(
            self.product, self.channel, self.lang
        )
        self.assertEqual(values["percentage"], 0.0)
        self.assertEqual(values["filled_count"], 0)
        self.assertEqual(values["state"], "below_threshold")

    def test_three_of_four(self):
        self._rule([(a, 1) for a in self.attrs])
        for attr in (self.attr_a, self.attr_b, self.attr_c):
            self._fill(attr)
        values = self.Completeness._compute_completeness(
            self.product, self.channel, self.lang
        )
        self.assertEqual(values["percentage"], 75.0)
        self.assertEqual(values["filled_count"], 3)
        self.assertEqual(values["required_count"], 4)

    def test_equal_weights_half(self):
        self._rule([(a, 1) for a in self.attrs])
        self._fill(self.attr_a)
        self._fill(self.attr_b)
        values = self.Completeness._compute_completeness(
            self.product, self.channel, self.lang
        )
        self.assertEqual(values["percentage"], 50.0)

    def test_heavier_attribute_weighs_more(self):
        self._rule(
            [
                (self.attr_a, 1),
                (self.attr_b, 1),
                (self.attr_c, 1),
                (self.attr_d, 2),
            ]
        )
        self._fill(self.attr_d)
        values = self.Completeness._compute_completeness(
            self.product, self.channel, self.lang
        )
        self.assertEqual(values["percentage"], 40.0)

    def test_weight_zero_excluded(self):
        self._rule(
            [
                (self.attr_a, 1),
                (self.attr_b, 1),
                (self.attr_c, 1),
                (self.attr_d, 0),
            ]
        )
        self._fill(self.attr_a)
        values = self.Completeness._compute_completeness(
            self.product, self.channel, self.lang
        )
        # Denominator is 3, not 4.
        self.assertEqual(values["required_count"], 3)
        self.assertEqual(round(values["percentage"], 2), 33.33)

    def test_inherited_counts_as_filled_but_is_reported(self):
        self._rule([(a, 1) for a in self.attrs])
        # The base value comes from the single variant value on the template.
        values = self.Completeness._compute_completeness(
            self.product, self.channel, self.lang
        )
        self.assertEqual(values["percentage"], 100.0)
        self.assertEqual(values["filled_count"], 4)
        self.assertEqual(values["inherited_count"], 4)

    def test_threshold_below(self):
        self._rule([(a, 1) for a in self.attrs], threshold=80)
        for attr in (self.attr_a, self.attr_b, self.attr_c):
            self._fill(attr)
        values = self.Completeness._compute_completeness(
            self.product, self.channel, self.lang
        )
        self.assertEqual(values["percentage"], 75.0)
        self.assertEqual(values["state"], "below_threshold")

    def test_threshold_reached(self):
        self._rule(
            [
                (self.attr_a, 1),
                (self.attr_b, 1),
                (self.attr_c, 1),
                (self.attr_d, 2),
            ],
            threshold=80,
        )
        for attr in self.attrs:
            self._fill(attr)
        values = self.Completeness._compute_completeness(
            self.product, self.channel, self.lang
        )
        self.assertEqual(values["percentage"], 100.0)
        self.assertEqual(values["state"], "ok")

    def test_no_rule_state(self):
        values = self.Completeness._compute_completeness(
            self.product, self.channel, self.lang
        )
        self.assertEqual(values["state"], "no_rule")
        self.assertEqual(values["percentage"], 0.0)

    def test_agrees_with_resolve_value(self):
        """Completeness and the channel view must agree on what is filled."""
        self._rule([(a, 1) for a in self.attrs])
        self._fill(self.attr_a)
        values = self.Completeness._compute_completeness(
            self.product, self.channel, self.lang
        )
        resolved_filled = 0
        for attr in self.attrs:
            value, _inherited = self.product._pim_resolve_value(
                attr, self.channel, self.lang
            )
            if value:
                resolved_filled += 1
        self.assertEqual(values["filled_count"], resolved_filled)

    def test_missing_attributes_listed(self):
        self._rule([(a, 1) for a in self.attrs])
        self._fill(self.attr_a)
        missing = self.Completeness._get_missing_for(
            self.product, self.channel, self.lang
        )
        self.assertNotIn(self.attr_a, missing)
        self.assertIn(self.attr_b, missing)
