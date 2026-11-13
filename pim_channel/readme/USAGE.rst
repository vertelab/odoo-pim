Usage
=====

1. Create a channel under *PIM > Configuration > Channels*. Give it a name, a
   unique code and a default language.
2. Scope the attributes that need a per-channel value under
   *PIM > Configuration > Attribute Scoping*. Scoping is per attribute **and**
   channel; an attribute can be scoped in one channel and not in another.
3. Open a product with a channel in the context to see the resolved values.
   Attributes shown in ``Inherited Attributes`` take their value from the base
   value instead of having their own.

Writing a channel value never touches the base value or other channels.
Clearing a channel value makes the channel fall back to the base value again.
