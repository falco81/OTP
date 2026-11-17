## 1.0.309 — 17 November 2026

**Bug fixes** (the hunt, round 8): time and the VIP address.

- **The clock guard times its own work by a clock that is not stepped**: stepped back 5 min, it wrote nothing and asked no directory for 5 min - and its last row, "aside" and dated ahead, kept the other node treating it as aside.
- **Whether the other node beats, read in its own database, is judged by that machine's clock**: this node's clock 2 min ahead took it for gone - the last node of an upgrade waited for good, and both nodes led.
- **keepalived's check takes no word dated ahead**: after the clock was stepped back, a daemon hung but alive kept the VIP address for as long as the step.
- **The sign-in pages' tidying never ends a RADIUS guard's block early**: kept in the same maps, a block of a day went after 6 h of quiet.

