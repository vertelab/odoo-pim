PIM Completeness
================

Measures how complete a product's information is for a given channel and
language, and makes that number visible where the editor works.

Completeness is what drives enrichment: without it nobody knows when the
catalogue is ready for a channel.

Rules, not magic
----------------

A rule is defined per product category, channel and language. It lists the
attributes that count, with a weight each (weight 0 excludes the attribute
from both numerator and denominator) and a threshold. Rules are inherited down
the category tree, so a rule on *Shoes* also covers *Running shoes* unless a
more specific rule exists.

Missing rule is not 0 percent
-----------------------------

When no rule matches, the state is *No Rule* and no score row is stored. A
product without a rule is never counted as incomplete — that would produce
false alarms in every filter and dashboard.

Inherited values count, but are reported
----------------------------------------

An attribute that inherits its value from the base value counts as filled, but
is reported separately, so a channel that only inherits does not look finished.
