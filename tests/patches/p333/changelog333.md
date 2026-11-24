## 1.0.333 — 24 November 2026

**Fixed (HA)**: a code checked against an SSH token, or an administrator's second step, wrote the whole row it had read back - right or wrong code. An SSH token replaced or removed on the other node at that moment (a phone lost) came back as it was, the old phone's codes good again; a passkey taken away, or a second step reset, the same. Wrong codes on both nodes at once were counted as one. The row is now changed only where it is as it was read, and only while it is the same token; a token replaced meanwhile refuses the old code, one removed is not made again.

**Fixed**: a sign-in ended at the fifth wrong code of the second step still gave a session to a right code sent at the same time - a burst of guesses was not held to five. The sign-in is now taken by one request alone before the new one is given.

