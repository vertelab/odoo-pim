# Copyright 2026 Vertel AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class PimAttributeScope(models.Model):
    _name = "pim.attribute.scope"
    _description = "PIM Attribute Scoping per Channel"
    _order = "channel_id, sequence, attribute_id"

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
    is_scoped = fields.Boolean(
        default=True,
        help="When set, the attribute may have a different value per channel. "
        "When unset, the base value applies to every channel.",
    )
    is_required = fields.Boolean(
        help="When set, the attribute must be filled in for this channel.",
    )
    label = fields.Char(
        translate=True,
        help="Optional channel specific label for the attribute.",
    )
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one(
        related="channel_id.company_id",
        store=True,
    )

    _sql_constraints = [
        (
            "attribute_channel_uniq",
            "unique(attribute_id, channel_id)",
            "An attribute can only be scoped once per channel.",
        ),
    ]

    @api.constrains("is_scoped", "is_required")
    def _check_required_implies_scoped(self):
        for scope in self:
            if scope.is_required and not scope.is_scoped:
                raise ValidationError(
                    _(
                        "Attribute %(attribute)s cannot be required in channel "
                        "%(channel)s without being scoped there.",
                        attribute=scope.attribute_id.display_name,
                        channel=scope.channel_id.display_name,
                    )
                )
