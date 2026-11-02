# The clocks and the health of the nodes - gray failures

otp 1.0.222. Settings → Time → **The clocks of the nodes**. This document describes the whole
feature: the problem, the three modes and four switches, what each node measures and how, the
decision, every place in the program it touches, the card (HTML, CSS, JavaScript and the Czech
texts as they are), the API, the alerts, the tests, and a checklist for porting it to another
application with the same kind of two-node cluster. It is written to be enough on its own: the
other project can build the same thing, with the same card, from this file alone.

The companion document is `docs/split-brain.md` (1.0.218): *what the nodes do when they lose
each other*. This one is about the opposite case, which is harder to see: *the nodes still see
each other, and one of them is quietly wrong*.

## 1. The problem: a node that answers, wrongly

A failure that stops a node is easy. The VPN concentrator (the NAS) gets no answer, waits its
timeout, and asks the other node. Everything in a two-node cluster is built around that.

A **gray failure** is a node that is up, answers every request at once, and answers wrongly.
The NAS takes the answer: an Access-Reject is an answer. It never asks the other node. Every
person whose request lands on the sick node is turned away, and nothing in the cluster notices,
because nothing is down.

Two such failures matter for an OTP server:

1. **The clock.** A code from an authenticator app (TOTP, RFC 6238) is worked out from the time:
   `step = floor(unix_time / 30)`. The server accepts the current step and one either side
   (`totp_window`, default 1). A server whose clock is off by more than about 30-45 s refuses
   every right code. chrony normally keeps the clock right; it stops doing so when:
   - the time servers are not reachable (a firewall change, a DNS failure, a new network) and the
     clock drifts for days or weeks;
   - the virtualisation host's clock is wrong and the guest follows it (VMware Tools time sync,
     Hyper-V integration services) - the clock *steps* by minutes or hours at a resume, a
     snapshot restore or a vMotion;
   - chrony is stopped, removed, or its configuration is broken by hand;
   - the clock is set by hand (`date -s`) during troubleshooting and forgotten.

   The clock being off affects more than the codes:
   - **heartbeats**: each node writes `{'at': time.time()}` into the shared table every few
     seconds; the other judges "alive" by `now - at`. A node whose clock is 10 min *behind*
     writes beats that look 10 min old - it looks dead though it is fine. One 10 min *ahead*
     writes beats from the future - it looks alive for 10 min after it really died;
   - **pauses and lockouts**: `locked_until = t + 15 min` written with a clock 10 min behind is
     only 5 min on the other node; with a clock 10 min ahead it is 25 min. The pause after wrong
     codes (`fail_times` within `rate_limit_s`) counts wrong tries by their times: off by more
     than the span, a node's tries never meet the other's;
   - **"newer wins" stamps**: rows replicated both ways keep the newer change; a node ahead
     always wins, one behind always loses.

2. **The directory.** A realm that checks the directory password (password + code, or a code in
   a second window) refuses everybody when the node cannot reach the directory - a firewall rule
   on one node, a route lost, a domain controller reachable only from one data centre. Again an
   answer, again the NAS does not ask the other node.

### What otp did before 1.0.222 (and does still, in "As until now")

- The Settings → Time pane shows chrony's own word about each node (tracking, sources) and keeps
  the time servers for the whole cluster. 88z alerts warn when chrony says the clock is off.
- Nothing measured the clock independently of chrony. Nothing compared the two nodes' clocks.
  Nothing was done about a wrong clock: the node went on refusing right codes.
- A directory that could not be reached made the node refuse every password (Access-Reject,
  "LDAP server(s) have gone away").

**That behaviour is kept exactly as the mode "As until now", which is the default.** In it none
of the code of this feature runs: no thread is started, no SNTP packet is sent, nothing is
measured, no row is written, the codes and the locks use `time.time()` as before, heartbeats are
judged as before, no alert of this feature is raised. The tests check each of these.

## 2. The choices

### 2.1 The mode (`clock_mode`)

| Mode | What it does | Good | Costs |
|------|--------------|------|-------|
| `off` - **As until now: nothing is watched** (default) | Nothing of this feature runs. | Nothing new runs. | A node whose clock is off refuses right codes, and says nothing of why; heartbeats of a wrong clock look dead or alive for ever. |
| `watch` - **Measure and warn** | Each node asks the reference time servers itself (SNTP, every 30 s), measures the other node's clock through its database (every 5 s), checks the directory (with `health_dir`, every 15 s); shows it on the card, raises alerts. Changes nothing else unless a switch says so. | You learn of a clock going wrong before people do; each node measured on its own, not by its chrony's word. | A node whose clock is off still answers, and refuses right codes. |
| `guard` - **Step aside when not well** | As `watch`, and a node whose clock is off by more than `clock_aside_s` steps aside: maintenance nobody asked for - RADIUS is not answered, the VIP address goes to the other node - **only while the other node is well, never both**. With `health_dir`, the same for a node that cannot reach the directory. | A node with a broken clock stops refusing right codes - the other answers. Heals by itself. | With one node only, or the other not well, nothing steps aside. |

### 2.2 The switches

They act only with the mode `watch` or `guard` (in `off` nothing runs, whatever they say).

| Setting | Name on the card | What it does |
|---------|------------------|--------------|
| `clock_codes` | Codes by the corrected time | The code from the app is checked against the reference's time: `time.time() + offset`, where `offset` is the median offset of the reference servers measured in the last minutes, used only when larger than `clock_warn_s`. Right codes keep working on a node whose clock is off. With it, `guard` does not step a node aside for its clock (its codes are right). |
| `clock_beat` | Heartbeats by the measured difference | The other node's heartbeat age is `now - (at - skew)`, where `skew` is the other node's clock minus this one's as measured here. |
| `clock_locks` | Pauses and lockouts by the corrected time | `t` in the pause / lockout code is the corrected time. Lockouts written on a node whose clock is off last as long as on the other. |
| `health_dir` | Step aside when the directory cannot be reached | With `guard`: a node that cannot reach (TCP connect) any server of a directory used by a realm steps aside while the other node reaches all of them. |

### 2.3 The numbers

| Setting | Range | Default | Meaning |
|---------|-------|---------|---------|
| `clock_warn_s` | 1-60 | 2 | Off by more than this: an alert (warn), and the correction applies (with `clock_codes` / `clock_locks`). Within it, the machine's own clock is used - a small offset is never "corrected". |
| `clock_aside_s` | 5-600 | 20 | Off by more than this: the alert is "bad", and `guard` steps the node aside. Must be greater than `clock_warn_s` (refused otherwise, on the page and in the API). 20 s leaves room: with `totp_window` 1 right codes start to be refused somewhere past 30 s. |
| `clock_ref` (per node) | up to five servers | empty | Each node's own reference servers, `name` or `name:port` or `[v6]:port`. Empty: the time servers of Settings → Time (`ntp:conf`, the whole cluster's). |

`clock_ref` is a per-node setting (in `NODE_KEYS`): saved as `clock_ref@nodea`, `clock_ref@nodeb`;
the others are saved for every node (`'*'`).

## 3. The settings in the program

In `00_head.py`:

```python
DEFAULTS = {
    ...
    # The clocks and the health of the nodes (1.0.222, docs/clock-guard.md).
    'clock_mode': 'off',
    'clock_warn_s': 2,
    'clock_aside_s': 20,
    'clock_ref': '',
    'clock_codes': 0,
    'clock_beat': 0,
    'clock_locks': 0,
    'health_dir': 0,
    ...
}
NODE_KEYS = (..., 'split_arbiter', 'clock_ref')
TUNABLE = {
    ...
    'clock_mode': ('off', 'watch', 'guard'), 'clock_warn_s': (1, 60), 'clock_aside_s': (5, 600),
    'clock_codes': (0, 1), 'clock_beat': (0, 1), 'clock_locks': (0, 1), 'health_dir': (0, 1),
}
NAMES = {
    'clock_mode': 'The clocks of the nodes',
    'clock_warn_s': 'Warn when off by more than',
    'clock_aside_s': 'Step aside when off by more than',
    'clock_ref': 'Reference time servers',
    'clock_codes': 'Codes by the corrected time',
    'clock_beat': 'Heartbeats by the measured difference',
    'clock_locks': 'Pauses and lockouts by the corrected time',
    'health_dir': 'Step aside when the directory cannot be reached',
}
```

The generic settings list (`settings_state` in `80_daemon.py`) skips `clock_*` and `health_dir`:
they are drawn by their own card, which has its own rules (try the reference before `guard`,
the step aside after the warning). Without the skip they were shown again under every pane
(the same mistake 1.0.218 made with `split_*` and 1.0.219 mended).

## 4. Measuring

### 4.1 The reference: SNTP, asked by the node itself

Why not chrony's word: chrony *is* what may be wrong (stopped, misconfigured, following a bad
source, or overridden by the hypervisor). The node asks independently, with a plain SNTP client
(RFC 4330) of 40 lines, no library, no subprocess:

- one UDP packet of 48 bytes to port 123: `LI=0, VN=4, Mode=3` (`0x23`), our transmit time in the
  transmit timestamp field (bytes 40-47) so the server echoes it in the originate field
  (bytes 24-31) - that is how an answer is matched to its question (an old or forged answer is
  ignored);
- the answer must be mode 4 or 5 and stratum 1-15: stratum 0 ("kiss of death", unsynchronised)
  is not believed;
- `offset = ((t1 - t0) + (t2 - t3)) / 2`, `delay = (t3 - t0) - (t2 - t1)` with `t0` sent here,
  `t1` received there, `t2` sent there, `t3` received here. **offset > 0: this machine's clock is
  behind the server.** The card shows it as "behind by" / "ahead by";
- a timeout of 1.5 s per server, up to five servers, asked one after another;
- the **median** of the offsets of those that answered is the reference: one server gone wild
  does not move it (tested with servers at 0, +0.2 and +500 s: the result is +0.2).

Every 30 s (`CLOCK_REF_EVERY_S`). When no server is given and the cluster has none either, or
none answers, the reference is `None` with the reason in `ref_err` - and **a node with no
reference is never stepped aside** (it cannot be judged), it raises the alert "cannot ask for
the right time".

### 4.2 The other node: its database server's clock

The two nodes' clocks are compared without any new port or protocol: each node already talks to
a database that runs on the other machine.

- In a **replicated pair** (each node its own PostgreSQL, logical replication both ways) the
  node opens a connection of its own to the other node's PostgreSQL (`ha_peer_conf`, the same
  TLS and credentials as the replication) and reads `SELECT extract(epoch from clock_timestamp())`.
  That PostgreSQL runs on the other machine, so its clock is the other node's clock.
- With **one shared database server** (PostgreSQL or MariaDB, both nodes on it) each node
  measures its clock against the database server (`UNIX_TIMESTAMP(NOW(6))` on MariaDB); the
  other node's clock minus this one's is the difference of the two nodes' measurements, both
  written in the state rows: `skew(B - A) = skew(A→db) - skew(B→db)`.
- SQLite, or one node alone: nothing to measure (`None`).

The read is made three times after the connection is up, and the one with the shortest round
trip is used: `skew = there - (t0 + t1) / 2`. All of it runs in a helper thread joined for
3.5 s at most - a peer that does not answer holds nothing.

### 4.3 The directory

With `health_dir` (and only then) every 15 s: every directory used by a realm (a realm with a
`directory`), enabled, one TCP connect (2 s) to its servers in turn until one answers. `True`
when every used directory reached one server, `False` when any did not, `None` when no realm uses
a directory. It is a reachability check, not a bind: no password is sent, nothing is counted
against any account.

### 4.4 The state row

Every 10 s each node writes `meta['clock:state:<node>']`:

```json
{"at": 1793000000.1, "node": "nodea", "engaged": true, "mode": "guard",
 "ref": 0.004, "ref_at": 1792999990.0, "ref_src": "tik.cesnet.cz, tak.cesnet.cz", "ref_err": "",
 "refs": [{"server": "tik.cesnet.cz", "offset": 0.004, "words": "delay 3 ms"}],
 "skew": -0.012, "skew_of": "nodeb", "skew_err": "",
 "dir_ok": true, "dirs": [{"name": "AD", "ok": true, "words": "dc1.corp:636"}],
 "role": "serve", "why": "", "codes_fixed": false, "correction": 0.0}
```

It is how the other node, the card and the alerts (which may run in another process) know this
node's state. The other node judges the row **fresh** by its age corrected by the measured skew -
a row from a node 5 min behind is not "5 min old".

## 5. The decision

A pure function, tested alone:

```python
def clock_decide(mode, ref, aside_s, codes_fixed, dir_ok, health_dir, peer):
    if mode != 'guard':
        return 'serve', ''
    peer_well = peer fresh and serving and not in maintenance
    clock_bad = ref is not None and abs(ref) > aside_s and not codes_fixed
    if clock_bad:
        if peer_well and peer's ref is not None and abs(peer's ref) <= aside_s:
            return 'aside', "this node's clock is ... off - the other node answers"
        return 'serve', "this node's clock is off, but the other node cannot take over"
    if health_dir and dir_ok is False:
        if peer_well and peer's dir_ok is True:
            return 'aside', 'this node cannot reach the directory - the other node answers'
        return 'serve', '... neither can the other node take over'
    return 'serve', ''
```

Why it never steps both nodes aside:

- for the clock: a node steps aside only when *its* clock is bad and *the other's* is good. Both
  conditions cannot hold on both nodes at once;
- for the directory: only when this node does not reach it and the other does - again never both;
- the other node must be **serving** (`role == 'serve'`): a node already aside is never a reason
  for the second to go;
- the other node must be **fresh** (its row younger than 60 s, by the corrected age) and not in
  maintenance (an upgrade, a restart, a restore);
- no reference here, or none there: nothing is known - serve.

| This node | The other node | Result |
|-----------|----------------|--------|
| clock within `aside_s` | anything | serve |
| clock off, `clock_codes` on | anything | serve (its codes are right) |
| clock off | well, its clock right | **aside** |
| clock off | well, its clock off too | serve ("the other is no better") |
| clock off | not heard from / not fresh | serve |
| clock off | stepped aside itself | serve |
| clock off | in maintenance | serve |
| clock off | cannot ask its reference | serve |
| no reference | anything | serve (never judged by nothing) |
| directory not reached, `health_dir` | well, reaches it | **aside** |
| directory not reached, `health_dir` | does not reach it either | serve |
| directory not reached, no `health_dir` | anything | serve |

The decision is made every 5 s (`CLOCK_STEP_S`). Each change of role writes an event (kind
`time`) and a log line, and flushes the maintenance cache so RADIUS and the VIP are told at once.

## 6. Stepping aside

otp has one gate for "this node does not serve": `maintenance_now()` (88_upgrade). RADIUS
consults it before answering (no answer at all - the NAS times out and asks the other node), the
VIP check script (keepalived) consults it (the address moves), the health endpoint consults it.
The split-brain feature (1.0.218) steps aside through the same gate; this one does too:

```python
    if split_aside():
        return {'on': True, 'why': 'stepped aside: ' + ..., 'split': True}
    if clock_aside():
        # Stepped aside for its clock or the directory (1.0.222, clock_mode guard): only
        # while the other node is well, ended by itself.
        return {'on': True, 'why': 'stepped aside: ' + (CLOCK['why'] or 'this node is not well'),
                'clock': True}
```

"Not answering" is deliberate: an Access-Reject is taken by the NAS as final; no answer makes it
try the other server. The administration pages keep working on the node that stepped aside.

Switched off (mode `off`) while a node is aside: the daemon's loop sees the role still `aside`
and calls `clock_step` once, which sets it back to `serve` at once.

## 7. Codes by the corrected time

`clock_now(kind)`:

```python
def clock_now(kind='codes'):
    t = time.time()
    if not clock_engaged():
        return t
    if (kind == 'codes' and CONFIG.get('clock_codes')) or (kind == 'locks' and CONFIG.get('clock_locks')):
        return t + clock_correction()
    return t
```

`clock_correction()` is the reference offset when it is known, measured in the last 4 min, and
larger than `clock_warn_s`; else 0.

Every place the code's step is worked out uses `clock_now('codes')`:

| Where | What |
|-------|------|
| `60_engine.py` `Tokens.check` | the code of a sign-in (`totp_match(secret, code, tc, ...)` and the drift `facts['off']`) |
| `60_engine.py` `Tokens.confirm` | the code that confirms a new token |
| `60_engine.py` `Tokens.why_wrong` | "it is this token's code, but from N s ago" |
| `90_api.py` "the code now" | the administrator's look at the current code |
| `90m_mfa.py` | the administrators' own second factor |
| `87s_sshotp.py` | the SSH gate's codes |

The "used once" rule (`last_step`) is kept in steps of the corrected time: both nodes, each
correcting its own clock, agree on the step numbers.

## 8. Heartbeats by the measured difference

In `ha_nodes()` (87_ha):

```python
        # With clock_beat (1.0.222) judged by the measured difference of the clocks.
        age = clock_beat_age(store, name, float(beat.get('at') or 0), now)
```

```python
def clock_beat_age(store, name, at, now):
    if not (clock_engaged() and CONFIG.get('clock_beat')) or name == node_name():
        return now - at
    sk = clock_skew_of(store, name)
    return now - at if sk is None else now - (at - sk)
```

Without a fresh measurement (`None`) the age is as before.

## 9. Pauses and lockouts by the corrected time

`t = clock_now('locks')` in `Tokens.check`, `Tokens.confirm` and `Tokens.blocked`. The times
written in `fail_times` and `locked_until` are then the corrected times; both nodes read them
with their own corrected time.

## 10. Alerts

In `88z_alerts.py`, only when the mode is not `off`, per node from its state row (younger than
90 s):

| Key | Level | When |
|-----|-------|------|
| `clock:aside:<node>` | bad | the node stepped aside (with the reason) |
| `clock:ref:<node>` | warn | no reference server answered (with the reason) |
| `clock:skew:<node>` | warn / bad (past `clock_aside_s`) | the clock is off the reference by more than `clock_warn_s`; says whether the codes are corrected |
| `clock:peer:<node>` | warn | the two nodes' clocks differ by more than `clock_warn_s` |
| `clock:dir:<node>` | bad | with `health_dir`: the directory not reached (which, and why) |

Each alert links to the Time pane.

## 11. The API

`GET /api/clock` (any administrator) - the view:

```json
{"engaged": true, "ha_mode": "replicated", "cluster": true,
 "conf": {"clock_mode": "watch", "clock_warn_s": 2, "clock_aside_s": 20, "clock_codes": 0,
          "clock_beat": 0, "clock_locks": 0, "health_dir": 0},
 "me": "nodea",
 "nodes": [{"name": "nodea", "me": true, "alive": true, "fresh": true, "ref": "", "state": {...}},
           {"name": "nodeb", "me": false, "alive": true, "fresh": true, "ref": "ntp.local", "state": {...}}],
 "common": ["tik.cesnet.cz", "tak.cesnet.cz"]}
```

`POST /api/clock` (full administrator):

| `action` | Body | Answer |
|----------|------|--------|
| `save` | `conf` (any of the 7 keys), `refs` `{node: "servers"}`, `checked` | `{message, view}`; 400 for a bad value, a node that is not, a bad server, `clock_aside_s <= clock_warn_s`; 409 when `clock_mode` becomes `guard` without `checked: true` |
| `try` | `refs` (as written in the form) | `{id, nodes}` - a per-node ask (`node_ask 'clock_try'`): every node asks its own reference servers, the other side's clock and its directory itself |
| `poll` | `id` | `{nodes: {node: answer or null}}` |

A try answer: `{ok, ref, servers, refs: [{server, offset, words}], skew, skew_of, skew_err,
dir_ok, dirs}`.

The page's relay (`web/admin/index.php`) must pass the name on: `'clock' => '/api/clock'` in both
`$reads` and `$writes`. (1.0.218 forgot this for the split card, and the card showed its title
only; the UI test goes through the real relay for this reason.)

## 12. The card

On Settings → Time, below the tiles of each node's chrony, above nothing else: one card, styled
exactly as the split-brain card on High availability (the same `split-*` classes - one look for
both). Shown on a single node too (measuring and the corrected codes work alone; the table then
says nothing can step aside).

From the top:

1. **The title** "The clocks of the nodes" with a state tag at the right: *as until now - not
   watched* (grey), *all well* (green), *not well* (red: a node aside, off past the warning, or
   not reaching the directory).
2. **The note**: why a wrong clock is a gray failure.
3. **The tiles of now**, one per node, with a link between them: the node's name, *this page*,
   its role (*not watched* / *not heard from* / *answers* / *stepped aside*); the lines:
   *the reference: right (+4 ms)* or *behind by 312 s* (amber past the warning, red past the
   step aside) or *the reference cannot be asked - why*; *otp2: alike* or *ahead of this one by
   312 s*; with `health_dir` *reaches the directory* / *cannot reach the directory - which*;
   *codes worked out with the corrected time*; the reason it stepped aside. The link between the
   tiles shows a clock and *alike* / *apart* / *not measured*.
4. **"What is done about the clocks"**: the three modes as three big buttons (cards), each with
   its icon, title, a sentence, green pros and red cons; *As until now* carries the tag
   *as before*. The chosen one is outlined.
5. **The said line**: *Exactly as before 1.0.222: nothing of this runs, whatever the switches
   below say.* (green check) or *Each node asks the reference every 30 s and the other side's
   clock every 5 s.* (info).
6. **Two numbers**: *Warn when off by more than (seconds)*, *Step aside when off by more than
   (seconds)* - the second outlined red when not greater than the first.
7. **The reference box** (with *Measure and warn* or *Step aside*): a note, one field per node
   (*Reference of otp1*, placeholder *the time servers above: tik.cesnet.cz, tak.cesnet.cz*),
   **Try it from every node**, and its result per node: each server with *behind by / ahead by*
   and its delay or *no answer*, the other side's clock, the directory. With *Step aside* chosen
   and not yet saved: *needed before saving* until every node has answered with a reference.
8. **"And with the clock measured"**: the four switches, two by two (one column under 720 px),
   each a row with icon, title, sentence and the switch.
9. **"What happens - with the choices above"**: a table worked out from the choices as they are
   made, before saving - columns *When*, *otp1*, *otp2*, *Sign-ins*, *What it costs*, of fixed
   widths (they never move when a switch is clicked); rows:
   - otp1's clock is 5 min off;
   - otp2's clock is 5 min off;
   - both clocks off alike;
   - the time servers cannot be reached from otp1;
   - otp1 cannot reach the directory, otp2 can.

Every choice waits for the save bar at the bottom (as every other setting); *Put back* drops it.
A redraw keeps the page's scroll where it was (`scrollHeld` / `scrollBack`): a switch clicked
half-way down must not send the page to the top (1.0.220 mended that on the split card).

### 12.1 HTML

In the Time pane, after `<div id="ntp-host"></div>`:

```html
    <div class="card full" id="clock-card" hidden>
      <h2>The clocks of the nodes <span class="right" id="clock-state"></span></h2>
      <p class="note">A node whose clock is off refuses codes that are right - and answers, so the VPN does not
        ask the other node. Its heartbeat, its pauses and lockouts are off with it; a node that cannot reach the
        directory refuses every password the same way. Here each node measures itself against the time servers
        and the other node, and what is done about it is chosen.</p>
      <div id="clock-guard"></div>
    </div>
```

The relay mapping in the same file, in both `$reads` and `$writes`:

```php
'ntp' => '/api/ntp', 'clock' => '/api/clock',
```

### 12.2 CSS

The split card's classes, as they are in `web/assets/otp.css` (the clock card adds no class of
its own beyond `.split-line.warn` and the red outline of a field):

```css
.split-now{display:grid;grid-template-columns:1fr auto 1fr;gap:12px;align-items:stretch;margin:6px 0 4px}
.split-node{border:1px solid var(--line);border-radius:var(--rad);padding:12px 14px;background:var(--panel2);
.split-node.aside{border-color:var(--warn);box-shadow:0 0 0 1px var(--warn) inset}
.split-node.stale{opacity:.7}
.split-node-top{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.split-node-top b{font-size:15px}
.split-node-top .split-role{margin-left:auto}
.split-line{display:flex;align-items:center;gap:6px;font-size:13px;flex-wrap:wrap;min-width:0;overflow-wrap:anywhere}
.split-line svg{flex:none}
.split-line.good svg{color:var(--ok)}
.split-line.bad svg{color:var(--crit)}
.split-line.bad{color:var(--crit)}
.split-line.muted svg{color:var(--tx-dim)}
.split-line.warn svg,.split-line.warn{color:var(--warn)}
.split-fields .field.bad input{border-color:var(--crit)}
.split-why{margin-left:20px}
.split-link{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;
.split-link.broken{color:var(--crit)}
.split-link::before,.split-link::after{content:"";flex:1;width:2px;min-height:10px;background:currentColor;opacity:.35}
.split-link.broken::before,.split-link.broken::after{background:repeating-linear-gradient(currentColor 0 4px,transparent 4px 8px);opacity:.7}
.split-h{margin:22px 0 10px}
.split-choices{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px}
.split-choice{text-align:left;padding:14px 16px;border:1.5px solid var(--line);border-radius:12px;background:var(--panel);
.split-choice:hover:not(:disabled){border-color:var(--accent)}
.split-choice.on{border-color:var(--accent);background:var(--info-bg);box-shadow:0 0 0 1px var(--accent) inset}
.split-choice:disabled{cursor:default;opacity:.8}
.split-choice-head{display:flex;align-items:center;gap:8px}
.split-choice-k{font-weight:700;font-size:15px}
.split-choice-head .tag{margin-left:auto}
.split-choice-s{font-size:13px;color:var(--tx-mut);line-height:1.45}
.split-ic{display:inline-flex;align-items:center;justify-content:center;width:32px;height:32px;border-radius:9px;
.split-choice.on .split-ic{background:var(--accent);color:#fff}
.split-pros{margin:2px 0 0;padding:0;list-style:none;display:flex;flex-direction:column;gap:4px;font-size:12.5px}
.split-pros li{padding-left:18px;position:relative;line-height:1.4}
.split-pros li::before{position:absolute;left:0;top:0;font-weight:700}
.split-pros li.good::before{content:"+";color:var(--ok)}
.split-pros li.bad::before{content:"\2212";color:var(--warn)}
.split-fields{margin-top:16px}
.split-arb{margin-top:14px;padding:14px;border:1px dashed var(--line);border-radius:var(--rad)}
.split-arb .btnrow{margin-top:10px}
.split-tried{margin-top:10px;display:flex;flex-direction:column;gap:6px}
.split-opts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
.split-opt{display:flex;align-items:flex-start;gap:12px;padding:12px 14px;border:1px solid var(--line);
.split-opt.on{border-color:var(--accent);background:var(--info-bg)}
.split-opt.changed{box-shadow:0 0 0 1px var(--warn) inset}
.split-opt .sw{margin-left:auto;flex:none}
.split-opt-txt{min-width:0}
.split-opt-k{font-weight:650;font-size:14px}
.split-opt-s{font-size:12.5px;color:var(--tx-mut);margin-top:3px;line-height:1.45}
.split-scen td{vertical-align:top}
table.split-scen{table-layout:fixed;width:100%;min-width:760px}
.split-scen th:nth-child(1),.split-scen td:nth-child(1){width:25%}
.split-scen th:nth-child(2),.split-scen td:nth-child(2),
.split-scen th:nth-child(3),.split-scen td:nth-child(3){width:13%}
.split-scen th:nth-child(4),.split-scen td:nth-child(4){width:17%}
.split-scen th:nth-child(5),.split-scen td:nth-child(5){width:32%}
.split-scen td .tag{white-space:nowrap}
.split-when{font-weight:600}
.split-out{font-size:12.5px}
.split-out.ok{color:var(--ok)}
.split-out.warn{color:var(--warn)}
.split-out.crit{color:var(--crit);font-weight:600}
.split-report{display:flex;gap:8px;align-items:flex-start;margin-top:14px;padding:10px 12px;border-radius:var(--rad);font-size:13px}
.split-report.good{background:var(--ok-bg)}
.split-report.bad{background:var(--crit-bg)}
.split-report svg{flex:none;margin-top:2px}
.split-said{display:flex;align-items:center;gap:6px;margin:10px 0 0;font-size:13px}
.split-said.same{color:var(--ok)}
.split-said.new{color:var(--tx-mut)}
.split-said svg{flex:none}
@media (max-width:720px){.split-opts{grid-template-columns:1fr}.split-now{grid-template-columns:1fr}.split-link{flex-direction:row;padding:4px 0}
  .split-link::before,.split-link::after{width:auto;height:2px;min-height:0;min-width:20px}}
```

### 12.3 JavaScript

In `web/assets/admin.js`, before the Time pane's own code. `loadNtp()` calls `loadClock()` after
drawing the tiles, and its 10 s refresh calls `loadClock(true)` (the view refreshed, the draft and
a field being typed in left alone):

```javascript
/* ==========================================================================
   The clocks of the nodes - gray failures (1.0.222, docs/clock-guard.md)
   ==========================================================================
   One card on Settings -> Time: how far each node's clock is from the reference
   and from the other node, whether it reaches the directory, and what is done
   about it - three ways (drawn as cards), four switches, and a table of what
   happens in each kind of trouble, worked out from the choices before saving.
   The choices wait for the save bar at the bottom, as every other setting. */
var CLOCKC = {view: null, draft: null, tried: null};
var CLOCKC_MODES = [
  {k: 'off', icon: 'clock', t: 'As until now: nothing is watched',
   s: 'Each node keeps its clock with chrony, as the tiles above show; nothing of this card runs - no question to a time server, no measuring, nothing written: exactly as before.',
   good: ['Nothing new runs'],
   bad: ['A node whose clock is off refuses right codes - and says nothing of why',
         'A heartbeat of a node with a wrong clock looks dead, or alive for ever']},
  {k: 'watch', icon: 'eye', t: 'Measure and warn',
   s: 'Each node asks the reference time servers itself (SNTP, every 30 s) and measures the other node’s clock through its database. Shown here, and an alert when off - nothing else changes unless a switch below says so.',
   good: ['You learn of a clock going wrong before people do', 'Each node measured on its own, not by its chrony’s word'],
   bad: ['A node whose clock is off still answers - and refuses right codes']},
  {k: 'guard', icon: 'shield', t: 'Step aside when not well',
   s: 'As Measure and warn, and a node whose clock is off by more than the limit steps aside: RADIUS is answered by the other node, the VIP address goes to it - only while the other node is well, never both.',
   good: ['A node with a broken clock stops refusing right codes - the other answers', 'Heals by itself when the clock is right again'],
   bad: ['With one node only, or the other not well, nothing steps aside']}
];
var CLOCKC_OPTS = [
  {k: 'clock_codes', icon: 'key', t: 'Codes by the corrected time',
   s: 'The code from the app is checked against the reference’s time (this clock plus its measured offset), not this machine’s clock - right codes keep working on a node whose clock is off. With it, guard does not step a node aside for its clock.'},
  {k: 'clock_beat', icon: 'pulse', t: 'Heartbeats by the measured difference',
   s: 'The other node’s heartbeat is judged with the difference of the two clocks measured here: a node 10 min behind no longer looks dead, one ahead no longer looks alive for ever.'},
  {k: 'clock_locks', icon: 'lock', t: 'Pauses and lockouts by the corrected time',
   s: 'The pause after wrong codes and the lockout are timed by the corrected time: on a node whose clock is off they last as long as on the other, not minutes more or nothing at all.'},
  {k: 'health_dir', icon: 'people', t: 'Step aside when the directory cannot be reached',
   s: 'With Step aside when not well: a node that cannot reach the directory its realms sign in against (checked every 15 s) steps aside while the other node reaches it - rather than refusing every password.'}
];

function loadClock(quiet) {
  var card = $('clock-card');
  if (!card) return;
  api('clock').then(function (v) {
    CLOCKC.view = v;
    card.hidden = false;
    if (!CLOCKC.draft || !PENDING.clock) CLOCKC.draft = clockFresh(v);
    if (!quiet || !liveWorkedIn($('clock-guard'))) drawClock();
  }).catch(function () { /* the card stays as it was */ });
}
function clockFresh(v) {
  var c = v.conf || {}, ref = {};
  (v.nodes || []).forEach(function (n) { ref[n.name] = n.ref || ''; });
  return {mode: c.clock_mode || 'off', warn: Number(c.clock_warn_s) || 2, aside: Number(c.clock_aside_s) || 20,
          clock_codes: !!Number(c.clock_codes), clock_beat: !!Number(c.clock_beat),
          clock_locks: !!Number(c.clock_locks), health_dir: !!Number(c.health_dir), ref: ref};
}
function clockChanged() {
  return JSON.stringify(CLOCKC.draft) !== JSON.stringify(clockFresh(CLOCKC.view || {}));
}
function clockTouched(noDraw) {
  if (clockChanged()) {
    pendingSet('clock', {pane: 'time', save: clockSave, reset: function () { CLOCKC.draft = null; CLOCKC.tried = null; loadClock(); }});
  } else if (PENDING.clock) { delete PENDING.clock; markDirtyCount(); }
  if (!noDraw) drawClock();
}
function clockTried() {
  /* The reference servers as they are in the form, each node's answer good. */
  var t = CLOCKC.tried, d = CLOCKC.draft;
  if (!t || !t.done) return false;
  return Object.keys(d.ref).every(function (n) {
    return t.asked[n] === d.ref[n] && t.got[n] && t.got[n].ok === true;
  });
}
function clockSave() {
  var d = CLOCKC.draft, v = CLOCKC.view || {}, c = v.conf || {};
  if (d.aside <= d.warn) {
    toast('Stepping aside comes after the warning: more seconds than it', 'bad');
    return Promise.resolve(false);
  }
  if (d.mode === 'guard' && c.clock_mode !== 'guard' && !clockTried()) {
    toast('Try the reference from every node first: a node that cannot ask it is never stepped aside, and you would not know it is unguarded', 'bad');
    var b = $('clock-try'); if (b) b.scrollIntoView({block: 'center'});
    return Promise.resolve(false);
  }
  var refChanged = {};
  (v.nodes || []).forEach(function (n) { if ((n.ref || '') !== d.ref[n.name]) refChanged[n.name] = d.ref[n.name]; });
  var body = {action: 'save', checked: d.mode !== 'guard' || clockTried() || c.clock_mode === 'guard',
              conf: {clock_mode: d.mode, clock_warn_s: d.warn, clock_aside_s: d.aside,
                     clock_codes: d.clock_codes ? 1 : 0, clock_beat: d.clock_beat ? 1 : 0,
                     clock_locks: d.clock_locks ? 1 : 0, health_dir: d.health_dir ? 1 : 0},
              refs: refChanged};
  return api('clock', body).then(function (r) {
    toast(r.message, 'good');
    CLOCKC.view = r.view; CLOCKC.tried = null;
    CLOCKC.draft = clockFresh(r.view);
    drawClock();
    return true;
  });
}
function clockTry(btn) {
  var asked = JSON.parse(JSON.stringify(CLOCKC.draft.ref));
  busy(btn, true);
  api('clock', {action: 'try', refs: asked}).then(function (r) {
    CLOCKC.tried = {id: r.id, asked: asked, got: {}, nodes: r.nodes, done: false};
    var tries = 0;
    var poll = function () {
      api('clock', {action: 'poll', id: r.id}).then(function (p) {
        var got = p.nodes || {};
        Object.keys(got).forEach(function (n) { if (got[n]) CLOCKC.tried.got[n] = got[n]; });
        var all = (r.nodes || []).every(function (n) { return CLOCKC.tried.got[n]; });
        tries += 1;
        if (all || tries > 20) { CLOCKC.tried.done = true; busy(btn, false); }
        drawClock();
        if (!all && tries <= 20) setTimeout(poll, 1000);
      }).catch(function (e) { busy(btn, false); oops(e); });
    };
    setTimeout(poll, 800);
  }).catch(function (e) { busy(btn, false); oops(e); });
}
/* "behind by 1.2 s" / "ahead by 300 s" - the reference's offset is the server's time minus this one's. */
function clockOff(ref) {
  if (ref === null || ref === undefined || isNaN(ref)) return null;
  var a = Math.abs(ref);
  var n = a >= 100 ? a.toFixed(0) + ' s' : a >= 1 ? a.toFixed(1) + ' s' : (a * 1000).toFixed(0) + ' ms';
  return {w: ref > 0 ? 'behind by' : 'ahead by', n: n, a: a};
}
/* Each kind of trouble, with what each node does and what it costs - from the choices. */
function clockScenarios() {
  var d = CLOCKC.draft, v = CLOCKC.view || {};
  var names = (v.nodes || []).map(function (n) { return n.name; });
  var two = names.length > 1;
  if (!two) names = [names[0] || 'this node', 'the other node'];
  var A = names[0], B = names[1];
  var watched = d.mode !== 'off', guard = d.mode === 'guard';
  var serve = {k: 'ok', w: 'answers'}, aside = {k: 'warn', w: 'steps aside'}, refuses = {k: 'crit', w: 'refuses right codes'},
      fixed = {k: 'ok', w: 'answers - codes corrected'}, nodir = {k: 'crit', w: 'refuses every password'};
  var safe = function (w) { return {k: 'ok', w: w}; }, risk = function (w) { return {k: 'warn', w: w}; },
      down = function (w) { return {k: 'crit', w: w}; };
  var rows = [];
  /* One node's clock 5 minutes off, the other right. */
  [[A, B], [B, A]].forEach(function (p) {
    var bad = p[0], good = p[1], cells = {};
    var does = d.clock_codes && watched ? fixed : (guard && two ? aside : refuses);
    cells[bad] = does; cells[good] = serve;
    var costs = [];
    if (does === refuses) costs.push('people sent to ' + bad + ' are refused');
    if (!d.clock_locks && does !== aside) costs.push('pauses there last minutes more or not at all');
    if (!d.clock_beat) costs.push(bad + '’s heartbeat looks dead or alive for ever');
    if (!watched) costs.push('nobody is told');
    rows.push({t: bad + '’s clock is 5 min off', cells: cells,
               out: does === refuses ? down('right codes refused on ' + bad) : safe(does === aside ? good + ' answers everything' : 'both answer'),
               risk: costs.length ? (does === refuses ? down(costs) : risk(costs)) : safe('none')});
  });
  /* Both clocks off alike (the time servers themselves wrong, or unreachable for long). */
  var both = d.clock_codes && watched ? fixed : refuses, cb = {};
  cb[A] = both; cb[B] = both;
  rows.push({t: 'Both clocks off alike', cells: cb,
             out: both === fixed ? safe('both answer') : down('right codes refused on both'),
             risk: both === fixed ? safe('none') : down(watched ? ['never stepped aside - the other is no better'] : ['nobody is told'])});
  /* The reference unreachable from a node. */
  var cr = {}; cr[A] = serve; cr[B] = serve;
  rows.push({t: 'The time servers cannot be reached from ' + A, cells: cr,
             out: safe('both answer'),
             risk: watched ? risk(['an alert; ' + A + ' is judged by nothing - never stepped aside']) : safe('none - not asked')});
  /* The directory. */
  var cd = {}; var dirAside = guard && d.health_dir && two;
  cd[A] = dirAside ? aside : nodir; cd[B] = serve;
  rows.push({t: A + ' cannot reach the directory, ' + B + ' can', cells: cd,
             out: dirAside ? safe(B + ' answers everything') : down('passwords refused on ' + A),
             risk: dirAside ? safe('none') : down(['until it is mended or ' + A + ' is taken out by hand'])});
  return {rows: rows, A: A, B: B, two: two};
}
/* Drawn again where it is: emptied for a moment, the pane was short and a switch
   clicked half-way down sent the page to the top. */
function drawClock() {
  var host_ = $('clock-guard'), held_ = host_ ? scrollHeld(host_) : null;
  var r_ = drawClockIn();
  if (held_) scrollBack(held_);
  return r_;
}
function drawClockIn() {
  var host = $('clock-guard');
  var v = CLOCKC.view, d = CLOCKC.draft;
  if (!host || !v || !d) return;
  var may = !!ADMIN;
  var warnS = Number((v.conf || {}).clock_warn_s) || 2, asideS = Number((v.conf || {}).clock_aside_s) || 20;
  var st = $('clock-state');
  var anyBad = (v.nodes || []).some(function (n) {
    var s = n.state || {};
    return n.fresh && (s.role === 'aside' || (s.ref !== null && s.ref !== undefined && Math.abs(s.ref) > warnS) || s.dir_ok === false);
  });
  if (st) {
    clear(st);
    if (!v.engaged) st.appendChild(el('span', 'tag dim', 'as until now - not watched'));
    else st.appendChild(el('span', 'tag ' + (anyBad ? 'crit' : 'ok'), anyBad ? 'not well' : 'all well'));
  }
  clear(host);
  /* ---- now ---- */
  var now = el('div', 'split-now');
  (v.nodes || []).forEach(function (n, i) {
    var s = n.state || {};
    var tile = el('div', 'split-node' + (s.role === 'aside' ? ' aside' : '') + (n.fresh || !v.engaged ? '' : ' stale'));
    var top = el('div', 'split-node-top');
    top.appendChild(noI18n(el('b', '', n.name)));
    if (n.me) top.appendChild(el('span', 'tag dim', 'this page'));
    var role = !v.engaged ? {k: 'dim', w: 'not watched'} : !n.fresh ? {k: 'dim', w: 'not heard from'} : (s.role === 'aside' ? {k: 'warn', w: 'stepped aside'} : {k: 'ok', w: 'answers'});
    top.appendChild(el('span', 'tag ' + role.k + ' split-role', role.w));
    tile.appendChild(top);
    var line = function (ok, words, more) {
      var r = el('div', 'split-line ' + (ok === true ? 'good' : ok === false ? 'bad' : 'muted'));
      r.innerHTML = iconMarkup(ok === true ? 'check' : ok === false ? 'close' : 'info', 14);
      r.appendChild(el('span', '', words));
      if (more) r.appendChild(noI18n(el('span', 'muted small', ' ' + more)));
      tile.appendChild(r);
    };
    if (!v.engaged) {
      tile.appendChild(el('div', 'muted small', 'nothing is measured - its clock is kept by chrony, as the tile above shows'));
    } else if (n.fresh) {
      var o = clockOff(s.ref);
      if (o) {
        var r = el('div', 'split-line ' + (o.a > asideS ? 'bad' : o.a > warnS ? 'warn' : 'good'));
        r.innerHTML = iconMarkup(o.a > warnS ? 'clock' : 'check', 14);
        r.appendChild(el('span', '', 'the reference: '));
        r.appendChild(el('span', '', o.a <= warnS ? 'right' : o.w));
        r.appendChild(noI18n(el('span', 'muted small', ' ' + (o.a <= warnS ? '(' + (s.ref > 0 ? '-' : '+') + o.n + ')' : o.n))));
        tile.appendChild(r);
      } else line(false, 'the reference cannot be asked', s.ref_err ? '- ' + s.ref_err : '');
      var k = clockOff(s.skew);
      if (k && s.skew_of) {
        var r2 = el('div', 'split-line ' + (k.a > warnS ? 'warn' : 'good'));
        r2.innerHTML = iconMarkup(k.a > warnS ? 'clock' : 'check', 14);
        r2.appendChild(noI18n(el('span', '', s.skew_of + ': ')));
        r2.appendChild(el('span', '', k.a <= warnS ? 'alike' : (s.skew > 0 ? 'ahead of this one by' : 'behind this one by')));
        r2.appendChild(noI18n(el('span', 'muted small', ' ' + k.n)));
        tile.appendChild(r2);
      } else if (s.skew_err) line(false, 'the other side’s clock cannot be read', '- ' + s.skew_err);
      else if (v.cluster) line(null, 'the other side’s clock: not measured yet');
      if ((v.conf || {}).health_dir) {
        if (s.dir_ok === true) line(true, 'reaches the directory');
        else if (s.dir_ok === false) line(false, 'cannot reach the directory', (s.dirs || []).filter(function (x) { return !x.ok; }).map(function (x) { return x.name + ' (' + x.words + ')'; }).join(', '));
        else line(null, 'no realm uses a directory');
      }
      if (s.codes_fixed) tile.appendChild(el('div', 'split-why small', 'codes worked out with the corrected time'));
      if (s.why) tile.appendChild(el('div', 'split-why muted small', s.why));
    } else {
      tile.appendChild(el('div', 'muted small', n.alive ? 'its word has not come over yet' : 'nothing heard from it - it is down, or the link is'));
    }
    now.appendChild(tile);
    if (i === 0 && (v.nodes || []).length > 1) {
      var sk = (s.skew !== null && s.skew !== undefined) ? Math.abs(s.skew) : null;
      var far = v.engaged && sk !== null && sk > warnS;
      var link = el('div', 'split-link ' + (far ? 'broken' : 'whole'));
      link.innerHTML = iconMarkup('clock', 18);
      link.appendChild(el('span', 'small', !v.engaged || sk === null ? 'not measured' : far ? 'apart' : 'alike'));
      now.appendChild(link);
    }
  });
  host.appendChild(now);
  /* ---- what is done ---- */
  host.appendChild(el('h4', 'split-h', 'What is done about the clocks'));
  var choices = el('div', 'split-choices');
  CLOCKC_MODES.forEach(function (m) {
    var b = el('button', 'split-choice' + (d.mode === m.k ? ' on' : ''));
    b.type = 'button';
    b.disabled = !may;
    var head = el('div', 'split-choice-head');
    var ic = el('span', 'split-ic'); ic.innerHTML = iconMarkup(m.icon, 20);
    head.appendChild(ic);
    head.appendChild(el('span', 'split-choice-k', m.t));
    if (m.k === 'off') head.appendChild(el('span', 'tag dim', 'as before'));
    b.appendChild(head);
    b.appendChild(el('div', 'split-choice-s', m.s));
    var ul = el('ul', 'split-pros');
    m.good.forEach(function (g) { ul.appendChild(el('li', 'good', g)); });
    m.bad.forEach(function (g) { ul.appendChild(el('li', 'bad', g)); });
    b.appendChild(ul);
    b.onclick = function () { d.mode = m.k; clockTouched(); };
    choices.appendChild(b);
  });
  host.appendChild(choices);
  var asBefore = d.mode === 'off';
  var said = el('p', 'split-said ' + (asBefore ? 'same' : 'new'));
  said.innerHTML = iconMarkup(asBefore ? 'check' : 'info', 15);
  said.appendChild(el('span', '', asBefore ? 'Exactly as before 1.0.222: nothing of this runs, whatever the switches below say.'
    : 'Each node asks the reference every 30 s and the other side’s clock every 5 s.'));
  host.appendChild(said);
  /* ---- its details ---- */
  var g = el('div', 'set-grid split-fields');
  var warn = textBox(String(d.warn), '2', '');
  warn.type = 'number'; warn.min = 1; warn.max = 60; warn.disabled = !may;
  warn.onchange = function () { d.warn = Math.max(1, Math.min(60, Number(warn.value) || 2)); clockTouched(); };
  var wf = formField('Warn when off by more than (seconds)', warn, 'An alert, and the codes corrected (with the switch below), past this. A code lives 30 s and one step either way is let in: past some 30 s right codes start to be refused.');
  if (d.warn !== Number((v.conf || {}).clock_warn_s || 2)) wf.classList.add('changed');
  g.appendChild(wf);
  var asd = textBox(String(d.aside), '20', '');
  asd.type = 'number'; asd.min = 5; asd.max = 600; asd.disabled = !may;
  asd.onchange = function () { d.aside = Math.max(5, Math.min(600, Number(asd.value) || 20)); clockTouched(); };
  var sf = formField('Step aside when off by more than (seconds)', asd, 'With Step aside when not well. More than the warning; 20 s leaves room before the first right code is refused.');
  if (d.aside !== Number((v.conf || {}).clock_aside_s || 20)) sf.classList.add('changed');
  if (d.aside <= d.warn) sf.classList.add('bad');
  g.appendChild(sf);
  host.appendChild(g);
  if (d.mode !== 'off') {
    var box = el('div', 'split-arb');
    box.appendChild(el('p', 'note', 'Each node’s reference: the time servers it asks itself, apart from its chrony, to tell how far off its clock is. Empty: the time servers above (for the whole cluster). Up to five, name or name:port; the middle of their answers is taken, so one gone wild does not count.'));
    var ag = el('div', 'set-grid');
    (v.nodes || []).forEach(function (n) {
      var t = textBox(d.ref[n.name] || '', (v.common || []).length ? 'the time servers above: ' + v.common.join(', ') : 'the time servers above', 'mono');
      t.disabled = !may;
      /* Typed into without the card drawn again (the cursor stays); drawn when left. */
      t.oninput = function () { d.ref[n.name] = t.value.trim(); CLOCKC.tried = null; clockTouched(true); };
      t.onchange = function () { drawClock(); };
      var f = formField('Reference of ' + n.name, t);
      if ((n.ref || '') !== (d.ref[n.name] || '')) f.classList.add('changed');
      ag.appendChild(f);
    });
    box.appendChild(ag);
    var row = el('div', 'btnrow');
    var tb = cmdButton('Try it from every node', 'pulse', '');
    tb.id = 'clock-try';
    tb.disabled = !may;
    tb.onclick = function () { clockTry(tb); };
    row.appendChild(tb);
    if (clockTried()) row.appendChild(el('span', 'tag ok', 'every node asks its reference'));
    else if (CLOCKC.tried && CLOCKC.tried.done) row.appendChild(el('span', 'tag crit', 'not every node can ask its reference'));
    else if (d.mode === 'guard' && (v.conf || {}).clock_mode !== 'guard') row.appendChild(el('span', 'small muted', 'needed before saving'));
    box.appendChild(row);
    if (CLOCKC.tried) {
      var res = el('div', 'split-tried');
      (CLOCKC.tried.nodes || []).forEach(function (n) {
        var got = CLOCKC.tried.got[n];
        var r = el('div', 'split-line ' + (!got ? 'muted' : got.ok === true ? 'good' : 'bad'));
        r.innerHTML = iconMarkup(!got ? 'clock' : got.ok === true ? 'check' : 'close', 14);
        r.appendChild(noI18n(el('b', '', n + ': ')));
        if (!got) r.appendChild(el('span', '', 'asking…'));
        else {
          (got.refs || []).forEach(function (x) {
            r.appendChild(noI18n(el('span', 'mono small', x.server + ' ')));
            var oo = clockOff(x.offset);
            if (oo) { r.appendChild(el('span', 'small', oo.w)); r.appendChild(noI18n(el('span', 'small', ' ' + oo.n + ' '))); }
            else r.appendChild(el('span', 'small', 'no answer'));
            if (x.words) r.appendChild(noI18n(el('span', 'small muted', ' (' + x.words + ') ')));
          });
          if (!(got.refs || []).length) r.appendChild(el('span', 'small', 'no time server given - give one, or set the time servers above'));
          var ko = clockOff(got.skew);
          if (ko && got.skew_of) {
            r.appendChild(el('span', 'split-sep', ' · '));
            r.appendChild(noI18n(el('span', 'small', got.skew_of + ': ')));
            r.appendChild(el('span', 'small', got.skew > 0 ? 'ahead of this one by' : 'behind this one by'));
            r.appendChild(noI18n(el('span', 'small', ' ' + ko.n)));
          }
          if (got.dir_ok === false) { r.appendChild(el('span', 'split-sep', ' · ')); r.appendChild(el('span', 'small', 'cannot reach the directory')); }
          else if (got.dir_ok === true) { r.appendChild(el('span', 'split-sep', ' · ')); r.appendChild(el('span', 'small', 'reaches the directory')); }
        }
        res.appendChild(r);
      });
      box.appendChild(res);
    }
    host.appendChild(box);
  }
  /* ---- and what else ---- */
  host.appendChild(el('h4', 'split-h', 'And with the clock measured'));
  var opts = el('div', 'split-opts');
  CLOCKC_OPTS.forEach(function (o) {
    var item = el('div', 'split-opt' + (d[o.k] ? ' on' : ''));
    var sw = switchBox(d[o.k]);
    sw._input.disabled = !may;
    sw._input.onchange = function () { d[o.k] = !!sw._get(); clockTouched(); };
    var ic = el('span', 'split-ic'); ic.innerHTML = iconMarkup(o.icon, 18);
    var txt = el('div', 'split-opt-txt');
    txt.appendChild(el('div', 'split-opt-k', o.t));
    txt.appendChild(el('div', 'split-opt-s', o.s));
    item.appendChild(ic); item.appendChild(txt); item.appendChild(sw);
    if (!!Number((v.conf || {})[o.k] || 0) !== d[o.k]) item.classList.add('changed');
    opts.appendChild(item);
  });
  host.appendChild(opts);
  /* ---- what happens ---- */
  var sc = clockScenarios();
  host.appendChild(el('h4', 'split-h', 'What happens - with the choices above'));
  host.appendChild(listTable(['When', sc.A, sc.B, 'Sign-ins', 'What it costs'], sc.rows, function (r) {
    var tr = el('tr');
    tr.appendChild(el('td', 'split-when', r.t));
    [sc.A, sc.B].forEach(function (n) {
      var c = r.cells[n] || {k: 'dim', w: '-'};
      var td = el('td');
      td.appendChild(el('span', 'tag ' + c.k, c.w));
      tr.appendChild(td);
    });
    [r.out, r.risk].forEach(function (x) {
      var td = el('td');
      var box = el('span', 'split-out ' + x.k);
      [].concat(x.w).forEach(function (w, i) {
        if (i) box.appendChild(el('span', 'split-sep', '; '));
        box.appendChild(el('span', '', w));
      });
      td.appendChild(box);
      tr.appendChild(td);
    });
    return tr;
  }, 'plain split-scen'));
  if (!sc.two) host.appendChild(el('p', 'note', 'One node: nothing can step aside - there is no other node to answer. Measure and warn, and the corrected codes, work alone.'));
  dressButtons(host);
}


```

### 12.4 The texts in Czech

`i18n/cs_233.py` - every text of the card, the alerts' own are in Czech in the code (`_al`).

| English | Czech |
|---------|-------|
| The clocks of the nodes | Hodiny uzlů |
| A node whose clock is off refuses codes that are right - and answers, so the VPN does not ask the other node. Its heartbeat, its pauses and lockouts are off with it; a node that cannot reach the directory refuses every password the same way. Here each node measures itself against the time servers and the other node, and what is done about it is chosen. | Uzel, jehož hodiny jdou špatně, odmítá správné kódy – a přitom odpovídá, takže se VPN druhého uzlu nezeptá. Jeho heartbeat, pauzy i zámky jsou posunuté s ním; uzel, který nedosáhne na adresář, stejně tak odmítá každé heslo. Tady se každý uzel měří proti časovým serverům a proti druhému uzlu a volí se, co se s tím udělá. |
| As until now: nothing is watched | Jako dosud: nic se nesleduje |
| Each node keeps its clock with chrony, as the tiles above show; nothing of this card runs - no question to a time server, no measuring, nothing written: exactly as before. | Každý uzel si hodiny drží chronyd, jak ukazují dlaždice výše; nic z této karty neběží – žádný dotaz na časový server, žádné měření, nic se nezapisuje: přesně jako dřív. |
| Nothing new runs | Nic nového neběží |
| A node whose clock is off refuses right codes - and says nothing of why | Uzel se špatnými hodinami odmítá správné kódy – a neřekne proč |
| A heartbeat of a node with a wrong clock looks dead, or alive for ever | Heartbeat uzlu se špatnými hodinami vypadá mrtvý, nebo věčně živý |
| Measure and warn | Měřit a varovat |
| Each node asks the reference time servers itself (SNTP, every 30 s) and measures the other node’s clock through its database. Shown here, and an alert when off - nothing else changes unless a switch below says so. | Každý uzel se sám ptá referenčních časových serverů (SNTP, každých 30 s) a měří hodiny druhého uzlu přes jeho databázi. Ukáže se to tady a při odchylce přijde upozornění – nic jiného se nemění, pokud to neřekne přepínač níže. |
| You learn of a clock going wrong before people do | O rozjetých hodinách se dozvíte dřív než uživatelé |
| Each node measured on its own, not by its chrony’s word | Každý uzel změřen sám, ne podle slova svého chronyd |
| A node whose clock is off still answers - and refuses right codes | Uzel se špatnými hodinami dál odpovídá – a odmítá správné kódy |
| Step aside when not well | Ustoupit stranou, když není v pořádku |
| As Measure and warn, and a node whose clock is off by more than the limit steps aside: RADIUS is answered by the other node, the VIP address goes to it - only while the other node is well, never both. | Jako Měřit a varovat, a navíc uzel, jehož hodiny jdou víc než o limit, ustoupí stranou: RADIUS obslouží druhý uzel, VIP adresa přejde na něj – jen dokud je druhý uzel v pořádku, nikdy oba. |
| A node with a broken clock stops refusing right codes - the other answers | Uzel s rozbitými hodinami přestane odmítat správné kódy – obsluhuje druhý |
| Heals by itself when the clock is right again | Sám se vrátí, když hodiny zase jdou správně |
| With one node only, or the other not well, nothing steps aside | S jediným uzlem, nebo když druhý není v pořádku, nikdo neustoupí |
| Codes by the corrected time | Kódy podle opraveného času |
| The code from the app is checked against the reference’s time (this clock plus its measured offset), not this machine’s clock - right codes keep working on a node whose clock is off. With it, guard does not step a node aside for its clock. | Kód z aplikace se ověřuje podle času reference (tyto hodiny plus jejich změřená odchylka), ne podle hodin tohoto stroje – správné kódy fungují dál i na uzlu se špatnými hodinami. S tímto přepínačem hlídání kvůli hodinám uzel stranou neodsune. |
| Heartbeats by the measured difference | Heartbeaty podle změřeného rozdílu |
| The other node’s heartbeat is judged with the difference of the two clocks measured here: a node 10 min behind no longer looks dead, one ahead no longer looks alive for ever. | Heartbeat druhého uzlu se posuzuje se zde změřeným rozdílem obou hodin: uzel o 10 min pozadu už nevypadá mrtvý a uzel napřed už nevypadá věčně živý. |
| Pauses and lockouts by the corrected time | Pauzy a zámky podle opraveného času |
| The pause after wrong codes and the lockout are timed by the corrected time: on a node whose clock is off they last as long as on the other, not minutes more or nothing at all. | Pauza po špatných kódech a zámek se měří opraveným časem: na uzlu se špatnými hodinami trvají stejně dlouho jako na druhém, ne o minuty déle nebo vůbec. |
| Step aside when the directory cannot be reached | Ustoupit stranou, když není dosažitelný adresář |
| With Step aside when not well: a node that cannot reach the directory its realms sign in against (checked every 15 s) steps aside while the other node reaches it - rather than refusing every password. | S volbou Ustoupit stranou: uzel, který nedosáhne na adresář, proti kterému se jeho realmy přihlašují (kontrola každých 15 s), ustoupí stranou, dokud na něj druhý uzel dosáhne – místo aby odmítal každé heslo. |
| Stepping aside comes after the warning: more seconds than it | Ustoupení přichází až po varování: víc sekund než ono |
| Try the reference from every node first: a node that cannot ask it is never stepped aside, and you would not know it is unguarded | Nejdřív vyzkoušejte referenci ze všech uzlů: uzel, který se jí nemůže zeptat, nikdy neustoupí – a nevěděli byste, že není hlídaný |
| behind by | pozadu o |
| ahead by | napřed o |
| answers - codes corrected | obsluhuje – kódy opraveny |
| refuses right codes | odmítá správné kódy |
| refuses every password | odmítá každé heslo |
| nobody is told | nikdo se to nedozví |
| both answer | oba obsluhují |
| none | žádné |
| Both clocks off alike | Oboje hodiny jdou stejně špatně |
| right codes refused on both | správné kódy odmítnuty na obou |
| never stepped aside - the other is no better | nikdo neustoupí – druhý není o nic lepší |
| none - not asked | žádné – neptá se |
| all well | vše v pořádku |
| not well | není v pořádku |
| nothing is measured - its clock is kept by chrony, as the tile above shows | nic se neměří – hodiny drží chronyd, jak ukazuje dlaždice výše |
| the reference:  | reference:  |
| right | správně |
| the reference cannot be asked | reference se nedá zeptat |
| alike | stejně |
| ahead of this one by | napřed před tímto o |
| behind this one by | pozadu za tímto o |
| the other side’s clock cannot be read | hodiny druhé strany nejdou přečíst |
| the other side’s clock: not measured yet | hodiny druhé strany: zatím nezměřeny |
| reaches the directory | dosáhne na adresář |
| cannot reach the directory | nedosáhne na adresář |
| no realm uses a directory | žádný realm nepoužívá adresář |
| codes worked out with the corrected time | kódy se počítají z opraveného času |
| not measured | neměřeno |
| What is done about the clocks | Co se s hodinami dělá |
| Exactly as before 1.0.222: nothing of this runs, whatever the switches below say. | Přesně jako před 1.0.222: nic z toho neběží, ať přepínače níže říkají cokoli. |
| Each node asks the reference every 30 s and the other side’s clock every 5 s. | Každý uzel se ptá reference každých 30 s a hodin druhé strany každých 5 s. |
| Warn when off by more than (seconds) | Varovat při odchylce větší než (sekundy) |
| An alert, and the codes corrected (with the switch below), past this. A code lives 30 s and one step either way is let in: past some 30 s right codes start to be refused. | Nad tuto hodnotu přijde upozornění a kódy se opraví (s přepínačem níže). Kód platí 30 s a projde i o krok vedle: zhruba nad 30 s se začnou odmítat správné kódy. |
| Step aside when off by more than (seconds) | Ustoupit stranou při odchylce větší než (sekundy) |
| With Step aside when not well. More than the warning; 20 s leaves room before the first right code is refused. | S volbou Ustoupit stranou. Víc než varování; 20 s nechává rezervu, než se odmítne první správný kód. |
| Each node’s reference: the time servers it asks itself, apart from its chrony, to tell how far off its clock is. Empty: the time servers above (for the whole cluster). Up to five, name or name:port; the middle of their answers is taken, so one gone wild does not count. | Reference každého uzlu: časové servery, kterých se sám ptá mimo svůj chronyd, aby zjistil, o kolik jdou jeho hodiny. Prázdné: časové servery výše (pro celý cluster). Nejvýš pět, jméno nebo jméno:port; bere se prostřední z odpovědí, takže jeden ujetý se nepočítá. |
| the time servers above | časové servery výše |
| every node asks its reference | každý uzel se ptá své reference |
| not every node can ask its reference | ne každý uzel se může zeptat své reference |
| no time server given - give one, or set the time servers above | není zadán časový server – zadejte ho, nebo nastavte časové servery výše |
| And with the clock measured | A se změřenými hodinami |
| One node: nothing can step aside - there is no other node to answer. Measure and warn, and the corrected codes, work alone. | Jeden uzel: nikdo nemůže ustoupit – není druhý uzel, který by obsluhoval. Měřit a varovat i opravené kódy fungují i samostatně. |
| Warn when off by more than | Varovat při odchylce větší než |
| Step aside when off by more than | Ustoupit stranou při odchylce větší než |
| Reference time servers | Referenční časové servery |
| this node | tento uzel |
| the other node | druhý uzel |

Patterns (`{0}` stands for a node's name or a number):

| English | Czech |
|---------|-------|
| {0} digits, a new one every {1} s, {2} | {0} číslic, nový každých {1} s, {2} |
| people sent to {0} are refused | lidé poslaní na {0} jsou odmítnuti |
| pauses there last minutes more or not at all | pauzy tam trvají o minuty déle nebo vůbec |
| {0}’s heartbeat looks dead or alive for ever | heartbeat {0} vypadá mrtvý nebo věčně živý |
| {0}’s clock is 5 min off | hodiny {0} jdou o 5 min špatně |
| right codes refused on {0} | správné kódy odmítnuty na {0} |
| The time servers cannot be reached from {0} | Časové servery nejsou z {0} dosažitelné |
| an alert; {0} is judged by nothing - never stepped aside | upozornění; {0} se nemá podle čeho posoudit – nikdy neustoupí |
| {0} cannot reach the directory, {1} can | {0} nedosáhne na adresář, {1} ano |
| passwords refused on {0} | hesla odmítnuta na {0} |
| until it is mended or {0} is taken out by hand | dokud se to neopraví nebo se {0} nevyřadí ručně |
| Reference of {0} | Reference uzlu {0} |
| the time servers above: {0} | časové servery výše: {0} |
| stepped aside: {0} | ustoupil stranou: {0} |

### 12.5 The page's helpers it uses

| Helper | What it is |
|--------|------------|
| `$(id)` | `document.getElementById` |
| `el(tag, cls, text)` | an element with a class and text |
| `clear(node)` | removes the children |
| `iconMarkup(name, size)` | an inline SVG of the page's icon set: `clock`, `eye`, `shield`, `key`, `pulse`, `lock`, `people`, `check`, `close`, `info` |
| `noI18n(node)` | marks a node not to be translated (names, numbers) |
| `api(name, body)` | GET (no body) or POST through the page's relay; a promise of the JSON |
| `toast(words, kind)`, `oops(error)` | messages |
| `busy(button, on)` | a button's spinner |
| `textBox(value, placeholder, cls)`, `formField(label, input, help)`, `switchBox(on)` (with `_input`, `_get()`), `cmdButton(words, icon, cls)` | form pieces |
| `listTable(heads, rows, drawRow, cls)` | a table |
| `pendingSet(key, {pane, save, reset})`, `PENDING`, `markDirtyCount()` | the save bar |
| `liveWorkedIn(host)` | whether somebody is in a field inside |
| `scrollHeld(host)` / `scrollBack(held)` | the scroll kept over a redraw |
| `dressButtons(host)` | the page's button styles |
| `ADMIN` | the signed-in person is a full administrator |

## 13. Tests

**In one process** (`tests/clock/t_clock.py`, SQLite, 70 checks; a fake SNTP server,
`tests/clock/fakentp.py`, answers with this machine's time plus an offset of its own):

- SNTP: a server with the right time (offset ~0, delay small); one 300 s ahead (offset +300);
  one unsynchronised (stratum 0, refused); one silent (no offset, within the time); the median
  of three with one gone wild;
- the reference servers: the node's own first, else the time servers of Settings → Time;
- the decision: every row of the table of 5;
- "as until now": the default; nothing asked (the SNTP function patched), no row, no thread;
  `clock_now` is `time.time()`; heartbeats as before; no alert;
- watch: measured (300 s behind), row written, serves, the alert "bad", codes not corrected;
- `clock_codes`: the right code by the right time is refused on a node 300 s behind without it,
  let in with it; the state and the alert say so; the code of the machine's own wrong time is
  refused; no correction within `clock_warn_s`; none from a reference not fresh;
- `clock_locks`: the locks' time corrected;
- `clock_beat`: a node 10 min behind looks dead without it, alive with it; a node 10 min ahead
  "lives for ever" without it; a 100 s old beat from a node ahead is dead with it; one shared
  database server - the difference from both rows;
- guard: aside with the other well, `maintenance_now()` says it (`clock: true`), alert, event;
  the other gone quiet - serves at once; clock mended - serves; with `clock_codes` never aside;
  the peer's row freshness by the measured skew (a row "300 s old" from a node 300 s behind is
  fresh);
- the directory: no realm uses it (None); reached; not reached; guard + `health_dir` aside and
  back; the alert;
- switched off while aside: serves at once;
- the API: the view; guard without try refused (409); aside before warn refused; a bad server
  refused; a node that is not refused; save of mode, switch, number and a node's reference; an
  unknown action refused; back to off.

**The card in a browser** (`tests/clock/ui_clock.js`, Playwright through the real page and its
relay): the card shows its tiles and choices; a mode click marks the save bar; guard without a try
is refused by the save; the try fills each node's line; saved through the bar; a real mouse click
on a switch half-way down keeps the page where it is (no jump); the table's columns stay put
whatever is chosen; the Czech page has no English left on the card.

**On the two-node sandbox** (`tests/hasb/full/t_ha_clock.py`): each node's reference is a fake
SNTP server of its own (the two machines share one clock, so a node's "wrong clock" is played by
its reference saying another time):

- off: nothing in either state row;
- watch: both measured, the skew between them ~0, no alert;
- node b's reference 300 s ahead (b "behind"): the alert on b; guard - b steps aside (RADIUS
  silent there, a answers, the VIP check fails on b); its reference right again - b serves;
- both references 300 s off: neither steps aside;
- `clock_codes` on with b's reference 300 s ahead: b serves and lets in the code of the
  reference's time;
- left as found: settings back, replication running.

## 14. Porting it to another application - checklist

For an application with the same kind of cluster (two nodes, each its own database replicating
both ways or one shared database server, a shared settings store, an admin page with a save bar):

- [ ] **Settings** of 2.3 and 3, with their ranges; `clock_ref` per node; the generic settings
      list skips them.
- [ ] **SNTP client** of 4.1, with the originate check, the stratum check and the median of up
      to five servers. No subprocess, no library. Test it against a fake server (13).
- [ ] **The other node's clock** (4.2) through the database it already reaches, in a helper
      thread with a hard join timeout; the best of three round trips.
- [ ] **The directory** (4.3): TCP connect only, every server of every directory a realm uses.
- [ ] **The watch**: a thread started from the daemon's loop only when the mode is not `off`;
      every 5 s; the reference every 30 s; the directory every 15 s; the state row every 10 s.
- [ ] **The decision** (5) as a pure function - test every row of its table.
- [ ] **Stepping aside** through the one gate the application has for maintenance; flush its
      cache on every change of role; an event on each.
- [ ] **`clock_now('codes')`** in every place a TOTP step is worked out (7) - search for every
      call of the TOTP function, the administrators' second factor and any SSH gate included.
- [ ] **`clock_now('locks')`** where the pauses and lockouts take their `t` (9).
- [ ] **Heartbeat age** through `clock_beat_age` (8).
- [ ] **Alerts** of 10.
- [ ] **API** of 11; the try made by every node for itself.
- [ ] **The page's relay** passes `clock` on (reads and writes).
- [ ] **The card** of 12: HTML, CSS, JS as they are; the helpers of 12.5 mapped to the
      application's own; the texts of 12.4 into its translation files.
- [ ] **"As until now"** really runs nothing - a test that patches the SNTP function and checks
      it was never called, no row written, no thread.
- [ ] **Tests** of 13; on the cluster, a node's wrong clock played by its reference servers
      (the two test machines share one clock).

## 15. For the administrator

**Which to choose**

- *As until now* (the default) - nothing of this runs. The Time pane above the card still shows
  what chrony says.
- *Measure and warn* - the gentlest step, and the right one for a single node: you learn of a
  clock going wrong (and of the two nodes drifting apart) before people do. Add *Codes by the
  corrected time* to keep codes working on a node whose clock is off: the usual choice for a
  single node, since nothing can step aside there.
- *Step aside when not well* - for a pair: a node whose clock goes wrong stops answering and the
  other takes everything until it is mended. Add *Step aside when the directory cannot be
  reached* when the two nodes reach the directory by different ways (two data centres, two
  firewalls).
- *Heartbeats by the measured difference* and *Pauses and lockouts by the corrected time* are
  safe to switch on with either mode: they change nothing while the clocks are right.

**Before choosing guard**: *Try it from every node*. Each node must reach its reference servers
(UDP 123 out). A network that blocks NTP to the internet: give each node an NTP server inside
(the domain controllers usually are one), as *Reference of <node>*.

**When the card says a node is off**

1. Look at the tile: *the reference: behind by 312 s* - the clock is 312 s slow.
2. Look at chrony's tile above it on the same pane: is it synchronised? which sources?
3. Usual causes: UDP 123 blocked; the virtualisation host's time sync overriding chrony (switch
   off "synchronise guest time with host" in VMware Tools / Hyper-V integration services); a
   clock set by hand.
4. `chronyc makestep` on the node puts the clock right at once; the card says *right* within
   30 s, a node that stepped aside answers again by itself.

**What it does not do**: put the clock right itself (that is chrony's job - the correction is
only applied to the codes and locks, the machine's clock is not touched); judge a node whose
reference cannot be asked (it is never stepped aside for that, only warned of); help when both
nodes' clocks are equally wrong and the codes are not corrected (neither is better than the
other).

## 16. Appendix: the code as it is

`parts/87z_clock.py` - the measuring, the decision, the watch, the state, the try:

```python
# ---- the clocks and the health of the nodes (1.0.222) ------------------------------------
# Codes from the app are worked out from the clock: a node whose clock is off refuses every
# right code - an answer, so the VPN does not ask the other node - and its heartbeat, its
# lockouts and its "newer wins" stamps are off with it. A node that cannot reach the
# directory refuses every password the same way. Chosen on Settings -> Time -> The clocks of
# the nodes (docs/clock-guard.md says all of it):
#
#   clock_mode     off    as until now: nothing of this runs
#                  watch  each node measures its clock against a reference (SNTP to the time
#                         servers of Settings -> Time, or its own) and against the other node
#                         (its database server's clock), says it on the card, warns
#                  guard  and a node whose clock is off (or that cannot reach the directory,
#                         with health_dir) steps aside - only while the other node is well
#   clock_warn_s   off by more than this: a warning
#   clock_aside_s  off by more than this: guard steps the node aside
#   clock_ref      each node's own reference servers (empty: the time servers of Settings -> Time)
#   clock_codes    codes worked out from the corrected time (the clock + its measured offset)
#   clock_beat     the other node's heartbeat judged with the measured difference of the clocks
#   clock_locks    pauses and lockouts on the corrected time
#   health_dir     guard: step aside when this node cannot reach the directory and the other can
CLOCK_MODES = ('off', 'watch', 'guard')
CLOCK_LOCK = threading.Lock()
CLOCK = {'thread': None, 'ref': None, 'ref_src': '', 'ref_err': '', 'ref_at': 0.0, 'refs': [],
         'skew': None, 'skew_err': '', 'skew_at': 0.0, 'skew_of': '', 'dir_ok': None, 'dir_err': '',
         'dir_at': 0.0, 'dirs': [], 'role': 'serve', 'why': '', 'written': 0.0}
CLOCK_STEP_S = 5.0
CLOCK_REF_EVERY_S = 30.0
CLOCK_DIR_EVERY_S = 15.0
CLOCK_FRESH_S = 120.0


def clock_mode():
    m = str(CONFIG.get('clock_mode') or 'off')
    return m if m in CLOCK_MODES else 'off'


def clock_engaged():
    """Anything of it at all. "As until now" (off) runs nothing: exactly as before 1.0.222."""
    return clock_mode() != 'off'


# ---- the reference: SNTP (RFC 4330), one question each -----------------------------------------
NTP_EPOCH = 2208988800


def sntp_offset(server, timeout=1.5):
    """(offset, delay) of one server: offset > 0 when this machine's clock is behind it.
    Raises OSError / ValueError."""
    got = split_targets_parse(server)
    if len(got) != 1:
        raise ValueError('one server: a name or address, name:port')
    host, port = got[0][0], got[0][1] or 123
    infos = socket.getaddrinfo(host, port, 0, socket.SOCK_DGRAM)
    fam, addr = infos[0][0], infos[0][4]
    s = socket.socket(fam, socket.SOCK_DGRAM)
    try:
        s.settimeout(timeout)
        pkt = bytearray(48)
        pkt[0] = 0x23                                   # LI 0, version 4, mode 3 (client)
        t0 = time.time()
        sec = int(t0) + NTP_EPOCH
        frac = int((t0 - int(t0)) * (1 << 32))
        pkt[40:48] = struct.pack('!II', sec, frac)      # our transmit time, echoed back
        s.sendto(bytes(pkt), addr)
        while True:
            data, _a = s.recvfrom(512)
            t3 = time.time()
            if len(data) >= 48 and data[24:32] == bytes(pkt[40:48]):
                break
        mode, stratum = data[0] & 7, data[1]
        if mode not in (4, 5) or stratum == 0 or stratum > 15:
            raise ValueError('the server is not synchronised itself (stratum %d)' % stratum)

        def ts(off):
            a, b = struct.unpack('!II', data[off:off + 8])
            return a - NTP_EPOCH + b / float(1 << 32)
        t1, t2 = ts(32), ts(40)
        return ((t1 - t0) + (t2 - t3)) / 2.0, (t3 - t0) - (t2 - t1)
    finally:
        s.close()


def clock_ref_servers(value=None, store=None):
    """This node's reference servers: its own (clock_ref), else the time servers of Settings ->
    Time."""
    given = CONFIG.get('clock_ref') if value is None else value
    out = [w for w in re.split(r'[\s,;]+', str(given or '').strip()) if w]
    if not out and store is not None:
        try:
            out = [str(x.get('host') if isinstance(x, dict) else x) for x in
                   (ntp_conf(store).get('servers') or [])]
        except Exception:                               # noqa: BLE001
            out = []
    return [x for x in out if x][:5]


def clock_ref_check(servers):
    """[(server, offset or None, words)], and the median offset of those that answered (or None)."""
    got = []
    for srv in servers:
        try:
            off, delay = sntp_offset(srv)
            got.append((srv, off, 'delay %.0f ms' % (delay * 1000)))
        except (OSError, ValueError, struct.error, UnicodeError) as e:
            got.append((srv, None, str(e)[:160] or 'no answer'))
    offs = sorted(o for _s, o, _w in got if o is not None)
    if not offs:
        return got, None
    mid = len(offs) // 2
    return got, (offs[mid] if len(offs) % 2 else (offs[mid - 1] + offs[mid]) / 2.0)


# ---- the other node: its database server's clock ---------------------------------------------
def clock_peer_skew(store):
    """(name, skew) - the other side's clock minus this one's, from its database server: the
    other node's own PostgreSQL in a replicated pair (on that machine, so its clock), the shared
    database server otherwise ('the database server'). (None, None) when there is no other side
    to ask. Asked in a thread of its own, 3.5 s at most. Raises RuntimeError."""
    if CONFIG.get('ha_mode') == 'replicated' and CONFIG.get('ha_peer'):
        conf = ha_peer_conf(timeout=2)
        name = next((n['name'] for n in ha_nodes(store) if not n.get('me')), 'the other node')
    elif store.db.engine in ('postgres', 'mariadb') and in_cluster(store):
        conf = {k: CONFIG.get(k) for k in DB_KEYS}
        name = CLOCK_DB_SERVER
    else:
        return None, None
    got = {}

    def ask():
        db = None
        try:
            db = db_open(conf, statement_s=2)
            sql = ("SELECT extract(epoch from clock_timestamp())" if db.engine == 'postgres'
                   else "SELECT UNIX_TIMESTAMP(NOW(6))")
            db.value('SELECT 1')                        # connected before the clock is read
            best = None
            for _ in range(3):                          # the shortest of three round trips
                t0 = time.time()
                there = float(db.value(RawSql(sql)))
                t1 = time.time()
                if best is None or t1 - t0 < best[0]:
                    best = (t1 - t0, there - (t0 + t1) / 2.0)
            got['skew'] = best[1]
        except Exception as e:                          # noqa: BLE001
            got['e'] = str(e).split('\n')[0][:160] or 'no answer'
        finally:
            try:
                if db is not None:
                    db.close()
            except Exception:                           # noqa: BLE001
                pass
    t = threading.Thread(target=ask, name='otp-clock-peer', daemon=True)
    t.start()
    t.join(3.5)
    if 'skew' in got:
        return name, got['skew']
    raise RuntimeError(got.get('e') or 'no answer within 3.5 s')


CLOCK_DB_SERVER = 'the database server'


# ---- the directory -----------------------------------------------------------------------------
def clock_dir_check(store):
    """(True | False | None, [(directory, reached, words)]): every directory a realm signs in
    against, reached on one of its servers. None: no realm uses one."""
    used = set()
    try:
        for r in store.realms():
            if r.get('directory'):                      # its passwords, its groups
                used.add(str(r['directory']).lower())
    except Exception:                                   # noqa: BLE001
        return None, []
    out = []
    for d in store.directories():
        if str(d.get('name') or '').lower() not in used or not d.get('enabled', 1):
            continue
        port_d = int(d.get('port') or (636 if str(d.get('tls') or '') == 'ldaps' else 389))
        hosts = [h for h in re.split(r'[\s,;]+', str(d.get('hosts') or '')) if h]
        reached, words = False, 'no server given'
        for h in hosts[:6]:
            host, port = h, port_d
            if h.count(':') == 1:
                host, p = h.rsplit(':', 1)
                port = int(p) if p.isdigit() else port_d
            try:
                with socket.create_connection((host.strip('[]'), port), timeout=2):
                    reached, words = True, '%s:%d' % (host, port)
                    break
            except OSError as e:
                words = '%s:%d %s' % (host, port, str(e)[:80])
        out.append((d['name'], reached, words))
    if not out:
        return None, out
    return all(x[1] for x in out), out


# ---- the decision ----------------------------------------------------------------------------
def clock_decide(mode, ref, aside_s, codes_fixed, dir_ok, health_dir, peer):
    """('serve' | 'aside', why). `peer`: the other node's state row as known here (None when
    not heard from) - a node steps aside only for one that is well: fresh, serving, its clock
    within aside_s of the reference, and (for the directory) reaching it."""
    if mode != 'guard':
        return 'serve', ''
    peer_well = bool(peer) and peer.get('fresh') and peer.get('role') == 'serve' and \
        not peer.get('maintenance')
    clock_bad = ref is not None and abs(ref) > aside_s and not codes_fixed
    if clock_bad:
        pr = (peer or {}).get('ref')
        if peer_well and pr is not None and abs(pr) <= aside_s:
            return 'aside', 'this node\'s clock is %+.1f s off the time servers - the other node answers' % (-ref)
        return 'serve', 'this node\'s clock is off, but the other node cannot take over - it answers'
    if health_dir and dir_ok is False:
        if peer_well and (peer or {}).get('dir_ok') is True:
            return 'aside', 'this node cannot reach the directory - the other node answers'
        return 'serve', 'the directory cannot be reached, but neither can the other node take over'
    return 'serve', ''


def clock_aside():
    return clock_engaged() and CLOCK['role'] == 'aside'


def clock_correction():
    """Seconds to add to this machine's clock, by the reference - 0 when not known, not fresh,
    or within clock_warn_s."""
    ref = CLOCK['ref']
    if ref is None or time.time() - CLOCK['ref_at'] > CLOCK_FRESH_S * 2:
        return 0.0
    if abs(ref) <= float(CONFIG.get('clock_warn_s') or 2):
        return 0.0
    return ref


def clock_now(kind='codes'):
    """The time codes (kind 'codes') or pauses and lockouts (kind 'locks') are worked out
    with: the machine's clock, corrected by the reference with clock_codes / clock_locks."""
    t = time.time()
    if not clock_engaged():
        return t
    if (kind == 'codes' and CONFIG.get('clock_codes')) or (kind == 'locks' and CONFIG.get('clock_locks')):
        return t + clock_correction()
    return t


def clock_skew_of(store, name):
    """The other node's clock minus this one's, as measured here (or as this node's own row
    says, from a process that does not watch): None when not known. With one shared database
    server both nodes measure against it: the other's minus this one's is the difference of
    the two."""
    def mine():
        if CLOCK['skew'] is not None and time.time() - CLOCK['skew_at'] < CLOCK_FRESH_S:
            return CLOCK['skew_of'], CLOCK['skew']
        row = _meta_json(store, 'clock:state:' + node_name()) or {}
        if row.get('skew') is not None and time.time() - float(row.get('at') or 0) < CLOCK_FRESH_S:
            return row.get('skew_of'), float(row['skew'])
        return None, None
    of, sk = mine()
    if sk is None:
        return None
    if of == name:
        return sk
    if of == CLOCK_DB_SERVER:
        row = _meta_json(store, 'clock:state:' + name) or {}
        if row.get('skew_of') == CLOCK_DB_SERVER and row.get('skew') is not None:
            return sk - float(row['skew'])
    return None


def clock_beat_age(store, name, at, now):
    """A heartbeat's age with clock_beat: judged by the measured difference of the clocks, not
    by the sender's clock alone - a node 10 min behind looked dead, one ahead lived for ever."""
    if not (clock_engaged() and CONFIG.get('clock_beat')) or name == node_name():
        return now - at
    sk = clock_skew_of(store, name)
    return now - at if sk is None else now - (at - sk)


# ---- the watch -------------------------------------------------------------------------------
def clock_tick(daemon):
    with CLOCK_LOCK:
        t = CLOCK['thread']
        if t is not None and t.is_alive():
            return
        t = threading.Thread(target=_clock_loop, args=(daemon,), name='otp-clock', daemon=True)
        CLOCK['thread'] = t
    t.start()


def _clock_loop(daemon):
    while True:
        try:
            clock_step(daemon.store)
        except Exception as e:                          # noqa: BLE001
            log_sparing('clock', 'watching the clocks: %s' % e, 'warn', every=600)
        time.sleep(CLOCK_STEP_S)


def clock_watching():
    t = CLOCK['thread']
    return t is not None and t.is_alive()


def clock_peer_row(store, now=None):
    """The other node's row, with 'fresh' worked out by the measured difference of the clocks."""
    now = time.time() if now is None else now
    for n in ha_nodes(store):
        if n.get('me'):
            continue
        row = _meta_json(store, 'clock:state:' + n['name']) or {}
        if not row:
            return None
        sk = clock_skew_of(store, n['name'])
        at = float(row.get('at') or 0) - (sk or 0.0)
        row['fresh'] = now - at < 60
        row['maintenance'] = bool(n.get('maintenance'))
        return row
    return None


def clock_step(store, now=None, ref=None, skew=None, dir_ok=None, peer=None):
    """One look. `ref`, `skew`, `dir_ok`, `peer` given only by the tests."""
    now = time.time() if now is None else now
    if not clock_engaged():
        if CLOCK['role'] != 'serve':
            CLOCK.update(role='serve', why='')
            MAINT_CACHE['at'] = 0
        return
    if ref is not None:
        CLOCK.update(ref=None if ref == 'none' else ref, ref_at=now, ref_src='test', ref_err='')
    elif now - CLOCK['ref_at'] > CLOCK_REF_EVERY_S:
        servers = clock_ref_servers(store=store)
        got, med = clock_ref_check(servers) if servers else ([], None)
        CLOCK.update(refs=got, ref=med, ref_at=now, ref_src=', '.join(servers),
                     ref_err='' if med is not None else (
                         'no time server given (Settings -> Time, or this node\'s own)' if not servers
                         else 'no time server answered'))
    if skew is not None:
        of, val = skew if isinstance(skew, tuple) else ('test-peer', skew)
        CLOCK.update(skew=None if val == 'none' else val, skew_at=now, skew_of=of, skew_err='')
    else:
        try:
            name, sk = clock_peer_skew(store)
            if name is not None:
                CLOCK.update(skew=sk, skew_at=now, skew_of=name, skew_err='')
        except Exception as e:                          # noqa: BLE001
            CLOCK.update(skew_err=str(e).split('\n')[0][:160])
    if dir_ok is not None:
        CLOCK.update(dir_ok=None if dir_ok == 'none' else dir_ok, dir_at=now)
    elif CONFIG.get('health_dir') and now - CLOCK['dir_at'] > CLOCK_DIR_EVERY_S:
        ok, dirs = clock_dir_check(store)
        CLOCK.update(dir_ok=ok, dirs=dirs, dir_at=now)
    p = clock_peer_row(store, now) if peer is None else (None if peer == 'none' else peer)
    role, why = clock_decide(clock_mode(), CLOCK['ref'], float(CONFIG.get('clock_aside_s') or 20),
                             bool(CONFIG.get('clock_codes')) and CLOCK['ref'] is not None,
                             CLOCK['dir_ok'], bool(CONFIG.get('health_dir')), p)
    if role != CLOCK['role']:
        CLOCK['role'], CLOCK['why'] = role, why
        MAINT_CACHE['at'] = 0
        if role == 'aside':
            log('time: this node steps aside - %s' % why, 'warn')
            _clock_event(store, 'bad', 'this node steps aside: %s - RADIUS is answered by the other '
                         'node, the VIP address goes to it' % why)
        else:
            log('time: this node answers again', 'info')
            _clock_event(store, 'good', 'this node answers again%s' % (' - ' + why if why else ''))
    else:
        CLOCK['why'] = why
    if now - CLOCK['written'] > 10:
        CLOCK['written'] = now
        try:
            store.set_meta('clock:state:' + node_name(), json.dumps(clock_state_here(now)))
        except Exception:                               # noqa: BLE001
            pass


def clock_state_here(now=None):
    now = time.time() if now is None else now
    return {'at': now, 'node': node_name(), 'engaged': clock_engaged(), 'mode': clock_mode(),
            'ref': CLOCK['ref'], 'ref_at': CLOCK['ref_at'], 'ref_src': CLOCK['ref_src'],
            'ref_err': CLOCK['ref_err'],
            'refs': [{'server': s, 'offset': o, 'words': w} for s, o, w in CLOCK['refs']],
            'skew': CLOCK['skew'], 'skew_of': CLOCK['skew_of'], 'skew_err': CLOCK['skew_err'],
            'dir_ok': CLOCK['dir_ok'], 'dirs': [{'name': n, 'ok': ok, 'words': w} for n, ok, w in CLOCK['dirs']],
            'role': CLOCK['role'], 'why': CLOCK['why'],
            'codes_fixed': bool(CONFIG.get('clock_codes')) and clock_correction() != 0.0,
            'correction': clock_correction()}


def clock_state_of(store, name):
    if name == node_name() and (clock_watching() or CLOCK['ref_at'] > 0):
        return clock_state_here()                       # measured in this process
    return _meta_json(store, 'clock:state:' + name) or {}


def _clock_event(store, level, words):
    try:
        store.add_event('time', words, 'warn' if level == 'bad' else 'info', who='otp (clock)')
    except Exception:                                   # noqa: BLE001
        pass


@node_ask_kind('clock_try')
def _ask_clock_try(daemon, args):
    """Try it on the card: each node asks its own reference servers (as written in the form),
    the other side's clock and its directory."""
    mine = (args.get('refs') or {}).get(node_name())
    servers = clock_ref_servers(mine, daemon.store) if mine is not None else clock_ref_servers(store=daemon.store)
    got, med = clock_ref_check(servers) if servers else ([], None)
    try:
        name, sk = clock_peer_skew(daemon.store)
    except Exception as e:                              # noqa: BLE001
        name, sk = 'the other node', None
        skerr = str(e).split('\n')[0][:160]
    else:
        skerr = ''
    ok, dirs = clock_dir_check(daemon.store)
    return {'ok': med is not None, 'ref': med, 'servers': servers,
            'refs': [{'server': s, 'offset': o, 'words': w} for s, o, w in got],
            'skew': sk, 'skew_of': name, 'skew_err': skerr,
            'dir_ok': ok, 'dirs': [{'name': n, 'ok': o, 'words': w} for n, o, w in dirs]}


CLOCK_KEYS = ('clock_mode', 'clock_warn_s', 'clock_aside_s', 'clock_codes', 'clock_beat',
              'clock_locks', 'health_dir')


def clock_view(store):
    nodes = []
    saved = store.settings_saved()
    for n in ha_nodes(store):
        st = clock_state_of(store, n['name'])
        if n.get('me') and not st:
            st = clock_state_here()
        nodes.append({'name': n['name'], 'me': bool(n.get('me')), 'alive': bool(n.get('alive')),
                      'state': st, 'ref': str(saved.get('clock_ref@' + n['name'])
                                              or (CONFIG.get('clock_ref') if n.get('me') else '') or ''),
                      'fresh': bool(st) and time.time() - float(st.get('at') or 0) < 60})
    if not nodes:
        nodes = [{'name': node_name(), 'me': True, 'alive': True, 'state': clock_state_here(),
                  'ref': str(CONFIG.get('clock_ref') or ''), 'fresh': True}]
    try:
        common = [str(x.get('host') if isinstance(x, dict) else x) for x in
                  (ntp_conf(store).get('servers') or [])]
    except Exception:                                   # noqa: BLE001
        common = []
    return {'engaged': clock_engaged(), 'ha_mode': CONFIG.get('ha_mode') or '',
            'cluster': in_cluster(store), 'conf': {k: CONFIG.get(k, DEFAULTS.get(k)) for k in CLOCK_KEYS},
            'me': node_name(), 'nodes': nodes, 'common': [c for c in common if c][:5]}
```

`parts/90z_clock_api.py` - the card's API:

```python
# ---- the card of the clocks (1.0.222): Settings -> Time -> The clocks of the nodes
@route('GET', '/api/clock')
def _clock_get(h):
    h.me()
    return clock_view(h.store)


def _clock_refs_checked(names, refs):
    out = {}
    for n, v in refs.items():
        if n not in names:
            raise ApiError(400, 'there is no node called %s' % n)
        try:
            split_targets_parse(v)
        except ValueError as e:
            raise ApiError(400, '%s: %s' % (n, e))
        out[str(n)] = str(v or '').strip()
    return out


@route('POST', '/api/clock')
def _clock_post(h):
    s = h.me('fulladmin')
    b = h.body()
    act = str(b.get('action') or '')
    names = [n['name'] for n in ha_nodes(h.store)] or [node_name()]
    refs = _clock_refs_checked(names, b.get('refs') if isinstance(b.get('refs'), dict) else {})
    if act == 'try':
        return node_ask(h.d, 'clock_try', {'refs': refs}, s['name'])
    if act == 'poll':
        return {'nodes': node_ask_results(h.store, 'clock_try', str(b.get('id') or ''))}
    if act != 'save':
        raise ApiError(400, 'save, try or poll')
    conf = b.get('conf') if isinstance(b.get('conf'), dict) else {}
    want = {k: conf[k] for k in CLOCK_KEYS if k in conf}
    if 'clock_mode' in want and want['clock_mode'] not in CLOCK_MODES:
        raise ApiError(400, 'the mode is off, watch or guard')
    for k, (lo, hi) in (('clock_warn_s', (1, 60)), ('clock_aside_s', (5, 600))):
        if k in want:
            try:
                want[k] = int(want[k])
            except (TypeError, ValueError):
                raise ApiError(400, '%s is a number' % k)
            if not lo <= want[k] <= hi:
                raise ApiError(400, '%s is %d-%d' % (k, lo, hi))
    for k in ('clock_codes', 'clock_beat', 'clock_locks', 'health_dir'):
        if k in want:
            want[k] = 1 if want[k] in (1, True, '1', 'on') else 0
    warn = int(want.get('clock_warn_s', CONFIG.get('clock_warn_s') or 2))
    aside = int(want.get('clock_aside_s', CONFIG.get('clock_aside_s') or 20))
    if aside <= warn:
        raise ApiError(400, 'stepping aside comes after the warning: more seconds than it')
    if want.get('clock_mode') == 'guard' and want.get('clock_mode') != CONFIG.get('clock_mode') \
            and b.get('checked') is not True:
        raise ApiError(409, 'try the reference from every node first (Try it): a node that cannot '
                            'ask it is never stepped aside, but you would not know it is unguarded')
    many = len(names) > 1
    if want:
        h.d.save_settings(want, by=s['name'], node='*' if many else None)
    for n, v in refs.items():
        h.d.save_settings({'clock_ref': v}, by=s['name'], node=n)
    CLOCK['ref_at'] = 0.0                               # asked again at the next look
    h.store.add_event('settings', '%s chose what the nodes do about their clocks: %s' % (
        s['name'], ', '.join('%s=%s' % kv for kv in sorted(want.items())) or 'reference servers'),
        'warn', who=s['name'])
    return {'message': 'kept - each node follows it within seconds', 'view': clock_view(h.store)}
```

The hooks elsewhere, each one line or a few (sections 6-10): `88_upgrade.py` `maintenance_now`,
`87_ha.py` `ha_nodes`, `60_engine.py` (`clock_now('codes')`, `clock_now('locks')`), `90_api.py`
(the code now), `90m_mfa.py`, `87s_sshotp.py`, `88z_alerts.py`, `80_daemon.py` (the loop's
`clock_tick` and the settings list's skip).
