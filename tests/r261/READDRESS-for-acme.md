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
| `deploy/otp_web.py` (root helper) | `net_checked()`, new `net_static_hostname()` | 1 |
| `parts/88w_web.py` | new `ha_planned_away()`, `ha_watch_tick()` | 2 |
| `parts/87n_net.py` | `net_check()` (`old_ip6`), new `_cert_name_key()`, `_cert_names_swap()`, `net_cert_again()` | 3 |
| `parts/88w_web.py` | `NGINX_CERT_FILES` from `OTP_VIP_CERT_DIR` | 4 |
| `tests/hasb/newsb.sh`, `tests/hasb/setup.sh` | the sandbox (clusters first, join checked; `OTP_SB_STACK=dual`) | 0 |
| `tests/r261/t_ha_readdress.py` | the matrix | – |

No new setting, no new text on the pages (so no translations); nothing changes for a standalone
node (problems 1 and 3 are the network page's, also used there; 2 and 4 behave as before when
nothing is planned and the folder is not moved).

## 3. What works as designed (checked, nothing to port)

* The order of a re-addressing: the other node told first (`ha_readdress` → `readdress_tell` →
  the other node's `readdress_tick`), `pg_hba.conf` keeping the old address beside the new one while
  on trial (`keep_old`), the old line dropped once kept (`readdress:dropold:NODE`,
  `readdress_dropold_tick`).
* The link's TLS after a new address: `ha_readdress` calls `hatls_check_soon()`; `hatls_check()`
  sees that the node's PostgreSQL certificate does not name its new `ha_address` and makes a new one
  (both as IP and DNS SAN, for libpq 13) before the restart; after the restart `net_job_after()`
  waits for `net_hatls_ok()`. Subscriptions keep `sslmode=verify-full`, `pg_hba` keeps `hostssl`.
* The database's TLS alone (link off): the node's PostgreSQL certificate from `dbtls:server` is made
  again for the new address by `dbtls_tick()` (its names differ from `hatls_names()`).
* keepalived: both files rewritten with the new `unicast_src_ip` / `unicast_peer` from
  `ha_address` / `ha_peer`; the VIP address moved to the other node for the change and back after.
  RADIUS through the VIP address: at most one probe lost (about 2 s) while the address moved.
* A failure half way is put back (problem 1 showed it): the other node told the old address
  again, settings, `config.json` and the certificate as they were, out of maintenance.

## 4. Left open / notes

* **IPv6 traffic not tested** (no IPv6 in our test kernel): the IPv6 VIP address
  (`virtual_ipaddress_excluded`) and RADIUS on `::` are only checked as written. Replication stays
  on IPv4 by design (the network page says so).
* **Secondary IPv4 addresses**: `net_apply()` sets `ipv4.addresses` to the one new address; other
  addresses of the profile (our sandbox has `10.99.0.11/24` beside `10.99.0.1/24`) are dropped. The
  page shows and asks for one address only, and going back restores the whole profile – we left it,
  but say it on the plan in acme if your installations use secondaries.
* **The old address stays "needed" in the link's certificate**: `hatls_needs()` takes the other
  node's `peer_host` from that node's TLS state row, written when its steps last ran – after a
  re-addressing it still names the old address, so the renewed certificate names the old and the
  new one. Harmless (an extra SAN); it goes at the next full run of the steps.
* With the database's TLS off, the daemon's own connection uses libpq's default `sslmode=prefer`:
  where PostgreSQL has a certificate (the link's), it is encrypted, unchecked. Expected; the test
  only checks that `db_tls` is as set.
