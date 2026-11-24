## 1.0.338 — 24 November 2026

**Fixed (texts)**: the SMS of a sign-in code could be saved without `{code}` - every SMS of a sign-in then went with no code in it. It is refused now, as an empty one is.

**Fixed (texts)**: the length of a prompt the VPN or the SSH gate shows was measured with a short sample address - one accepted could be longer than RADIUS carries with a real address, and was cut; on the SSH gate the ": " after it went, and half a letter could be left. Measured now with an address as long as a real one; the SSH prompt is cut on a letter, before its ": ".

**Fixed (texts' editor)**: the count of an SMS did not make dashes and Czech quotes plain as the sending does - a text sent as one plain SMS was shown as Unicode, in two parts.

