## 1.0.297 — 17 November 2026

**Bug fixes** (the hunt, fourth round): the self-service portal.

- **Replacing a token, "Another address or way" after an address was given**: back to choosing the way - it asked for the password and a code of the old token again, and used up another sent code.
- **The code boxes** are wide enough for "12345 67890" (they cut it on a 220 px box) and no wider than a phone; a screen reader names them *The code* (it read "000000").
- **After the last try of a code**, the page is drawn again only while that card is still there - "Send it again" pressed meanwhile lost the code being typed into the new one.
- **A label of a box with a button beside it** (the code and its *Send*) names the box: a click on it lands in it.

