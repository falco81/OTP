## 1.0.310 — 17 November 2026

**Bug fixes** (the hunt, round 9): the rolling upgrade in a cluster.

- **A node's own upgrade rows are written to the other node's database again** every 30 s while an upgrade runs: the node on the newer version reaches the older one only so - one write lost (its database restarting, the network a moment away) and the upgrade was held for good.
- **A node forgotten while it still beats in its own database keeps its maintenance and its upgrade row**: one on a newer version looked gone here - forgetting it took it out of a maintenance kept on purpose, and the upgrade waited for it for good.

