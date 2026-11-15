Usage
=====

1. Create a review group under *Settings > Users & Companies > Groups*.
2. Define a policy under *PIM > Configuration > Change Policies*: category,
   channel, attribute and review group. Leave *Allow self review* off unless
   you really mean it.
3. As an editor: open a product with a channel in the context, propose a value
   and press *Send for review*. The product is unchanged until the proposal is
   approved.
4. As a reviewer: open *PIM > Changes > Review Queue*, compare the old and the
   new value, then *Approve* or *Reject*. A rejection requires a reason.

If the product value changed in the meantime, approval opens a confirmation
dialog showing the value at proposal time, the current value and the proposed
value. Nothing is written until you confirm.
