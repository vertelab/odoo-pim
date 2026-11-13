# Copyright 2026 Vertel AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestChannelScope(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.lang_sv = cls.env["res.lang"]._lang_get("sv_SE") or cls.env[
            "res.lang"
        ].search([], limit=1)
        cls.lang_en = cls.env["res.lang"]._lang_get("en_US") or cls.lang_sv
        cls.Channel = cls.env["pim.channel"]
        cls.Scope = cls.env["pim.attribute.scope"]
        cls.Value = cls.env["pim.channel.value"]

        cls.attribute = cls.env["product.attribute"].create(
            {
                "name": "Lång beskrivning",
                "display_type": "radio",
                "create_variant": "no_variant",
                "value_ids": [(0, 0, {"name": "Bas"}), (0, 0, {"name": "Alt"})],
            }
        )
        cls.channel_web = cls.Channel.create(
            {"name": "Webb", "code": "web", "lang_id": cls.lang_sv.id}
        )
        cls.channel_catalog = cls.Channel.create(
            {"name": "Katalog", "code": "katalog", "lang_id": cls.lang_sv.id}
        )
        cls.Scope.create(
            {
                "attribute_id": cls.attribute.id,
                "channel_id": cls.channel_web.id,
                "is_scoped": True,
            }
        )
        cls.base_option = cls.attribute.value_ids[:1]
        cls.product = cls.env["product.template"].create(
            {
                "name": "Testprodukt",
                "type": "consu",
                "attribute_line_ids": [
                    (
                        0,
                        0,
                        {
                            "attribute_id": cls.attribute.id,
                            "value_ids": [
                                (6, 0, cls.attribute.value_ids[:1].ids)
                            ],
                        },
                    )
                ],
            }
        )

    # -- scoping -----------------------------------------------------

    def test_unscoped_attribute_has_single_value(self):
        self.assertFalse(
            self.Scope.search(
                [
                    ("attribute_id", "=", self.attribute.id),
                    ("channel_id", "=", self.channel_catalog.id),
                    ("is_scoped", "=", True),
                ]
            )
        )
        value, inherited = self.product._pim_resolve_value(
            self.attribute, self.channel_catalog, self.lang_sv
        )
        self.assertTrue(inherited)
        self.assertEqual(value, self.base_option)

    def test_scoped_attribute_can_differ(self):
        self.product._pim_write_channel_value(
            self.attribute, self.channel_web, self.lang_sv, "Bas"
        )
        self.assertTrue(
            self.Value.search(
                [
                    ("product_tmpl_id", "=", self.product.id),
                    ("channel_id", "=", self.channel_web.id),
                ]
            )
        )

    # -- fallback ----------------------------------------------------

    def test_own_value(self):
        self.product._pim_write_channel_value(
            self.attribute, self.channel_web, self.lang_sv, "Bas"
        )
        value, inherited = self.product._pim_resolve_value(
            self.attribute, self.channel_web, self.lang_sv
        )
        self.assertEqual(value, self.base_option)
        self.assertFalse(inherited)

    def test_inherited_from_base(self):
        value, inherited = self.product._pim_resolve_value(
            self.attribute, self.channel_web, self.lang_sv
        )
        self.assertEqual(value, self.base_option)
        self.assertTrue(inherited)

    def test_nothing_filled(self):
        product = self.env["product.template"].create(
            {"name": "Tom produkt", "type": "consu"}
        )
        value, inherited = product._pim_resolve_value(
            self.attribute, self.channel_web, self.lang_sv
        )
        self.assertFalse(value)
        self.assertTrue(inherited)

    def test_language_fallback_to_channel_default(self):
        if self.lang_en == self.lang_sv:
            self.skipTest("Only one language is active")
        self.product._pim_write_channel_value(
            self.attribute, self.channel_web, self.lang_sv, "Bas"
        )
        # The channel default language is Swedish; asking in English must
        # fall back to the Swedish channel value, marked as inherited.
        value, inherited = self.product._pim_resolve_value(
            self.attribute, self.channel_web, self.lang_en
        )
        self.assertEqual(value, self.base_option)
        self.assertTrue(inherited)

    def test_value_in_requested_language_is_not_inherited(self):
        self.product._pim_write_channel_value(
            self.attribute, self.channel_web, self.lang_sv, "Bas"
        )
        value, inherited = self.product._pim_resolve_value(
            self.attribute, self.channel_web, self.lang_sv
        )
        self.assertEqual(value, self.base_option)
        self.assertFalse(inherited)

    # -- writing -----------------------------------------------------

    def test_write_in_channel_does_not_touch_base(self):
        base_before = self.product._pim_get_base_value(self.attribute)
        self.product._pim_write_channel_value(
            self.attribute, self.channel_web, self.lang_sv, "Bas"
        )
        self.assertEqual(
            self.product._pim_get_base_value(self.attribute), base_before
        )

    def test_clear_channel_value_falls_back(self):
        self.product._pim_write_channel_value(
            self.attribute, self.channel_web, self.lang_sv, "Bas"
        )
        self.product._pim_write_channel_value(
            self.attribute, self.channel_web, self.lang_sv, False
        )
        self.assertFalse(
            self.Value.search(
                [
                    ("product_tmpl_id", "=", self.product.id),
                    ("channel_id", "=", self.channel_web.id),
                ]
            )
        )
        value, inherited = self.product._pim_resolve_value(
            self.attribute, self.channel_web, self.lang_sv
        )
        self.assertEqual(value, self.base_option)
        self.assertTrue(inherited)

    def test_write_without_channel_is_refused(self):
        with self.assertRaises(UserError):
            self.product._pim_write_channel_value(
                self.attribute, self.Channel, self.lang_sv, "Bas"
            )

    def test_write_without_language_is_refused(self):
        with self.assertRaises(UserError):
            self.product._pim_write_channel_value(
                self.attribute, self.channel_web, self.env["res.lang"], "Bas"
            )

    # -- single value column -----------------------------------------

    def test_only_one_value_column_allowed(self):
        self.product._pim_write_channel_value(
            self.attribute, self.channel_web, self.lang_sv, "Bas"
        )
        row = self.Value.search(
            [
                ("product_tmpl_id", "=", self.product.id),
                ("channel_id", "=", self.channel_web.id),
            ]
        )
        self.assertEqual(row.value_m2o_id, self.attribute.value_ids[:1])
        with self.assertRaises(Exception):
            row.write({"value_char": "Fel", "value_text": "Också fel"})

    # -- computed surface --------------------------------------------

    def test_resolved_empty_without_channel(self):
        self.product._compute_pim_channel_resolved()
        self.assertFalse(self.product.pim_channel_resolved)
        self.assertFalse(self.product.pim_channel_inherited)

    def test_resolved_with_channel_in_context(self):
        product = self.product.with_context(pim_channel_id=self.channel_web.id)
        product._compute_pim_channel_resolved()
        self.assertIn(str(self.attribute.id), product.pim_channel_resolved)
        self.assertIn(self.attribute.id, product.pim_channel_inherited)

    # -- search ------------------------------------------------------

    def test_search_missing_own_value(self):
        other = self.env["product.template"].create(
            {"name": "Annan produkt", "type": "consu"}
        )
        self.product._pim_write_channel_value(
            self.attribute, self.channel_web, self.lang_sv, "Bas"
        )
        missing = self.env["product.template"].search(
            self.env["product.template"]._pim_search_missing_in_channel(
                self.channel_web, self.attribute, "=", True
            )
        )
        self.assertIn(other, missing)
        self.assertNotIn(self.product, missing)

    def test_search_has_own_value(self):
        self.product._pim_write_channel_value(
            self.attribute, self.channel_web, self.lang_sv, "Bas"
        )
        found = self.env["product.template"].search(
            self.env["product.template"]._pim_search_missing_in_channel(
                self.channel_web, self.attribute, "=", False
            )
        )
        self.assertIn(self.product, found)

    def test_search_requires_channel_and_attribute(self):
        with self.assertRaises(UserError):
            self.env["product.template"]._search_pim_channel_inherited(
                "=", True
            )
