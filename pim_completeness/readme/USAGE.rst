Usage
=====

1. Define a rule under *PIM > Configuration > Completeness Rules*: pick a
   category, a channel, a language, the attributes with their weights, and the
   threshold.
2. Open a product with a channel in the context. The *Completeness* tab shows
   the percentage, how many attributes are filled out of how many count, how
   many of them are inherited, and which attributes are missing.
3. Filter the product list on *Incomplete in channel* to find what is not
   ready, or on *No rule for channel* to find categories that still need a
   rule.

After changing a rule, run *Recompute* (the button or the nightly cron). Scores
are recomputed automatically when a channel value changes, but a rule change
does not retrigger them by itself.
