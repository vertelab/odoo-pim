# Copyright 2026 Vertel AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class PimChannel(models.Model):
    _name = "pim.channel"
    _description = "PIM Channel"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(
        required=True,
        help="Technical identifier, stored in lower case. Used in exports.",
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    lang_id = fields.Many2one(
        "res.lang",
        string="Default Language",
        required=True,
        ondelete="restrict",
        help="Language used when a product has no value in the requested "
        "language for this channel.",
    )
    currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.company.currency_id,
    )
    website_id = fields.Many2one(
        "website",
        string="Website",
        ondelete="set null",
        help="Optional. A channel does not have to be a website; a printed "
        "catalog or a marketplace is also a channel.",
    )
    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
    )
    attribute_scope_ids = fields.One2many(
        "pim.attribute.scope",
        "channel_id",
        string="Attribute Scoping",
    )

    _sql_constraints = [
        (
            "code_uniq",
            "unique(code)",
            "The channel code must be unique.",
        ),
    ]

    @api.constrains("code")
    def _check_code(self):
        for channel in self:
            if not channel.code:
                continue
            if channel.code != channel.code.strip():
                raise ValidationError(
                    _("The channel code must not contain leading or trailing spaces.")
                )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("code"):
                vals["code"] = vals["code"].strip().lower()
        return super().create(vals_list)

    def write(self, vals):
        if vals.get("code"):
            vals["code"] = vals["code"].strip().lower()
        return super().write(vals)

    @api.depends("name", "code")
    def _compute_display_name(self):
        for channel in self:
            if channel.name and channel.code:
                channel.display_name = f"{channel.name} ({channel.code})"
            else:
                channel.display_name = channel.name or channel.code or ""

    def _get_scoped_attributes(self):
        """Return the attributes scoped in this channel."""
        self.ensure_one()
        return self.attribute_scope_ids.filtered("is_scoped").attribute_id

    def _get_required_attributes(self):
        """Return the attributes required in this channel."""
        self.ensure_one()
        return self.attribute_scope_ids.filtered("is_required").attribute_id
