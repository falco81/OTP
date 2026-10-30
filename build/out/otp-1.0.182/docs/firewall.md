# The firewall and who may reach the pages

Settings → **Firewall and access** looks after two things, on every node of
the cluster at once:

1. **Who may reach which pages.** The enrolment pages (`/`), the
   administration (`/admin/`) and the health check (`/healthz`) all answer
   on ports 80 and 443, so a firewall cannot tell them apart. nginx does: each
   of the three has an allow list in `/etc/nginx/conf.d/otp.conf`, between
   `# PORTAL-ALLOW-BEGIN/END`, `# ADMIN-ALLOW-BEGIN/END` and
   `# HEALTH-ALLOW-BEGIN/END`. Each is *everybody* or *only from* a list of
   addresses and networks (IPv4 and IPv6). The other node, the VIP address
   (VIP) and the machine itself (127.0.0.1, ::1) are always let in, so
   everything inside the cluster keeps working. The VIP address's server
   (`otp_vip.conf`) is a copy of the node's and has the same lists.

2. **The machine's firewall** - iptables and ip6tables (the
   `iptables-services` package on AlmaLinux / RHEL). Off by default: nothing
   is touched until it is turned on.

## What otp changes in the firewall

Only a chain of its own, `OTP-IN`, jumped to first from `INPUT`:

```
INPUT ─► OTP-IN: the other node ─► your rules (in your order) ─► what otp needs ─► the rest of INPUT
```

At the bottom of *Settings → Firewall*, *The whole firewall* shows each node's filter table as `iptables-save` shows it - every chain, OTP-IN's lines marked - read by root after every change and again on *Read it again* (1.0.68).

`OTP-IN` holds ACCEPT rules for what otp needs, plus whatever you add. It starts with three fixed rules no rule of yours can override: loopback (`-i lo`), answers to connections this machine opened itself (`conntrack ESTABLISHED,RELATED` - LDAP, DNS, mail, replication), and on IPv6 neighbour discovery (ICMPv6 133-136). Then the other node of the cluster, so no rule of yours can shut it out.
Anything it does not match goes back to INPUT and on to the rules that were
there before (your SSH, Zabbix, the final REJECT…). otp never changes those.

It is put in at once (`iptables-restore --noflush`, all of the chain in one
go) and also written into `/etc/sysconfig/iptables` and
`/etc/sysconfig/ip6tables`, between lines that start `# otp:`, so it is
there after a reboot. Each file is checked with `iptables-restore --test`
first and left as it was if the check fails. A later `service iptables save`
does no harm: otp finds its lines again by their names.

Turned off, the jump and the chain are taken away (live and in the files),
and nothing else.

### What otp lets in by itself

| Rule | IPv4 / IPv6 | Let in | Can be turned off |
|---|---|---|---|
| SSH | both | tcp 22 from anywhere | yes - keep a rule of your own if you do |
| ICMP / ICMPv6 | both | ping; IPv6 needs ICMPv6 for neighbour discovery | yes |
| DHCPv6 client | 6 | udp 546 from fe80::/10 | yes |
| HTTP / HTTPS | both | tcp 80,443 - from everybody when one of the three page lists is for everybody, else from the networks of the three lists | yes |
| RADIUS | as the client | udp 1812 (and 1813 for accounting) from each enabled RADIUS client, only from them | yes |
| SNMPv3 | as the network | udp 161 (the port set) from the networks under *Settings → Monitoring → Only from*, from everywhere when none is set - only while SNMPv3 is on | yes |
| The other node | as the node | everything from the other node (replication, its pages, the health check, its answers) | no |
| VRRP | as the node | IP protocol 112 from the other node, while the VIP address is on | no |

They follow what is set up: a client added, the cluster made, the VIP address
turned on - and the rules change within a few seconds.

### Rules of your own

Accept, drop or reject; TCP, UDP, ICMP, VRRP or any protocol; a port, a
range (`8000-8100`) or several (`80,443`); from an address or a network;
IPv4, IPv6 or both; for every node or one. They come after the other node and before the rest of otp's own in
`OTP-IN`, in the order shown, so a DROP of yours wins over what otp lets in.
Each one carries its note as an iptables comment (`otp: Zabbix agent`).

## Before turning it on

```
dnf install iptables-services
systemctl disable --now firewalld        # if it is running
systemctl enable --now iptables ip6tables
```

If firewalld is running, otp leaves the firewall to it and says so on the
page. What firewalld must let in is in [tls-and-vip.md](tls-and-vip.md).

## Doing it by hand instead

The same as otp does, on each node (here otp1 = 192.168.42.32, otp2 =
192.168.42.33, a RADIUS client 10.1.2.3):

```
iptables -N OTP-IN
iptables -I INPUT 1 -j OTP-IN
iptables -A OTP-IN -i lo -j ACCEPT
iptables -A OTP-IN -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
iptables -A OTP-IN -p tcp -m multiport --dports 80,443 -j ACCEPT
iptables -A OTP-IN -s 10.1.2.3 -p udp -m multiport --dports 1812,1813 -j ACCEPT
iptables -A OTP-IN -s 192.168.42.33 -j ACCEPT
iptables -A OTP-IN -s 192.168.42.33 -p vrrp -j ACCEPT
service iptables save
```

(on otp2 the other node is 192.168.42.32), and the same with `ip6tables` for
IPv6.

## Checking

```
iptables -S OTP-IN; ip6tables -S OTP-IN
grep -n otp /etc/sysconfig/iptables
otp --web-status                  # what root did last, node by node
```

## On trial (1.0.137)

A change of the firewall or of who may reach the pages goes back by itself
unless kept within `fw_confirm_min` minutes (5): the banner on every page, or
`otp --change-keep fw`. See [sign-in-protection.md](sign-in-protection.md).
