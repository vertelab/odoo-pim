PIM Change
==========

Lets an editor *propose* a value for a single field in a single channel and
language, and lets a reviewer approve or reject before the value is written.

Odoo's ``base_tier_validation`` validates the whole record on a state
transition. A product has no such transition, and record-level validation
cannot express "this editor may change the description but not the price, and
only in the web channel". This module works at field level instead.

Opt-in
------

Without a policy, editing behaves exactly as before. A policy names a
category, a channel, an attribute and a review group. Policies are inherited
down the category tree, so a policy on *Shoes* also covers *Running shoes*
unless a more specific policy exists.

Single write path
-----------------

An approved proposal is written through ``pim_channel``'s
``_pim_write_channel_value()`` — the same method a direct channel edit uses.
Scoping and language handling therefore cannot drift into two versions.

Conflicts are detected, not overwritten
---------------------------------------

If the product value changed after the proposal was created, approval is
refused until the reviewer confirms the overwrite. Comparison is done on a
normalised form, so an HTML editor round-trip does not produce a false
conflict.

Settled proposals cannot be deleted
-----------------------------------

An approved or rejected proposal is the record of who changed what. It can be
archived (and a nightly cron archives settled proposals older than the
configured number of days), but not deleted.
