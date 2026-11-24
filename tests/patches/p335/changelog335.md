## 1.0.335 — 24 November 2026

**Fixed (network)**: a change of a node's network that failed half way on the root side - `/etc/hosts` made unchangeable (`chattr +i`), the reboot not asked - left NetworkManager's profile with the new address and the new host name, with no trial and no reboot: the next restart (an update of the system) brought the node up at an address the cluster did not know. What was changed is now put back before the failure is said.

**Fixed (VIP)**: firewalld was reloaded at every change of the pages while the VIP is on, to let the other node's VRRP in - a reload throws away what others hold only in force, such as fail2ban's bans. The rule is now added kept and in force, without a reload.

**Fixed (HA)**: in a cluster whose VIP address is IPv6, every change of a node's network was refused with "the VIP address ... is not in <its IPv4 network>". Only an IPv4 VIP is compared with the IPv4 network.

