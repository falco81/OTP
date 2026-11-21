## 1.0.314 — 20 November 2026

**Bug fix**: the help of *Replication behind by more than (MB)* said an e-mail goes out also when the replication runs into errors, but none ever did. Each node now notes whether its replication's apply and sync errors went up; when they did within the last half hour, an alert names the node and the subscriptions (HA with replication only, and only while the setting is not 0).

**Bug fix**: the disk alert fired also when the inodes (files) ran out, but it said only how full the space was (e.g. *40 % full*). It now says how many inodes are used too and points to `df -i`.

