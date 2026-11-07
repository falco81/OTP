# Re-addressing a node of an HA pair from the pages — what we found in otp 1.0.261, and how to port it to acme

For the developers of **acme**, which runs the same HA code as otp (two nodes, each with its own
PostgreSQL 16, logical replication both ways, a VRRP VIP by keepalived, the root helper
`otp_web.py`). This is the result of a test campaign on **changing a node's address through the
pages** (Settings → Network → *Change it and restart*, then *Keep it* on the trial banner) in every
combination of:

| dimension | values |
|---|---|
| the replication link between the nodes (Settings → High availability → the link's TLS) | encrypted + checked (verify-full) / not |
| each node's own connection to its database (Settings → The database → Encryption) | verify-full / not |
| which node is re-addressed | node A / node B / both (A, then B) |
| address families | IPv4 only / dual stack IPv4 + IPv6 |

24 cases. Each case runs on a fresh sandbox; RADIUS is asked through the VIP address all the time.

Function and file names below are otp's (`parts/*.py` are concatenated into `otp.py`;
`deploy/otp_web.py` is the root helper). In acme, find the same functions under the same names.

---

## 1. How to run the matrix

Prerequisites: the full HA sandbox (`tests/hasb`), root, PostgreSQL 16 clusters `main` (5432,
node A) and `second` (5433, node B), keepalived installed, `psycopg2`.

```
# one case
python3 tests/r261/t_ha_readdress.py VERSION --stack ipv4|dual --link on|off --db on|off --which a|b|both

# the whole matrix: one line per case, then "ALL n / m" (cases passed)
python3 tests/r261/t_ha_readdress.py VERSION --all            # logs: /tmp/claude-0/f261/logs/
python3 tests/r261/t_ha_readdress.py VERSION --all --only 'dual.*both'   # a part of it
```

What one case does:

1. Stops every sandbox process by exact PID, makes a fresh sandbox (`newsb.sh`, with
   `OTP_SB_STACK=dual` for dual stack), puts on `lo` only the addresses each node's NetworkManager
   profile names (secondaries promoted, so taking `10.99.0.1` away takes no other address with it).
2. Through the API, as the pages do it: an administrator signs in; `net_confirm_min = 2`
   (a new network goes back unless kept within 2 min); each node's own self-signed web
   certificate (`/api/web tls_selfsigned`, naming its address, and its IPv6 one in dual stack);
   the VIP address `10.99.0.200/24` (+ `fd99::200/64` in dual stack) saved and switched on;
   keepalived started on both nodes from the files the root helpers write.
3. The TLS combination: `/api/ha {action: tls_link}` and waiting for both nodes' steps to be
   `done`; `/api/dbtls` phases `server` then `connect` with `verify-full` (exactly the wizard's
   two steps).
4. Replication checked both ways (a row written on each node, seen on the other), a RADIUS prober
   started (each node and the VIP address, every 0.3 s).
5. The re-addressing, from the pages of the **other** node (the changed node restarts):
   `/api/net {action: read}` (Read it again) and wait for the node's network row; the `want`
   built from that row exactly as `admin.js` builds it, only the IPv4 address (and in dual stack
   the IPv6 address) changed; `/api/net {action: plan}` (Check it), `/api/net {action: apply}`.
   The node's reboot is simulated when its root helper writes the reboot request: keepalived and
   the daemon of that node stopped, the old addresses taken off `lo` and the new ones put on, as
   the profile now says, the daemon started with a new boot time, keepalived started again. When
   the job waits on trial, `/api/trial {kind: net, action: keep}` (the banner's *Keep it*).
   Node A: `10.99.0.1 → 10.99.0.3` (`fd99::1 → fd99::3`); node B: `10.99.0.2 → 10.99.0.4`
   (`fd99::2 → fd99::4`).
6. Afterwards it checks: both nodes answer and sign in; replication both ways; every step of the
   job good, the job `done` and kept; `config.json` `ha_address` / `ha_peer` on both;
   each subscription's `host=` the other node's new address, running, `sslmode=verify-full`
   when the link is encrypted; each `pg_hba.conf` lets the other node's new address in
   (`hostssl` with the link encrypted, `host` otherwise) and no longer its old one; the link
   encrypted and checked on both nodes (`net_hatls_ok`), each PostgreSQL's certificate naming the
   node's new address both as an IP and as a DNS name and ending 2 years from now; `ha_tls`,
   `db_tls` as set and the daemons' own connections encrypted when set; with the database's TLS
   alone, its PostgreSQL certificate made again for the new address; the profile, `/etc/hosts`
   and the web certificate naming the new addresses and not the old; keepalived's
   `unicast_src_ip` / `unicast_peer` the new addresses (and the IPv6 VIP address in its file);
   the VIP address served, a code from the app let in through it; RADIUS through the VIP address
   unanswered 15 s at most; no node left in maintenance; the HA page's addresses right; no event
   of level *bad* since the change began; no alert left; nothing new in *To be done by hand*.

The kernel of our test machine has **no IPv6 at all** (no `/proc/net/if_inet6`, `AF_INET6` not
supported): the dual-stack cases check what the product writes for IPv6 (NetworkManager, `/etc/hosts`,
the certificates, keepalived's file, RADIUS falling back to IPv4), not IPv6 packets. On a machine
with IPv6, the same test also puts the `fd99::` addresses on `lo`.

### Results

**Before the fixes** (otp.py and otp_web.py of 1.0.261 as they were; a sample of 7 of the 24
cases – partial on purpose: every case fails at the same step, problem 1):

| case | checks passed |
|---|---|
| `ipv4 link=on db=off which=a` (first run) | 47 / 63 |
| `ipv4 link=on db=on which=a` | 56 / 71 |
| `ipv4 link=on db=off which=both` | 49 / 74 |
| `ipv4 link=off db=on which=a` | 50 / 66 |
| `ipv4 link=off db=off which=b` | 46 / 61 |
| `dual link=on db=on which=both` | 54 / 81 |
| `dual link=on db=off which=b` | 56 / 72 |

In each, the job failed ("the host name is the whole name") after the other node had been told,
was put back, and the checks of the new addresses failed. Problems 2–4 were hidden behind
problem 1 and showed once it was fixed.

**After the fixes**: the whole matrix **24 / 24** cases, every check of every case passed – three
times (with problems 1–3 fixed; with 1–4 fixed; once more on the final code after the test machine
restarted, run in two parts), 2–5 minutes a case. RADIUS through the VIP
address: no probe lost in most cases, one probe (a gap of about 2 s) in a few - the moment the
VIP address moves between the nodes.

---|---|---|
| `ipv4 link=on db=off which=a` (first case run) | **47 / 63** — the change failed at root, see problem 1 | 68 / 68 |
| whole matrix | every case fails at the same step (problem 1: the sandbox's nodes have short host names) | **24 / 24** cases (see the run's summary in the final report) |

Problems 2 and 3 were hidden behind problem 1 and showed once it was fixed.

---

## 2. The problems and the fixes

### Problem 1 — a node whose host name is short cannot be re-addressed from the pages at all

**Symptom.** *Change it and restart* on a node whose static host name is short (`otp1`, not
`otp1.example.cz`) – the page fills the field with the name the node has – ends a few seconds later
with the job *failed*: "stopped: the host name is the whole name: otp1.example.cz – nothing of the
network was changed". Before that, the other node had been told the new address and then told the
old one again ("put back"), replication from the node stopped for that time, and an event of
level *bad* said so.

**Scenario.** Any re-addressing from the network page where the host name is left as it is and the
machine's static host name has no dot. (Most of our test machines; many real installations.)

**Root cause.** Two checks of one rule that disagree:

* the daemon, `net_check()` (`parts/87n_net.py`): a host name **kept as it is** may be short
  (comment "1.0.139": the name the node has now may be a short one) – the plan is accepted;
* the root helper, `net_checked()` (`deploy/otp_web.py`): a short name is refused unless the
  request is a going back (`rollback`).

So the daemon told the other node, wrote its settings, put the node into maintenance – and root
refused the request. `net_job_run()` put everything back (`net_job_undo_told`, `net_undo_put_back`),
so nothing was left broken, but the change could never be made.

**Fix** (`deploy/otp_web.py`):

```diff
     host = str(r.get('hostname') or '').strip().rstrip('.').lower()
-    # Going back may ask for a short name again - the one the machine had.
-    if host and (not NAME_RE.match(host) or ('.' not in host and not r.get('rollback'))):
+    # Going back may ask for a short name again - the one the machine had. So may a change
+    # that keeps the name the machine has now (1.0.261): ...
+    if host and (not NAME_RE.match(host) or ('.' not in host and not r.get('rollback') and
+                                             host != net_static_hostname())):
         raise Refused('the host name is the whole name: otp1.example.cz')
 ...
+def net_static_hostname():
+    """The machine's static host name as it is now, lower case ('' unknown) (1.0.261)."""
+    try:
+        return run([HOSTNAMECTL, '--static'], 'hostnamectl').strip().rstrip('.').lower()
+    except (Refused, OSError):
+        return ''
```

A new short name is still refused; the one the machine has may be kept. (The root helper is
installed by `install.sh`; acme's equivalent must be shipped with the daemon of the same version.)

**How to test.** `t_ha_readdress.py VERSION --which a` on the sandbox (its nodes are `nodea`,
`nodeb`): before, the job fails with the message above; after, it goes through. Unit level: call
`net_checked({'con': 'x', 'ipv4': {'addr': '192.0.2.10/24'}, 'hostname': '<hostname --static>'})`
– accepted; with another short name – refused.

### Problem 2 — a planned change is reported as failures (events of level *bad*, mailed)

**Symptom.** Every re-addressing (and every planned maintenance) left events of level *bad* – the
alerts mail them as failures:

* on the other node: "replication coming in (otp_from_1): stopped – the other node or its
  PostgreSQL is not reached, or an error stops it";
* on the node changed: "nodeA is not healthy – in maintenance: the VIP address leaves it";
* where the restart takes long enough to miss heartbeats: "nodeA stopped answering".

**Scenario.** Re-addressing node A: by design the other node is told the new address first
(its `pg_hba.conf`, its subscription and its `ha_peer` move to it), so its subscription cannot reach
A until A has restarted with that address – replication A → B stops for the minute or two of the
change, then starts again by itself. Then A goes into maintenance (the VIP address moves away) and
restarts. All of it was asked for.

**Root cause.** `ha_watch_tick()` (`parts/88w_web.py`) gives every subscription that is not running,
every node that stops answering and every unhealthy state the level *bad*, whatever the reason; and
`vip_watch()` sets the health reason `'in maintenance'` for a maintenance asked for.

**Fix** (`parts/88w_web.py`): a helper that says which other nodes are away on purpose now – a
network job active for them (`net_job_active(net:job:NODE)`: asked, running, rebooting), or a
restart of a power plan under way (`power:node:NODE` state `going`) – and the three events use it:

```diff
+def ha_planned_away(store):
+    """{node: why} of the other nodes away on purpose now (1.0.261) ..."""
+    out = {}
+    try:
+        me = node_name()
+        plan = power_plan(store)
+        for n in ha_nodes(store):
+            name = n['name']
+            if name == me:
+                continue
+            if net_job_active(_meta_json(store, 'net:job:' + name)):
+                out[name] = '%s is changing its network' % name
+                continue
+            row = _meta_json(store, 'power:node:' + name) or {}
+            if plan and row.get('id') == plan.get('id') and row.get('state') == 'going' and \
+                    time.time() - fnum(row.get('moved')) < 900:
+                out[name] = '%s is restarting' % name
+    except Exception:
+        return {}
+    return out

 in ha_watch_tick():
-                       'info' if ok else 'bad')
+                       'info' if ok else ('warn' if why == 'in maintenance' else 'bad'))
 ...
+    planned = ha_planned_away(store)
     ... node stopped answering:
-                   'info' if n.get('alive') else 'bad')
+                   ... + ' - expected: <why>' when planned
+                   'info' if n.get('alive') else ('warn' if n['name'] in planned else 'bad'))
 ... replication coming in stopped:
+        why_planned = '; '.join(planned.values())
-   'stopped - the other node or its PostgreSQL is not reached, or an error stops it'  /  'bad'
+   'stopped - expected while <why>; it starts again by itself once that is over'  /  'warn'
+   (unchanged words and 'bad' when nothing planned)
```

The node's job row reaches the other node by replication; when replication from the node changed
has already stopped, the other node still has its last row (`running`, moved seconds ago), so it
still reads as active. A job that stalls is no longer active after `NET_JOB_LIVE_S` (30 min) – a
replication that stays stopped is then *bad* again.

**How to test.** The matrix checks "no bad event since the change began". By hand: re-address a
node and read Settings → High availability → history: *warn* lines saying "expected while nodeA is
changing its network", then "running again".

### Problem 3 — dual stack: the node's own web certificate keeps naming the old IPv6 address

**Symptom.** After re-addressing a dual-stack node (`fd99::1 → fd99::3`), its self-signed web
certificate named `10.99.0.3`, `fd99::3` **and the old `fd99::1`**.

**Scenario.** Dual stack, the IPv6 address set by hand changed together with the IPv4 one, a
certificate made on the pages (self-signed) that names the IPv6 address.

**Root cause.** `net_cert_again()` (`parts/87n_net.py`) swapped the old IPv4 address and the old
host name for the new ones, but knew nothing of the old IPv6 address: `net_check()` did not carry
it in the job's `want`, and the new one was only appended. Besides, the names were compared as
text, and `cert_info()` gives IPv6 SANs as openssl prints them (`FD99:0:0:0:0:0:0:1`), so even a
known old address would not have matched `fd99::1`.

**Fix** (`parts/87n_net.py`):

* `net_check()` adds `old_ip6`: the IPv6 addresses the profile has set by hand
  (`ipv6_method == 'manual'`), without prefix;
* a key for comparing names – an address in one canonical form, a name in lower case:

```python
def _cert_name_key(n):
    n = str(n or '').strip()
    try:
        return str(ipaddress.ip_address(n.strip('[]')))
    except ValueError:
        return n.lower()
```

* `_cert_names_swap()` compares by that key (and drops a name swapped to `''`);
* `net_cert_again()`: each old IPv6 address that is not the new one is swapped for the new one
  (or dropped when IPv6 is switched off); the trigger "does the certificate name anything that
  changed?" and the new CN use the key; the new IPv6 address is appended only when not there yet.
  A certificate from an authority is still only said, not changed.

**How to test.** `t_ha_readdress.py VERSION --stack dual --which a`: the check "its own web
certificate names 10.99.0.3 and fd99::3" (and not `10.99.0.1` / `fd99::1`).

### Problem 4 — "the certificate nginx has is not the one saved" after every certificate made again (two nodes on one machine)

**Symptom.** After each re-addressing, a warning on the node changed: "the certificate nginx has
on nodeA is not the one saved (/etc/nginx/certs/otp.pem holds another certificate): put in again",
and the web part asked of root once more.

**Scenario.** The node's own certificate made again by the change (problem 3's
`net_cert_again`), on a machine where the root helper is told to put the certificates elsewhere
(`OTP_VIP_CERT_DIR` – our sandbox, two nodes on one machine).

**Root cause.** Two names of one folder: the root helper writes the certificates nginx serves into
`CERT_DIR = os.environ.get('OTP_VIP_CERT_DIR', '/etc/nginx/certs')` (`deploy/otp_web.py`), while the
daemon's check `web_drift()` (`parts/88w_web.py`) read the fixed `NGINX_CERT_FILES =
{'node': '/etc/nginx/certs/otp.pem', ...}` – on the test machine the certificate of another
installation. On a production node both are `/etc/nginx/certs`, so it is only a false warning
there – but it hides a real drift check in every test with the folder moved.

**Fix** (`parts/88w_web.py`):

```diff
-NGINX_CERT_FILES = {'node': '/etc/nginx/certs/otp.pem', 'vip': '/etc/nginx/certs/otp-vip.pem'}
+_NGINX_CERT_DIR = os.environ.get('OTP_VIP_CERT_DIR') or '/etc/nginx/certs'
+NGINX_CERT_FILES = {'node': os.path.join(_NGINX_CERT_DIR, 'otp.pem'),
+                    'vip': os.path.join(_NGINX_CERT_DIR, 'otp-vip.pem')}
```

**How to test.** The matrix checks "no warning of something that went wrong meanwhile" (a warning
with *could not / cannot / failed / did not / not put in / not the one saved*).

### Problem 0 (the test sandbox, not the product) — the sandbox maker left the slots of an older sandbox

`newsb.sh` dropped the subscriptions and replication slots of older sandboxes **before** it
started the PostgreSQL clusters; after a restart of the test machine they were down, nothing was
dropped, and the join failed with "replication slot otp_from_1 already exists" – while the script
still printed "made and joined". Fixed in `tests/hasb/newsb.sh`: the clusters are started (and
waited for) first, and a join that did not leave `ha_mode: replicated` in node B's `config.json`
fails the script. If acme has a copy of the sandbox, port it.

The sandbox's `setup.sh` takes `OTP_SB_STACK=dual`: each node's profile with `ipv6.method=manual`,
`ipv6.addresses=fd99::1/64` (`::2`), an IPv6 gateway and DNS server, its `/etc/hosts` line, a
`pg_hba` line for `fd99::/64`, the address on `lo` where the kernel has IPv6. Without the variable
everything is as before.

---

### Files changed, for porting

| file | function(s) | problem |
|---|---|---|
| `deploy/otp_web.py` (root helper) | `net_checked()`, new `net_static_hostname()` (its fallback changed in 1.0.262, fix 9) | 1 |
| `parts/88w_web.py` | new `ha_planned_away()`, `ha_watch_tick()` | 2 |
| `parts/87n_net.py` | `net_check()` (`old_ip6`), new `_cert_name_key()`, `_cert_names_swap()`, `net_cert_again()` | 3 |
| `parts/88w_web.py` | `NGINX_CERT_FILES` from `OTP_VIP_CERT_DIR` | 4 |
| `tests/hasb/newsb.sh`, `tests/hasb/setup.sh` | the sandbox (clusters first, join checked; `OTP_SB_STACK=dual`) | 0 |
| `tests/r261/t_ha_readdress.py` | the matrix | – |

No new setting, no new text on the pages (so no translations); nothing changes for a standalone
node (problems 1 and 3 are the network page's, also used there; 2 and 4 behave as before when
nothing is planned and the folder is not moved).

## 3. What works as designed (checked, nothing to port)

* The order of a re-addressing (as of 1.0.262, round 3 R3-6: maintenance and the VIP leaving come
  first): the other node told (`ha_readdress` → `readdress_tell` → the other node's `readdress_tick`), `pg_hba.conf` keeping the old address beside the new one while
  on trial (`keep_old`), the old line dropped once kept (`readdress:dropold:NODE`,
  `readdress_dropold_tick`) - in 1.0.261 also when the address had not changed, which dropped the
  node's own line (fixed in 1.0.262, R3-1).
* The link's TLS after a new address: `ha_readdress` calls `hatls_check_soon()`; `hatls_check()`
  sees that the node's PostgreSQL certificate does not name its new `ha_address` and makes a new one
  (both as IP and DNS SAN, for libpq 13) before the restart; after the restart `net_job_after()`
  waits for `net_hatls_ok()`. Subscriptions keep `sslmode=verify-full`, `pg_hba` keeps `hostssl`.
* The database's TLS alone (link off): the node's PostgreSQL certificate from `dbtls:server` is made
  again for the new address by `dbtls_tick()` (its names differ from `hatls_names()`).
* keepalived: both files rewritten with the new `unicast_src_ip` / `unicast_peer` from
  `ha_address` / `ha_peer`; the VIP address moved to the other node for the change (and back after
  only with the VIP's "back" preference).
  RADIUS through the VIP address: at most one probe lost (about 2 s) while the address moved.
* A failure half way is put back (problem 1 showed it): the other node told the old address
  again, settings, `config.json` and the certificate as they were, out of maintenance. In 1.0.261
  only for a failure inside the job; after a daemon restart in the middle, or the one-hour give-up,
  the settings stayed on the new address (fixed in 1.0.262, R3-2).

## 4. Left open / notes

* **IPv6 traffic not tested** (no IPv6 in our test kernel): the IPv6 VIP address
  (`virtual_ipaddress_excluded`) and RADIUS on `::` are only checked as written. Replication stays
  on IPv4 by design (the network page says so).
* **Secondary IPv4 addresses**: fixed in otp 1.0.262 - see section 5, fix 5.
* **The old address stays "needed" in the link's certificate**: `hatls_needs()` takes the other
  node's `peer_host` from that node's TLS state row, written when its steps last ran – after a
  re-addressing it still names the old address, so the renewed certificate names the old and the
  new one. Harmless (an extra SAN); it goes at the next full run of the steps.
* With the database's TLS off, the daemon's own connection uses libpq's default `sslmode=prefer`:
  where PostgreSQL has a certificate (the link's), it is encrypted, unchecked. Expected; the test
  only checks that `db_tls` is as set.

## 5. Found after the matrix: otp 1.0.262 (three bug-hunt rounds over the HA and re-addressing code)

A code review of the same code the matrix ran, looking for what the matrix does not cover:
split mode *priority*, the other node out of service, `radius_bind` on a specific address,
addresses where one is the start of the other, secondary addresses, going back after a trial on
/32 cloud networks, shared-database clusters, reboots longer than the alert delay, machines with
no static host name. Round 1's fixes are listed first; rounds 2 and 3 corrected some of them (marked "replaced") and found more - their
list follows. Everything is in otp 1.0.262; the matrix (24 cases) and the new `--extra` cases were run on it.
Unit tests: `tests/r262/t_ha_fix.py` (pure Python, the functions taken out of the parts).

### Fix 1 — Split brain rule: preferred node re-addressed (87y_split.py split_preferred_unable)
- Problem: with split_mode=priority the non-preferred node steps aside whenever the nodes are apart.
  While the preferred node was being re-addressed (told the new address, then rebooting) it was silent
  too, so neither node answered RADIUS.
- Fix: a fresh net job for the preferred node (net_job_active of 'net:job:NAME') or ha_planned_away()
  naming it counts as "the preferred node is known not to serve", so the other node keeps serving.

### Fix 2 (replaced by round 2 A) — Re-address with nobody else serving (87n_net.py net_ask, net_job_run step 5)
- Problem: a network change in a cluster puts the node in maintenance and reboots it, but it was asked
  even when the other node was down or in maintenance, so the whole service stopped.
- Fix: net_ask refuses a non-rollback change unless net_others_serving(store, node) is non-empty
  (others_in_service when the node is this one; this node counted when it is the other one).
- The job checks others_in_service() again just before maintenance_set; if nobody answers, it fails
  before the network is touched, and the usual undo (other node told back, settings put back) runs.
- Rollback is never refused.

### Fix 3 (replaced by round 2 B) — radius_bind carried over to the new network (87n_net.py net_bind_after)
- Problem: only an exact old-IPv4 bind moved to the new IPv4. A bind on the old IPv6 address, or on any
  address the machine would no longer have, stayed, and RADIUS listened on an address that was gone.
- Fix: 0.0.0.0/:: as before; old IPv4 becomes new IPv4; old manual IPv6 becomes new IPv6 ('::' if IPv6
  is automatic, '0.0.0.0' if IPv6 goes off); any other specific address not among the new ones (new
  IPv4, new IPv6, secondary IPv4 kept) becomes '0.0.0.0' ('::' if it was IPv6 and IPv6 stays on).

### Fix 4 — Address equality in ha_readdress (87u_readdress.py)
- Problem: `peer in (mine or had_mine)` was a substring test on strings: 10.0.0.1 "was in" 10.0.0.12,
  and a valid readdress was refused with "the two nodes cannot have one address".
- Fix: compare one normalised address to the other (_cert_name_key(peer) == _cert_name_key(mine)).

### Fix 5 — Secondary IPv4 addresses kept (otp_web.py net_apply, 87n_net.py step 2)
- Problem: root's nmcli call set ipv4.addresses to the new address alone, so a second address
  (e.g. one used for replication) vanished; and the other node was told the new primary address even
  when replication ran over the secondary one.
- Fix (root): net_addrs4_after() keeps the manual addresses after the first; only the first (the old
  primary) is replaced. DHCP before: the new address alone, as before.
- Fix (daemon): ha_readdress(mine=new_ip) only when CONFIG ha_address is '' or the old primary;
  ha_address == primary (the usual case) works exactly as before.

### Fix 6 — Rollback refused for its gateway (87n_net.py net_check, otp_web.py net_checked)
- Problem: going back re-checked the old gateway; an on-link gateway outside the subnet, or an IPv6
  gateway root does not take, refused the rollback and the untested network stayed.
- Fix: on rollback the subnet check is skipped (root accepts it too with rollback), and a gateway that
  is not an address at all is left out, as DNS servers and search domains already were.

### Fix 7 (replaced by round 2 C and round 3 M) — keepalived peer in a shared-database cluster (88w_web.py vip_peer_want)
- Problem: ha_peer is written once at the join; after the other node's address changed keepalived kept
  unicasting to the old address and both nodes could hold the VIP.
- Fix: with ha_mode=shared, a fresh heartbeat address of the other node (< 2 min old) wins over ha_peer
  when they differ. Replicated mode unchanged (ha_peer is moved by ha_readdress).

### Fix 8 — Alerts during a re-address (88z_alerts.py alerts_quiet)
- Problem: only maintenance rows, upgrades, OS updates and restarts quieted alerts; a node being told a
  new address and rebooting raised failure alerts before its maintenance row replicated.
- Fix: an active net job of any node, or ha_planned_away() naming one, quiets alerts as maintenance does
  (and for the usual 10 minutes after).

### Fix 9 — Short host name check without hostnamectl (otp_web.py net_static_hostname)
- Problem: when `hostnamectl --static` printed nothing or failed, '' was returned and a machine with a
  short name could not keep it in a network change, while net_read reported the kernel name.
- Fix: fall back to os.uname().nodename, lower-cased, trailing dot removed - as net_read does.

### Fix 10 — Certificate state from the configured nginx path (88w_web.py web_state)
- Problem: cert_now/vip_cert_now read /etc/nginx/certs/otp*.pem even when OTP_VIP_CERT_DIR moved them.
- Fix: read NGINX_CERT_FILES['node'] / ['vip'], the same paths root writes and web_drift reads.

### Round 2 (a review of round 1 and the rest of HA)

#### A — Re-address refusal (replaces fix 2)
- The round-1 rule (refuse unless another node serves) blocked for good a node whose partner died,
  or one made standalone with --ha-standalone (in_cluster stays true).
- Now net_others_held(): refuse only when another node is heard from (fresh heartbeat) but out of
  service (maintenance, stepped aside), or any other node's network is on trial (as power_ask). A
  dead or absent partner never blocks. The job re-checks the same thing before maintenance_set.

#### B — radius_bind (replaces fix 3)
- The round-1 rule widened specific binds to 0.0.0.0 for addresses outside the change (second NIC,
  the VIP with ip_nonlocal_bind, SLAAC IPv6).
- Now rewritten only when the bind is an address the change removes: old_ip -> new_ip, an old
  manual IPv6 -> the new IPv6 (or ::/0.0.0.0). Anything else is left exactly as it was.

#### C — keepalived peer in shared mode (replaces fix 7)
- The heartbeat carries node_address() (default-route source), not the VRRP link's address.
- Now the other node's ha_address as it publishes it in 'net:now:NAME' wins over ha_peer; a node
  that does not publish one (1.0.261) keeps ha_peer. Replicated mode unchanged.

#### F — VIP address family
- own/peer of another family than the VIP (IPv6 cluster + IPv4 VIP, or the other way round) made
  root refuse the whole web request forever. vip_family_fix() picks addresses of the VIP's family
  (this machine's own; the other node's heartbeat or its published live addresses, in the VIP's
  subnet first); none -> the VIP waits (existing log), never a mismatched pair; a remembered pair
  of the other family is dropped.

#### G — Cluster CA made twice
- Replicated, no 'hatls:ca' yet: both nodes in the dbtls server phase made one -> two INSERTs of
  the one row, replication stopped. Only ha_lead makes (or rolls) it; the other waits up to 60 s for
  it to replicate (or keeps its still-valid one when only a roll is due).

#### H — Split rule changed while apart
- While the nodes are apart, each side keeps its own change; the preferred node changed on one
  side only made each take the other for it - both stepped aside. Changing split_prefer is refused
  while apart (409). A mode or an arbiter set on each half is still taken: that is how the halves
  are run while apart (the HA split test does exactly that; refusing it broke the test and left the
  test's split mode on).

#### I — Link TLS failed only waiting for the peer
- A 'failed' state with failed_step 'link' and nothing wrong locally waited an hour. hatls_check now
  puts it back to step 'link' with link_since reset, so it finishes once the peer passes.

#### J — otp --ha-forget
- An extra DELETE of maint:/upgrade:node: rows removed them even for a node still answering;
  ha_forget already removes them only when the node is not alive. Dropped the extra DELETE.

#### K — Directory failover and the peer's clock
- A node stepped aside for the directory toward a peer whose clock was off (serving only because
  this node could not take over). Now the peer's clock must be within clock_aside_s too (not measured
  = as before), in clock_decide and clock_dir_failover.

#### L — upgrade:online written by both nodes
- Both nodes' daily look could INSERT the first 'upgrade:online' row -> replication stopped. In
  replicated mode only ha_lead looks (the other takes over when it hears no other).

### Round 3 (the whole re-addressing flow again, step by step)

#### R3-1 — Keep dropped the node's own pg_hba line
- Keep wrote readdress:dropold whenever the trial had keep_old, also for a gateway/DNS/name change
  or replication on another address; the other node then removed "the old" line = the current one.
- Now only when the other node was told (job 'told'), the IPv4 address changed and old != new; the
  root helper's pgtls_peer also treats old == new as nothing to drop (patch r3_otpweb_patch.py).

#### R3-2 — Restart of the service mid-job left settings on the new address
- `before` (net_undo_now) is kept at the job's start in STATE_DIR/net-before.json (0600, never on the
  pages; the certificate row may hold sealed key material). net_job_stalled and net_job_give_up put
  it back with net_undo_put_back; the file goes when the job ends (done/trial/failed).

#### R3-3 — Maintenance never ended for legacy shared clusters
- net_job_after judged the cluster by bool(ha_mode) while net_job_run used in_cluster(); with an
  empty ha_mode the maintenance it set stayed. Now in_cluster(), and maintenance ends whenever the job
  set it (job['maint']).

#### R3-4 — Trial time-out while nobody else answers
- On time-out only, going back (a reboot) waits up to 30 min while another node is heard but out of
  service (net_others_held) or no other node answers in a cluster; the reason is written as a job
  step. Keep / "go back now" are not delayed. Trade-off: a network that cut the node off also goes
  back up to 30 min later.

#### R3-5 — tell_after tried once
- After going back from an address the other node could not reach, a failed tell is kept in
  'readdress:tell:NODE' and retried from net_tick (every minute with a fresh heartbeat of the other
  node, every 5 min otherwise) until it succeeds; dropped if ha_address moved on meanwhile.

#### R3-6 — Order: maintenance before telling the other node
- The held check, maintenance and waiting for the VIP to leave now come before ha_readdress, so the
  other node's keepalived is re-pointed while it already holds the VIP. Undo paths are unchanged
  (nothing told yet if it stops there; maintenance taken off as before).

#### R3-7 — radius_bind saved too early
- The new radius_bind is saved once root has accepted the apply (just before the reboot); pending
  in job['bind_later'] and set by net_job_after if root's answer came late; on a half-way root
  failure it is saved with db_host as before. A root refusal leaves it untouched.

#### R3-8 — Replication over IPv6
- ha_readdress tells only the new IPv4. net_check refuses (not on rollback) an IPv6 change that
  removes the IPv6 address the nodes replicate over (ha_address / ha_peer IPv6), with a message to
  change the addresses of the two nodes first.

#### M — Shared-mode keepalived peer (refines C)
- The published ha_address ('net:now:NAME') is used only if the row is < 10 min old, of the VIP's
  family (a host name resolved in it) and differs from ha_peer; otherwise ha_peer. vip_family_fix
  tries ha_peer first among the peer candidates.

#### N — ha_address given as a host name
- "Replication is on the address changed" also when ha_address is a name resolving to the old IP
  (net_ha_on_old, compared normalised).

#### O — Split card saves while apart (refines H)
- The card always sends split_mode and split_prefer; only a split_prefer that differs from the kept
  one (numbers normalised) counts as a change.

### What the test runs now beside the matrix (`t_ha_readdress.py VER --extra`)

* (a) a gateway-only change of node a on trial, Keep: node b's `pg_hba.conf` still has a's line, and replication
  runs both ways after `ALTER SUBSCRIPTION … DISABLE; ENABLE` on a (round 3, R3-1).
* (b) a new address not kept - the trial goes back: the profile, a's `ha_address`, b's `ha_peer` and `pg_hba.conf`
  on the old address, no maintenance left, replication both ways.
* (c) the change refused while b is in maintenance; accepted, and run to its end, while b's daemon is stopped.
* (d) b asked while a is rebooting or on trial - refused; accepted once a's change is kept.
