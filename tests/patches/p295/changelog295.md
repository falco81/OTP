## 1.0.295 — 17 November 2026

**Bug fixes** (the hunt, second round). Without a database agent nothing changes.

- **Settings → The database on a node with no agent of its own**, in a cluster whose other node has one: the card of a server no agent looks after, with the other node's server as a tile beside it - it drew an agent of this node's ("Looked after by otp-db-agent at ?:?") with Move, Restart, Renew and Forget, which failed or did nothing.
- **High availability → The database servers** without replication (one node, or both nodes on one server): *– no replication* - it said a red *not set up* for each, with an arrow to "?".
- **A node forgotten or renamed**: its database server's rows go with it (Forget), and rows of a node that is no longer one of the cluster are left out - its tile, its pills on the cards, its "The database agent of … does not answer" alert, its `otp_db_agent_up` and its row of the meter stayed for good.
- **The meter's database rows are timed by this node's clock** when it read them: the database server's clock behind made its row late (dimmed, "?") for good, and an hour behind left it out.

