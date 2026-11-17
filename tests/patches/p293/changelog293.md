## 1.0.293 — 16 November 2026

**The database servers in the header's meter** (isemon's external-database kit, the last part). Without an agent nothing changes. docs/external-database.md → *Monitoring*.

- With an otp-db-agent, the meter in the header (Settings → About → the performance meter) has a row for each database server after the nodes, in the look chosen (graphs, pills, line, rings), named with a small cylinder - the server's own short name (`db1`), or `db·NODE` where that is not one. This node's row is named beside it.
- Its numbers are what the agent reads of its machine (the processor, the memory, the disks, the network, the load), every 2 s while a page looks; the other node's server (layout B) from the row its node writes.
- Pointed at, its panel: the graph of what was pointed at, **The database** - the version, running for how long, the connections, *Waiting to go over (replication)*, the size of otp's database, its data's disk, TLS - and **The machine** in numbers.
- An agent that does not answer: the row dimmed and its name red, its panel says so. The meter does not wait for it: an agent known down is not asked, and one that did not answer is asked again 10 s later.
- docs/external-database.md: the intro brought up to date (1.0.292 and this).

