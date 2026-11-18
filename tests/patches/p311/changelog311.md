## 1.0.311 — 18 November 2026

**Bug fixes** (the hunt, round 10): a node back after a failure, RADIUS spellings, the balancer's port.

- **A node marked failed by the other one that comes back on the new version is checked and back in service** (its database, RADIUS listening): it stayed in maintenance for good - RADIUS silent, the VIP address never there.
- **RADIUS: the token of another spelling whose directory cannot be asked now is "the directory is away"** - an answer the VPN takes to the other node - not "no token", a refusal counted as a guess.
- **High availability → the balancer's guides and the sign-in with a certificate or a smart card**: with that sign-in on (its own port 8443 by default), the guides offered 8443 for the balancer too - the `otp --set` line they gave was refused by the nodes, and the configurations they filled in (HAProxy, nginx, F5, NetScaler...) sent the balancer to the sign-in's own port, which would have published it. They now offer 9443 then, and say in red when the port typed is the sign-in's; docs/load-balancers.md says so too.

