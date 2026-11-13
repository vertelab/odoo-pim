PIM Channel
===========

Adds a channel axis to product information: the same attribute can hold a
different value per sales channel and per language, with an explicit and
visible fallback to the base value.

A channel is *not* a website. A printed catalog or a marketplace is also a
channel, which is why ``pim.channel`` only optionally points at a website.

Why a dedicated value table
---------------------------

Odoo's ``fields.Properties`` cannot store ``html`` or ``text`` values
(``ALLOWED_TYPES`` in ``odoo/fields.py``), and the long description is the most
important PIM attribute. Channel values therefore live in ``pim.channel.value``
with one typed column per value kind. Scoping is opt-in per attribute and
channel: a product without scoped attributes behaves exactly as before.
