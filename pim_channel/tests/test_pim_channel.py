# Copyright 2026 Vertel AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.exceptions import ValidationError
from odoo.tests import Form, TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPimChannel(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.lang_sv = cls.env["res.lang"]._lang_get("sv_SE") or cls.env[
            "res.lang"
        ].search([], limit=1)
        cls.lang_en = cls.env["res.lang"]._lang_get("en_US") or cls.lang_sv
        cls.Channel = cls.env["pim.channel"]
        cls.attribute = cls.env["product.attribute"].create(
            {
                "name": "Lång beskrivning",
                "display_type": "radio",
                "create_variant": "no_variant",
                "value_ids": [(0, 0, {"name": "A"}), (0, 0, {"name": "B"})],
            }
        )
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
                            "value_ids": [(6, 0, cls.attribute.value_ids.ids)],
                        },
                    )
                ],
            }
        )

    def test_channel_create_and_read(self):
        channel = self.Channel.create(
            {
                "name": "Webb",
                "code": "web",
                "lang_id": self.lang_sv.id,
            }
        )
        self.assertEqual(channel.name, "Webb")
        self.assertEqual(channel.code, "web")
        self.assertEqual(channel.lang_id, self.lang_sv)
        self.assertTrue(channel.active)
        self.assertFalse(channel.website_id)

    def test_code_is_lowercased_and_stripped(self):
        channel = self.Channel.create(
            {"name": "Webb", "code": "  WEB  ", "lang_id": self.lang_sv.id}
        )
        self.assertEqual(channel.code, "web")

    def test_code_unique(self):
        self.Channel.create(
            {"name": "Webb", "code": "web", "lang_id": self.lang_sv.id}
        )
        with self.assertRaises(Exception):
            self.Channel.create(
                {"name": "Webben", "code": "web", "lang_id": self.lang_sv.id}
            )

    def test_display_name_contains_name_and_code(self):
        channel = self.Channel.create(
            {"name": "Webb", "code": "web", "lang_id": self.lang_sv.id}
        )
        self.assertIn("Webb", channel.display_name)
        self.assertIn("web", channel.display_name)

    def test_channel_without_website(self):
        channel = self.Channel.create(
            {"name": "Katalog", "code": "katalog", "lang_id": self.lang_sv.id}
        )
        self.assertFalse(channel.website_id)
        # A channel without a website can still be used for enrichment.
        self.env["pim.attribute.scope"].create(
            {
                "attribute_id": self.attribute.id,
                "channel_id": channel.id,
                "is_scoped": True,
            }
        )
        self.product._pim_write_channel_value(
            self.attribute, channel, self.lang_sv, "A"
        )
        self.assertTrue(
            self.env["pim.channel.value"].search(
                [("product_tmpl_id", "=", self.product.id)]
            )
        )

    def test_archived_channel_keeps_values(self):
        channel = self.Channel.create(
            {"name": "Webb", "code": "web", "lang_id": self.lang_sv.id}
        )
        self.env["pim.attribute.scope"].create(
            {
                "attribute_id": self.attribute.id,
                "channel_id": channel.id,
                "is_scoped": True,
            }
        )
        self.product._pim_write_channel_value(
            self.attribute, channel, self.lang_sv, "A"
        )
        channel.active = False
        values = self.env["pim.channel.value"].search(
            [("channel_id", "=", channel.id)]
        )
        self.assertTrue(values)
        channel.active = True
        self.assertTrue(channel.active)
        self.assertEqual(len(values), 1)

    def test_two_channels_same_website_allowed(self):
        if "website" not in self.env.registry.models:
            self.skipTest("The website module is not installed")
        website = self.env["website"].search([], limit=1)
        if not website:
            self.skipTest("No website in the database")
        channel_a = self.Channel.create(
            {
                "name": "Webb A",
                "code": "weba",
                "lang_id": self.lang_sv.id,
                "website_id": website.id,
            }
        )
        channel_b = self.Channel.create(
            {
                "name": "Webb B",
                "code": "webb",
                "lang_id": self.lang_sv.id,
                "website_id": website.id,
            }
        )
        self.assertEqual(channel_a.website_id, channel_b.website_id)

    def test_scoped_and_required_helpers(self):
        channel = self.Channel.create(
            {"name": "Webb", "code": "web", "lang_id": self.lang_sv.id}
        )
        self.assertFalse(channel._get_scoped_attributes())
        self.assertFalse(channel._get_required_attributes())
        self.env["pim.attribute.scope"].create(
            {
                "attribute_id": self.attribute.id,
                "channel_id": channel.id,
                "is_scoped": True,
                "is_required": True,
            }
        )
        self.assertEqual(channel._get_scoped_attributes(), self.attribute)
        self.assertEqual(channel._get_required_attributes(), self.attribute)

    def test_required_without_scoped_is_refused(self):
        channel = self.Channel.create(
            {"name": "Webb", "code": "web", "lang_id": self.lang_sv.id}
        )
        with self.assertRaises(ValidationError):
            self.env["pim.attribute.scope"].create(
                {
                    "attribute_id": self.attribute.id,
                    "channel_id": channel.id,
                    "is_scoped": False,
                    "is_required": True,
                }
            )

    def test_scope_unique_per_attribute_channel(self):
        channel = self.Channel.create(
            {"name": "Webb", "code": "web", "lang_id": self.lang_sv.id}
        )
        vals = {
            "attribute_id": self.attribute.id,
            "channel_id": channel.id,
            "is_scoped": True,
        }
        self.env["pim.attribute.scope"].create(vals)
        with self.assertRaises(Exception):
            self.env["pim.attribute.scope"].create(vals)
