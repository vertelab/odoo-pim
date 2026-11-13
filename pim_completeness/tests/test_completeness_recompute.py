# Copyright 2026 Vertel AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCompletenessRecompute(TransactionCase):
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
        cls.categ_a = cls.env["product.category"].create({"name": "Skor"})
        cls.categ_b = cls.env["product.category"].create({"name": "Hattar"})
        cls.attr = cls.env["product.attribute"].create(
            {
                "name": "A",
                "create_variant": "no_variant",
                "value_ids": [(0, 0, {"name": "A1"})],
            }
        )
        cls.env["pim.attribute.scope"].create(
            {
                "attribute_id": cls.attr.id,
                "channel_id": cls.channel.id,
                "is_scoped": True,
            }
        )
        for categ in (cls.categ_a, cls.categ_b):
            rule = cls.env["pim.completeness.rule"].create(
                {
                    "categ_id": categ.id,
                    "channel_id": cls.channel.id,
                    "lang_id": cls.lang.id,
                    "threshold": 100,
                }
            )
            cls.env["pim.completeness.rule.line"].create(
                {"rule_id": rule.id, "attribute_id": cls.attr.id}
            )
        cls.Completeness = cls.env["pim.completeness"]
        cls.product_a = cls.env["product.template"].create(
            {
                "name": "Sko",
                "type": "consu",
                "categ_id": cls.categ_a.id,
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
        cls.product_b = cls.env["product.template"].create(
            {
                "name": "Hatt",
                "type": "consu",
                "categ_id": cls.categ_b.id,
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

    def _row(self, product):
        return self.Completeness.search(
            [
                ("product_tmpl_id", "=", product.id),
                ("channel_id", "=", self.channel.id),
                ("lang_id", "=", self.lang.id),
            ]
        )

    def test_write_creates_score(self):
        self.product_a._pim_write_channel_value(
            self.attr, self.channel, self.lang, self.attr.value_ids[:1].name
        )
        row = self._row(self.product_a)
        self.assertTrue(row)
        self.assertEqual(row.percentage, 100.0)
        self.assertEqual(row.state, "ok")

    def test_clear_lowers_score(self):
        self.product_a._pim_write_channel_value(
            self.attr, self.channel, self.lang, self.attr.value_ids[:1].name
        )
        self.assertEqual(self._row(self.product_a).percentage, 100.0)
        self.product_a._pim_write_channel_value(
            self.attr, self.channel, self.lang, False
        )
        # Base value still exists, so the attribute is inherited, not empty.
        row = self._row(self.product_a)
        self.assertEqual(row.percentage, 100.0)
        self.assertEqual(row.inherited_count, 1)

    def test_list_price_does_not_recompute(self):
        self.product_a._pim_write_channel_value(
            self.attr, self.channel, self.lang, self.attr.value_ids[:1].name
        )
        row = self._row(self.product_a)
        write_date = row.write_date
        self.product_a.write({"list_price": 123.0})
        self.assertEqual(self._row(self.product_a).write_date, write_date)

    def test_recompute_all_channels(self):
        self.product_a._recompute_completeness()
        self.assertTrue(self._row(self.product_a))

    def test_batch_only_touches_selection(self):
        self.Completeness._update_for_products(self.product_a | self.product_b)
        self.assertTrue(self._row(self.product_a))
        self.assertTrue(self._row(self.product_b))
        # Wipe the scores, then recompute only category A.
        self.Completeness.search([]).unlink()
        self.env["product.template"].with_context(
            pim_recompute_categ_id=self.categ_a.id
        ).browse().action_recompute_completeness()
        self.assertTrue(self._row(self.product_a))
        self.assertFalse(self._row(self.product_b))

    def test_import_context_skips_recompute(self):
        env = self.env(
            context=dict(self.env.context, pim_no_completeness_recompute=True)
        )
        product = self.product_a.with_env(env)
        product._pim_write_channel_value(
            self.attr, self.channel, self.lang, self.attr.value_ids[:1].name
        )
        self.assertFalse(self._row(self.product_a))

    def test_cron_runs(self):
        self.product_a._pim_write_channel_value(
            self.attr, self.channel, self.lang, self.attr.value_ids[:1].name
        )
        self.env["product.template"]._cron_recompute_below_threshold()
        self.assertTrue(self._row(self.product_a))

    def test_no_rule_creates_no_row(self):
        categ = self.env["product.category"].create({"name": "Utan regel"})
        product = self.env["product.template"].create(
            {"name": "Utan regel", "type": "consu", "categ_id": categ.id}
        )
        product._recompute_completeness()
        self.assertFalse(self._row(product))

    def test_computed_fields_empty_without_channel(self):
        self.product_a._compute_pim_completeness()
        self.assertEqual(self.product_a.pim_completeness_state, "no_channel")

    def test_computed_fields_with_channel(self):
        self.product_a._pim_write_channel_value(
            self.attr, self.channel, self.lang, self.attr.value_ids[:1].name
        )
        product = self.product_a.with_context(pim_channel_id=self.channel.id)
        product._compute_pim_completeness()
        self.assertEqual(product.pim_completeness_state, "ok")
        self.assertEqual(product.pim_completeness_percentage, 100.0)
        self.assertEqual(product.pim_completeness_required, 1)
