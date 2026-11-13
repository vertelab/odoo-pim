# Copyright 2026 Vertel AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .pim_channel_value import VALUE_FIELDS


class ProductTemplate(models.Model):
    _inherit = "product.template"

    pim_channel_id = fields.Many2one(
        "pim.channel",
        string="Channel",
        compute="_compute_pim_channel_id",
        store=False,
        help="Channel selected in the context. Not stored: it is a view "
        "selector, not product data.",
    )
    pim_channel_resolved = fields.Json(
        string="Channel Values",
        compute="_compute_pim_channel_resolved",
        help="Values resolved for the selected channel, with inherited "
        "values merged in.",
    )
    pim_channel_inherited = fields.Json(
        string="Inherited Attributes",
        compute="_compute_pim_channel_resolved",
        search="_search_pim_channel_inherited",
        help="Attributes whose value is inherited from the base value in the "
        "selected channel.",
    )

    # ------------------------------------------------------------------
    # Context helpers
    # ------------------------------------------------------------------

    def _pim_get_channel(self):
        """Return the channel selected in the context, if any."""
        channel_id = self.env.context.get("pim_channel_id")
        if not channel_id:
            return self.env["pim.channel"]
        return self.env["pim.channel"].browse(channel_id).exists()

    def _pim_get_lang(self):
        """Return the language to resolve values in."""
        lang_code = self.env.context.get("lang")
        lang = self.env["res.lang"]._lang_get(lang_code or self.env.lang)
        return lang

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------

    def _pim_resolve_value(self, attribute, channel, lang):
        """Resolve an attribute value for a channel and a language.

        Order: channel value in the requested language, channel value in the
        channel default language, base value. Returns ``(value, inherited)``.

        This is the only place the fallback rule lives. The UI, the list
        filter and completeness all call it.
        """
        self.ensure_one()
        Value = self.env["pim.channel.value"]
        domain = [
            ("product_tmpl_id", "=", self.id),
            ("attribute_id", "=", attribute.id),
            ("channel_id", "=", channel.id),
        ]
        if lang:
            row = Value.search(domain + [("lang_id", "=", lang.id)], limit=1)
            if row:
                return row._pim_get_value(), False
        if channel.lang_id and (not lang or channel.lang_id != lang):
            row = Value.search(
                domain + [("lang_id", "=", channel.lang_id.id)], limit=1
            )
            if row:
                return row._pim_get_value(), True
        return self._pim_get_base_value(attribute), True

    def _pim_get_base_value(self, attribute):
        """Return the non-channel (base) value of an attribute.

        Core ``product.attribute`` is a variant attribute; its base value is
        carried by the template attribute lines. A line with a single value
        is *not* a base value: Odoo writes single-value attributes on every
        variant automatically (``_create_variant_ids``), so "one option
        exists" says nothing about whether anyone filled it in. Only a line
        that has been narrowed to one value out of several carries a choice.

        An attribute whose key is not on the template at all has no base
        value either.
        """
        self.ensure_one()
        line = self.attribute_line_ids.filtered(
            lambda l, a=attribute: l.attribute_id == a
        )[:1]
        if not line:
            return False
        active = line.product_template_value_ids.filtered("ptav_active")
        if len(active) != 1:
            return False
        # The line must have been narrowed: the attribute offers more values
        # than the one left on the line.
        if len(attribute.value_ids) <= 1:
            return False
        return active.product_attribute_value_id

    @api.depends_context("pim_channel_id")
    def _compute_pim_channel_id(self):
        channel = self._pim_get_channel()
        for product in self:
            product.pim_channel_id = channel

    @api.depends(
        "attribute_line_ids",
        "attribute_line_ids.product_template_value_ids",
    )
    @api.depends_context("pim_channel_id", "lang")
    def _compute_pim_channel_resolved(self):
        channel = self._pim_get_channel()
        lang = self._pim_get_lang()
        for product in self:
            if not channel:
                product.pim_channel_resolved = {}
                product.pim_channel_inherited = []
                continue
            resolved = {}
            inherited = []
            for attribute in channel._get_scoped_attributes():
                value, is_inherited = product._pim_resolve_value(
                    attribute, channel, lang
                )
                resolved[str(attribute.id)] = (
                    value.id if hasattr(value, "id") else value
                )
                if is_inherited:
                    inherited.append(attribute.id)
            product.pim_channel_resolved = resolved
            product.pim_channel_inherited = inherited

    # ------------------------------------------------------------------
    # Writing
    # ------------------------------------------------------------------

    def _pim_write_channel_value(self, attribute, channel, lang, value):
        """Write a channel value. The only write path for channel values.

        ``pim_change`` calls this method instead of writing the table itself,
        so scoping and language handling cannot drift into two versions.
        """
        self.ensure_one()
        if not channel:
            raise UserError(_("A channel is required to write a channel value."))
        if not lang:
            raise UserError(_("A language is required to write a channel value."))
        scope = self.env["pim.attribute.scope"].search(
            [
                ("attribute_id", "=", attribute.id),
                ("channel_id", "=", channel.id),
                ("is_scoped", "=", True),
            ],
            limit=1,
        )
        Value = self.env["pim.channel.value"]
        domain = [
            ("product_tmpl_id", "=", self.id),
            ("attribute_id", "=", attribute.id),
            ("channel_id", "=", channel.id),
            ("lang_id", "=", lang.id),
        ]
        if not scope:
            # Not scoped in this channel: the base value is what applies.
            return self._pim_write_base_value(attribute, value)
        row = Value.search(domain, limit=1)
        if not value:
            if row:
                row.unlink()
            return True
        field_name = Value._pim_value_field_for(attribute)
        value = Value._pim_normalize_value(attribute, value)
        vals = {field_name: value}
        for other in VALUE_FIELDS:
            if other != field_name:
                vals[other] = False
        if row:
            row.write(vals)
        else:
            vals.update(
                {
                    "product_tmpl_id": self.id,
                    "attribute_id": attribute.id,
                    "channel_id": channel.id,
                    "lang_id": lang.id,
                }
            )
            Value.create(vals)
        return True

    def _pim_write_base_value(self, attribute, value):
        """Write the base (non-channel) value of an attribute."""
        self.ensure_one()
        line = self.attribute_line_ids.filtered(
            lambda l, a=attribute: l.attribute_id == a
        )[:1]
        if not line:
            raise UserError(
                _(
                    "Attribute %(attribute)s is not a variant attribute of "
                    "%(product)s and has no base value to write.",
                    attribute=attribute.display_name,
                    product=self.display_name,
                )
            )
        attribute_value = attribute.value_ids.filtered(
            lambda v, val=value: v.name == val
            or v.display_name == val
            or str(v.id) == str(val)
        )[:1]
        if not attribute_value:
            raise UserError(
                _(
                    "%(value)s is not a valid value for attribute %(attribute)s.",
                    value=value,
                    attribute=attribute.display_name,
                )
            )
        line.write({"value_ids": [(6, 0, [attribute_value.id])]})
        return True

    def action_pim_reset_channel_value(self):
        """Drop the channel value so the channel inherits the base value."""
        self.ensure_one()
        channel = self._pim_get_channel()
        lang = self._pim_get_lang()
        if not channel:
            raise UserError(_("Select a channel first."))
        attribute_id = self.env.context.get("pim_attribute_id")
        attribute = self.env["product.attribute"].browse(attribute_id).exists()
        if not attribute:
            raise UserError(_("Select an attribute first."))
        return self._pim_write_channel_value(attribute, channel, lang, False)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    @api.model
    def _pim_search_missing_in_channel(self, channel, attribute, operator, value):
        """Search products missing (or not missing) an own value in a channel.

        ``value`` True means "missing own value". Inherited values do not
        count as own values, which is why this cannot be a plain domain on a
        stored field.
        """
        self.env["pim.channel.value"].flush_model()
        self.env.cr.execute(
            """
            SELECT product_tmpl_id
              FROM pim_channel_value
             WHERE channel_id = %s
               AND attribute_id = %s
            """,
            (channel.id, attribute.id),
        )
        with_own_value = [row[0] for row in self.env.cr.fetchall()]
        if value:
            return [("id", "not in", with_own_value)]
        return [("id", "in", with_own_value)]

    @api.model
    def _search_pim_channel_inherited(self, operator, value):
        """Search hook for ``pim_channel_inherited``.

        The field is computed and not stored, so filtering on "missing own
        value in channel" has to be translated into a subquery. The channel
        and the attribute come from the context.
        """
        channel = self._pim_get_channel()
        attribute_id = self.env.context.get("pim_attribute_id")
        if not channel or not attribute_id:
            raise UserError(
                _(
                    "Filtering on inherited values requires a channel and an "
                    "attribute in the context."
                )
            )
        attribute = self.env["product.attribute"].browse(attribute_id).exists()
        if not attribute:
            raise UserError(_("Unknown attribute."))
        missing = bool(value)
        if operator in ("!=", "<>"):
            missing = not missing
        return self._pim_search_missing_in_channel(
            channel, attribute, operator, missing
        )
