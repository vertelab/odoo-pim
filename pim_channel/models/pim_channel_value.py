# Copyright 2026 Vertel AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.translate import html_translate

# Mapping from the attribute kind to the column holding its value.
# Odoo's fields.Properties cannot store html/text, which is why this table
# exists at all: the long description is the most important PIM attribute.
VALUE_FIELDS = (
    "value_char",
    "value_text",
    "value_html",
    "value_int",
    "value_float",
    "value_bool",
    "value_date",
    "value_datetime",
    "value_selection",
    "value_m2o_id",
)


class PimChannelValue(models.Model):
    _name = "pim.channel.value"
    _description = "PIM Channel Value"
    _order = "product_tmpl_id, channel_id, attribute_id, lang_id"

    product_tmpl_id = fields.Many2one(
        "product.template",
        required=True,
        ondelete="cascade",
        index=True,
    )
    attribute_id = fields.Many2one(
        "product.attribute",
        required=True,
        ondelete="cascade",
    )
    channel_id = fields.Many2one(
        "pim.channel",
        required=True,
        ondelete="cascade",
    )
    lang_id = fields.Many2one(
        "res.lang",
        string="Language",
        required=True,
        ondelete="restrict",
    )
    company_id = fields.Many2one(
        related="product_tmpl_id.company_id",
        store=True,
        index=True,
    )

    value_char = fields.Char(string="Text")
    value_text = fields.Text(string="Long Text")
    value_html = fields.Html(string="HTML", translate=html_translate)
    value_int = fields.Integer(string="Integer")
    value_float = fields.Float(string="Decimal")
    value_bool = fields.Boolean(string="Yes/No")
    value_date = fields.Date(string="Date")
    value_datetime = fields.Datetime(string="Date & Time")
    value_selection = fields.Char(string="Selection")
    value_m2o_id = fields.Many2one(
        "product.attribute.value",
        string="Option",
        ondelete="restrict",
    )

    _sql_constraints = [
        (
            "product_attribute_channel_lang_uniq",
            "unique(product_tmpl_id, attribute_id, channel_id, lang_id)",
            "A product can only have one value per attribute, channel and language.",
        ),
    ]

    @api.constrains(*VALUE_FIELDS)
    def _check_single_value_column(self):
        for record in self:
            filled = [f for f in VALUE_FIELDS if record[f]]
            # A boolean False is a legitimate value; treat it as filled when
            # the attribute is boolean.
            if record.attribute_id and record.attribute_id.display_type == "multi":
                pass
            if len(filled) > 1:
                raise ValidationError(
                    _(
                        "A channel value can only hold one value column, "
                        "but %(fields)s are filled.",
                        fields=", ".join(filled),
                    )
                )

    @api.model
    def _pim_value_field_for(self, attribute):
        """Map a product.attribute to the column holding its value.

        ``product.attribute`` has no ``attribute_type`` field in core; the
        closest signal is ``display_type``. Attributes coming from OCA
        ``attribute_set`` carry ``attribute_type`` and are handled when that
        module is installed.

        Selection-like attributes hold a ``product.attribute.value`` record,
        so the value must be resolved to an option id before writing. The
        write path does that; this method only names the column.
        """
        if "attribute_type" in attribute._fields and attribute.attribute_type:
            return {
                "char": "value_char",
                "text": "value_text",
                "select": "value_m2o_id",
                "multiselect": "value_selection",
                "boolean": "value_bool",
                "integer": "value_int",
                "float": "value_float",
                "date": "value_date",
                "datetime": "value_datetime",
            }.get(attribute.attribute_type)
        return {
            "radio": "value_m2o_id",
            "pills": "value_m2o_id",
            "select": "value_m2o_id",
            "color": "value_m2o_id",
            "multi": "value_m2o_id",
        }.get(attribute.display_type, "value_char")

    @api.model
    def _pim_normalize_value(self, attribute, value):
        """Turn a user supplied value into what the value column expects.

        Selection-like attributes are stored as ``product.attribute.value``
        ids, so a name or a display name is resolved to the option record.
        """
        field_name = self._pim_value_field_for(attribute)
        if field_name != "value_m2o_id" or not value:
            return value
        if isinstance(value, int) or (isinstance(value, str) and value.isdigit()):
            option = attribute.value_ids.filtered(lambda v: v.id == int(value))[:1]
            if option:
                return option.id
        option = attribute.value_ids.filtered(
            lambda v, val=value: v.name == val or v.display_name == val
        )[:1]
        if not option:
            raise ValidationError(
                _(
                    "%(value)s is not a valid value for attribute %(attribute)s.",
                    value=value,
                    attribute=attribute.display_name,
                )
            )
        return option.id

    def _pim_get_value(self):
        """Return the value held by this row, whichever column is filled."""
        self.ensure_one()
        for field_name in VALUE_FIELDS:
            value = self[field_name]
            if value:
                return value
        return False
