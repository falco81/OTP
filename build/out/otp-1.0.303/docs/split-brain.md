# When the two nodes lose each other - split brain (otp 1.0.218)

## Shrnutí česky

**Split brain** je situace, kdy dva uzly HA clusteru přestanou vidět jeden druhého,
ale oba dál běží. Každý si myslí, že druhý umřel, a pokračuje sám. U otp se dvěma
replikovanými PostgreSQL to znamená tři rizika:

1. **jednorázový kód projde na obou polovinách** (kód z aplikace během svých 30–90 s,
   záchranný kód kdykoli),
2. **špatné pokusy se počítají v každé polovině zvlášť** - útočník má dvojnásobek pokusů
   do pauzy a do zámku,
3. **změny adminů se rozejdou** - co se na každé straně změní, jde vlastní cestou a po
   spojení jedna verze tiše vyhraje.

Se dvěma uzly a bez třetího stroje se split brain **vyloučit nedá** (mrtvý soused a
odříznutý soused vypadají zevnitř stejně). Dá se ale zvolit, **kdo pokračuje**, a
**zmírnit, co se mezitím děje**. Na kartě **Nastavení → Vysoká dostupnost → Když se uzly
ztratí** se volí:

**Kdo obsluhuje, když se uzly nevidí** (jedna ze tří):

| volba | co dělá | plus | mínus |
|---|---|---|---|
| **Jako dosud: pokračují oba uzly** | se všemi přepínači vypnutými **neběží vůbec nic** - přesně chování před 1.0.218 (výchozí) | nikdo není odmítnut | všechna tři rizika |
| **Uzel, který stále vidí síť** (arbitr) | každý uzel se ptá svého arbitra (výchozí brána nebo zadaná adresa); kdo nevidí druhý uzel ani arbitra, ustoupí stranou | odříznutý uzel okamžitě přestane obsluhovat; opravdu mrtvý uzel nevadí | když se přeruší jen spojení mezi uzly a oba vidí síť, obsluhují oba |
| **Jen upřednostněný uzel** | když se nevidí, obsluhuje jen upřednostněný | nikdy neobsluhují dvě poloviny | když vypadne právě upřednostněný, neobsluhuje nikdo |

**A zatímco jsou odděleně** (libovolná kombinace):

- **Záchranné kódy jen s potvrzením druhého uzlu** - záchranný kód se odmítne (a nepočítá jako
  špatný), dokud se nedá zeptat druhého uzlu; kódy z aplikace fungují dál.
- **Poloviční pokusy** - pauza i zámek na každém uzlu po polovině pokusů; obě poloviny
  dohromady dovolí tolik, co jeden uzel.
- **Změny jen na upřednostněném uzlu** - jinde stránky jen čtou (karta Split jde měnit vždy).
- **Upozornit během oddělení, report potom** - alert, a po spojení report: kolik kódů
  prošlo bez dotazu na druhý uzel, a které prošly na obou (jménem).

**Výchozí stav = „Jako dosud“ se všemi přepínači vypnutými** a v něm se nespouští nic
nového: žádný dotaz na databázi druhého uzlu, žádný ping arbitra, nic se nezapisuje, žádné
upozornění, žádná změna přihlašování. Upgrade tedy chování nemění; karta to říká („Přesně
jako před 1.0.218: nic z toho neběží“).

„Ustoupit stranou“ = údržba, kterou nikdo nezapnul a která sama skončí: RADIUS se
neobsluhuje (VPN se zeptá druhého uzlu), VIP adresa odejde, stránky zůstávají.

Karta ukazuje živý stav obou uzlů, tři volby jako dlaždice s plusy a mínusy, čtyři
přepínače, **tabulku „Co se stane“** spočítanou z aktuálních voleb pro pět druhů výpadku
(ještě před uložením) a report posledního oddělení. Ukládá se lištou dole. Arbitra je
nutné před uložením vyzkoušet ze všech uzlů (tlačítko **Vyzkoušet ze všech uzlů**).

Zbytek dokumentu je specifikace pro implementaci (anglicky): algoritmus, napojení,
API, data, **kompletní UI včetně HTML, CSS a JavaScriptu** a české texty - aby šlo stejnou
věc i se stejným vzhledem udělat v jiné aplikaci (kapitola 12 je kontrolní seznam).

---

## Contents

1. What it is about
2. Words used
3. Settings
4. The watch - how "apart" is told
5. The arbiter
6. The decision
7. What changes while apart (stepping aside, recovery codes, tries, changes, report)
8. What happens - the matrix
9. API
10. What is kept in the database
11. The card - UI specification (layout, behaviour, texts, HTML, CSS, JavaScript)
12. Porting it to another application - checklist
13. Tests
14. For the administrator - choosing, and what to do while apart

---

## 1. What it is about

Two nodes, each with its own PostgreSQL, replicating both ways (active/active). Either
node answers RADIUS and the pages. A code used on one node is written to that node's
database (`token_once`); before it is let in, the node also asks the **other node's
database** directly whether it was used there (the replication may lag). As long as the
other database answers, a code is never let in twice.

When the two nodes cannot reach each other, the direct question fails - and, until 1.0.218,
the code was let in on the strength of this node's rows alone. Each node, believing the
other gone, went on: that is split brain. Its costs:

| cost | why |
|---|---|
| a code let in twice | each half checks only its own rows |
| twice the wrong tries | each half counts its own failures (pause after N, lockout after M) |
| changes going two ways | an admin on each half changes the same thing; after the heal, "newer wins" per row |
| the VIP address on both | keepalived of each node cannot hear the other's VRRP |

**Not solvable with two nodes:** from inside one node, "the other is dead" and "I am cut
off" look the same. Only a third point of view - an *arbiter* - tells them apart. otp uses
something that is already there (the default gateway, the router, the VPN concentrator)
as that third point; a dedicated third machine (a witness) is not part of this.

**One shared database** (both nodes open one PostgreSQL): no split brain of the data at all
- the database decides. The card says so and offers nothing.

## 2. Words used

| word | meaning |
|---|---|
| **apart** | the other node's database has not answered for `split_after_s` seconds |
| **together** | it answers again |
| **step aside** | stop answering RADIUS and let the VIP address go - as maintenance, but automatic and ending by itself |
| **preferred node** | the one chosen (`split_prefer`), else the first node of the cluster (`ha_slot` 1) |
| **arbiter** | addresses a node pings (or `host:port` it connects to) to know whether *it* is cut off |
| **cut off** | a node that reaches neither the other node nor its arbiter |

## 3. Settings

All are cluster-wide settings, except `split_arbiter`, which each node has its own
(`split_arbiter@NODE`).

| key | type, range | default | meaning |
|---|---|---|---|
| `split_mode` | `off` \| `arbiter` \| `priority` | `off` | who answers while apart |
| `split_prefer` | a node's name, or empty | `''` | the preferred node; empty = `ha_slot` 1 |
| `split_arbiter` | text, per node | `''` | up to 5 targets, comma or space separated: `192.0.2.1`, `gw.example.cz:443`, `[2001:db8::1]:53`, `2001:db8::2`; empty = the node's default gateway |
| `split_after_s` | 5-300 | 20 | seconds without the other database before "apart" |
| `split_scratch` | 0/1 | 0 | recovery codes only with the other node asked |
| `split_halve` | 0/1 | 0 | half the tries (pause and lockout) while apart |
| `split_freeze` | 0/1 | 0 | changes only on the preferred node while apart |
| `split_report` | 0/1 | 0 | alert while apart, report afterwards |

**"As until now"** - `split_mode = off` and all four switches 0, the defaults - is exactly
the behaviour before 1.0.218: the watch (4) does nothing at all in it - no question to the
other node's database, no arbiter, no state row written, no code written down, no alert,
no limit changed, nothing frozen (`split_engaged()` false). An upgrade changes nothing.

Saving `split_mode = arbiter` (from a mode that was not arbiter) is **refused unless the
arbiter was tried from every node** and every node reached its own (`checked: true`, see
9). A node that cannot reach its arbiter would step aside the moment the other node is away
- the whole cluster silent.

## 4. The watch - how "apart" is told

A thread of its own (`otp-split`), started once by the daemon's loop, every **2 s**:

1. **Not a replicating pair** (`ha_mode != 'replicated'` or no `ha_peer`), **or "as until
   now"** (mode off, every switch off - `split_engaged()` false): reset - never apart, always
   serving, nothing asked, nothing written. Done.
2. **Ask the other node's database**: on a connection of its own (2 s connect timeout,
   2 s statement timeout), `SELECT 1`, waited for 3.5 s at most in a helper thread (a peer
   that drops packets holds nothing). Success: `peer_ok_at = now`.
   *Why the database and not a heartbeat:* the heartbeat comes through replication (it
   stops when replication stops even if the node is fine), and the other node's database
   is exactly what is asked before a code is let in - "apart" means "the code check
   cannot be done".
3. **Ask the arbiter** - every step in `arbiter` mode, otherwise every 30 s (for the card).
4. **apart = now - peer_ok_at > split_after_s** (min 5). On start, `peer_ok_at` is the
   start time: a node gets `split_after_s` to find the other.
5. Transitions: *together → apart*: log + event "the nodes lost each other …"; *apart →
   together*: event "… again, after X apart", and a report is due 30 s later - made only
   once the other node's state row written after it found this one again has come over by
   replication (its earlier rows come before it), at the latest 10 min later (1.0.224: after a
   long cut the replication took 40 s, and the codes let in on both were not found). Its
   pooled connections from before are closed. And in any mode, "as until now" included,
   while the question before a code is let in is held off (the other node's database did not
   answer) the watch asks every 2 s and lifts the hold the moment it answers (1.0.224).
6. **Decide** (6) the role; on a change: event + log, and the maintenance cache is
   flushed so that RADIUS and the VIP check see it at once.
7. Every 10 s (and on every change of apart) write this node's state into meta
   `split:state:<node>` (for the card and the alerts; replicated to the other node
   whenever they are together).
8. If the report is due and the nodes are together: make it (7.5).

Hysteresis is built in: apart needs `split_after_s` of silence; together needs one answer.

## 5. The arbiter

Targets: `split_arbiter` of this node; empty → the default gateway, read from
`/proc/net/route` (the line with destination `00000000` and the gateway flag). No gateway
and none given → no arbiter (verdict "cannot be asked").

Each target:

- **`host:port`** → TCP connect, 1 s. Connected → reached. **Refused → reached too** (it
  answered: it is there). Timeout or unreachable → not reached.
- **an address or a name** → one ICMP echo, 1 s, tried in this order:
  1. a **datagram ICMP socket** (`socket(AF_INET, SOCK_DGRAM, IPPROTO_ICMP)`) - allowed to
     any user whose group is in `net.ipv4.ping_group_range` (RHEL 9, systemd's default:
     everybody), needs no capability, no binary;
  2. a **raw socket** (root or CAP_NET_RAW);
  3. **`/usr/bin/ping -c 1 -W 1`**;
  4. none possible → **"cannot be asked"** (not "not reached"!) with the words "this machine
     lets nobody send a ping - give the arbiter as host:port".
  A name that does not resolve → not reached.

Verdict over all targets: **any one reached → reached**; every one asked and none answered
→ **not reached**; otherwise → **cannot be asked**. "Cannot be asked" never makes a node step
aside (fail-open: a broken ping must not silence a healthy cluster) - the card shows it.

Choosing an arbiter: something both nodes reach **by another way than they reach each
other**: the router/gateway, the VPN concentrator (it is the RADIUS client - if a node
cannot reach it, that node is useless anyway). Not the other node, not a machine behind the
same switch port as one node.

## 6. The decision

```
decide(mode, apart, arbiter, preferred) -> ('serve' | 'aside', why)

if not apart                 -> serve
mode == 'priority':
    preferred                -> serve  "the preferred node answers while the nodes are apart"
    else                     -> aside  "the nodes cannot reach each other and this is not the preferred node"
mode == 'arbiter':
    arbiter is False         -> aside  "neither the other node nor the arbiter can be reached - this node is the one cut off"
    arbiter is None          -> serve  "the arbiter cannot be asked from here - this node answers"
    arbiter is True          -> serve  "the arbiter is reached - this node answers"
mode == 'off'                -> serve  "both nodes answer while they are apart (no rule chosen)"
```

Deliberately **no tie-break in arbiter mode** (both see the arbiter but not each other):
from inside, "the link between us broke" and "the other node died" are the same picture -
a tie rule that silences one node would silence it when the other really dies. The
switches of 7 limit what two serving halves can do.

### 6.1 The preferred node's database down, its machine there (1.0.226)

"Apart" is "the other node's database does not answer". In priority mode that used to step the
other node aside even when the preferred node's machine and link were fine and only its database
was down (stopped, restarting) - and the preferred node, with no database, answered nobody either:
both silent for as long as it lasted. A refusal of the database (connection refused, shutting down,
starting up) is not a cut link - a cut link gives no answer at all: the other node then takes the
preferred node for unable and goes on. The same when the preferred node's last word, from about
when the nodes lost each other, was that it stepped aside for its clock or is in maintenance.

1.0.227 narrows this:

- **"Connection refused" alone is not enough.** A firewall between the nodes that rejects (nftables
  `reject`, iptables `REJECT`) gives the same words while the preferred node is up and answering -
  both nodes answered. A bare refusal counts only when the preferred node's machine takes a TCP
  connection on another port (443, 22 or 80): the machine there, only its database refusing.
  "Shutting down" / "starting up" (an answer from PostgreSQL itself) counts as before.
- **Its clock "aside" counts only while its row is fresh** (younger than 32 s, by the measured
  difference of the clocks). The preferred node, aside for its clock, no longer stays aside for as
  long as the nodes are apart (1.0.226 did: with the other node dead that was for ever, and nobody
  answered): it answers again once the other node's row reads stale to it (25 s), and the other
  node gives way a few seconds after.
- **A node that steps aside for the split or its clock is silent at once**, also on the VIP
  address while keepalived moves it. Before, it went on answering up to 20 s ("draining", meant for
  maintenance asked for by hand): a code was let in there and again on the other node.

## 7. What changes while apart

### 7.1 Stepping aside

One gate everybody already asks: `maintenance_now()`. While the role is `aside`, it returns
`{'on': True, 'why': 'stepped aside: <why>', 'split': True}` before reading the stored
maintenance row. Hence, with no other change:

- RADIUS packets are not answered (the NAS asks the other server, as for a node down),
- the VIP health check says "in maintenance" → keepalived moves the address,
- `/healthz` and the heartbeat say maintenance (load balancers take the node out),
- the pages keep working.

The stored maintenance (`maint:<node>`) is not touched: when the role goes back to `serve`,
whatever maintenance was set by hand stays.

### 7.2 Recovery codes only with the other node asked (`split_scratch`)

Before a recovery code is used (and before anything is written):

- apart → refuse;
- together, but the other node's database cannot be asked this moment (the direct
  question returns "unknown") → refuse;

with the words *"A recovery code cannot be used while the two servers cannot reach each
other - use the code of the app"*, **not counted as a wrong code**, the code not used up.
TOTP codes (30 s life) keep working.

### 7.3 Half the tries (`split_halve`)

Wherever `rate_limit_tries` (the pause) and `lockout_after` (the lockout) are read for
counting, they are read through `split_limit(key)`: apart and switched on → `max(1,
ceil(v/2))`. Two halves together then allow about what one node does.

### 7.4 Changes only on the preferred node (`split_freeze`)

In the API dispatcher, before a POST route runs: apart, switched on, and this node is
**aside or not the preferred node** → **409** `{"ok": false, "split": true, "error": "the two
nodes cannot reach each other: changes are made on <preferred> only until they do (…)"}`.
Allowed always: `/api/auth/*` (sign in/out, 2nd step), `/api/split` (to switch it off),
`/api/ha*`, `/api/power`, `/api/maintenance`, `/api/acme-push/*`, `/api/health`,
`/api/alerts`, `/api/logs`. GET is never refused. RADIUS is not affected.

### 7.5 Warning and report (`split_report`)

- **While apart**: an alert problem `split:<node>` (level bad): "<node> cannot reach the
  other node [and stepped aside]" - "The other node's database has not answered since …
  This node answers RADIUS alone / does not answer RADIUS." Through the alert mail like any
  other problem.
- **Written down**: every one-time code let in while the other node's database could not
  be asked (the direct question returned "unknown") → meta
  `split:took:<node>:<once key>` = `{name, kind, at}`. The once key is the same hash for
  the same code on both nodes.
- **The report** (on the preferred node, after together, the other node's rows having
  come over; rows from the first code the other node could not be asked about, those of an
  earlier short outage left out, each code counted once - not again by its token's `#id`): group `split:took:*` by once key; a key with rows from both nodes = let in
  on both. Meta `split:report` = `{at, since, taken: {node: n}, twice: [{name, kind,
  nodes, at}], twice_n}`; the rows deleted; an event (bad if any twice); an alert
  `split:twice` (warn) for 24 h listing the names.

## 8. What happens - the matrix

A = the preferred node, B = the other. "answers" = serves RADIUS; "aside" = steps aside.

| what fails | off | arbiter | priority |
|---|---|---|---|
| **B fails** | A answers | A answers | A answers |
| **A fails** | B answers | B answers | **nobody** (B aside) |
| **B loses the network** | A answers; B answers whatever still reaches it (risks) | A answers; B aside | A answers; B aside |
| **A loses the network** | B answers; A answers whatever reaches it (risks) | B answers; A aside | **nobody reachable** (B aside, A cut off) |
| **only the link A-B breaks** | both answer (risks) | both answer (risks) | A answers; B aside |

"Risks" = a code may pass on both (recovery codes: not with `split_scratch`), twice the
wrong tries (not with `split_halve`), changes two ways (not with `split_freeze`). The card
draws this table live from the choices.

## 9. API

### GET /api/split (any signed-in administrator)

```json
{"active": true, "ha_mode": "replicated",
 "conf": {"split_mode": "arbiter", "split_prefer": "", "split_after_s": 20, "split_scratch": 1,
          "split_halve": 0, "split_freeze": 0, "split_report": 1},
 "preferred": "otp1", "me": "otp1",
 "nodes": [
   {"name": "otp1", "me": true, "alive": true, "fresh": true, "arbiter": "",
    "state": {"at": 1793570000.1, "node": "otp1", "active": true, "mode": "arbiter",
              "apart": false, "since": 0, "peer_ok_at": 1793570000.0, "peer_err": "",
              "role": "serve", "why": "", "preferred": true,
              "arbiter": true, "arbiter_at": 1793569999.0,
              "arbiters": [{"target": "192.0.2.1", "ok": true, "how": "ping", "words": ""}],
              "gateway": "192.0.2.1", "frozen": false, "halved": false}},
   {"name": "otp2", "me": false, "alive": true, "fresh": true, "arbiter": "10.0.0.1, vpn.example.cz:443",
    "state": {"...": "the other node's own row, as replication brought it"}}],
 "report": {"at": 1793560000, "since": 1793559000, "taken": {"otp1": 12, "otp2": 3},
            "twice": [{"name": "ana@corp", "kind": "step", "nodes": ["otp1", "otp2"], "at": 1793559100}],
            "twice_n": 1}}
```

`fresh`: the node's state row is under 60 s old (the other node's row is stale while
apart - it cannot come over).

### POST /api/split (full administrator)

- `{"action": "save", "conf": {split_* keys}, "arbiter": {"otp1": "...", "otp2": "..."},
  "checked": true|false}` → saves (cluster-wide `conf`, each node's `arbiter`), event,
  `{"message", "view"}`. 409 when switching to `arbiter` without `checked`. 400 on a bad
  mode, an unknown node, a bad arbiter.
- `{"action": "try", "targets": {"otp1": "...", "otp2": "..."}}` → asks **every node** to
  check its own targets (an "ask" kept in the database that each node's loop answers within
  seconds); `{"id", "nodes": [...]}`.
- `{"action": "poll", "id": "..."}` → `{"nodes": {"otp1": {"ok", "verdict": true|false|null,
  "gateway", "targets": [{"target", "ok", "how", "words"}]} | null, ...}}`.

Refused while frozen? No - `/api/split` is always allowed (to switch the freeze off).

## 10. What is kept in the database (meta, replicated)

| key | written by | what |
|---|---|---|
| `split:state:<node>` | that node, every 10 s and on change | its state (as in `nodes[].state`) |
| `split:took:<node>:<once key>` | that node, per code let in without the other asked | `{name, kind, at}` |
| `split:report` | the preferred node, after together | the last report |
| settings `split_*`, `split_arbiter@<node>` | the pages | as in 3 |
| `ask:want:split_arbiter`, `ask:got:split_arbiter:<node>` | the card / each node | Try it |

Nothing of this is a secret. On a restore of a backup `split:state:` rows of the backup are
harmless (stale, `fresh` false).


## 11. The card - UI specification

The card lives on **Settings → High availability**, after the card of the VIP address and
before the generic settings of the pane. It is drawn only when the node is one of a cluster
(`ha.mode` set); for one shared database it says there is nothing to choose.

### 11.1 Layout

```
┌ When the nodes lose each other ─────────────────────────────── [TOGETHER] ┐
│ Two nodes that cannot reach each other … (the note: what split brain is)    │
│                                                                             │
│ ┌ otp1  [this page] [preferred]   [ANSWERS] ┐   ║    ┌ otp2         [ANSWERS] ┐
│ │ ✓ reaches the other node                  │ ⟷ ║    │ ✓ reaches the other node│
│ │ ✓ arbiter 192.0.2.1                        │ together│ ✓ arbiter 10.0.0.1      │
│ └────────────────────────────────────────────┘   ║    └─────────────────────────┘
│                                                                             │
│ Who answers while they cannot reach each other                              │
│ ┌──────────────────────┐ ┌──────────────────────┐ ┌──────────────────────┐  │
│ │ [ico] As until now: │ │ [ico] The node that   │ │ [ico] Only the        │  │
│ │  both nodes go on [AS BEFORE]│ │  still sees the network│ │  preferred node       │  │
│ │ As until now: …       │ │ Each node asks its …  │ │ While they cannot …   │  │
│ │ + Nobody is ever …    │ │ + A node cut off …    │ │ + Never two halves …  │  │
│ │ − A code may be …     │ │ + A node really gone… │ │ − If the preferred …  │  │
│ │ − The wrong tries …   │ │ − When only the link… │ │                       │  │
│ └──────────────────────┘ └──────────────────────┘ └──────────────────────┘  │
│  (the chosen one: accent border, light accent background, icon filled)       │
│                                                                             │
│ The preferred node [select]            Apart after (seconds) [20]           │
│                                                                             │
│ ┌ (only in arbiter mode, dashed box) ────────────────────────────────────┐  │
│ │ Each node's arbiter: … (note)                                          │  │
│ │ Arbiter of otp1 [ its gateway 192.0.2.1 ]  Arbiter of otp2 [         ] │  │
│ │ [Try it from every node]  [EVERY NODE REACHES ITS ARBITER]             │  │
│ │ ✓ otp1: 192.0.2.1 replies                                              │  │
│ │ ✗ otp2: 10.0.0.1 no answer (no answer to ping within 1.0 s)            │  │
│ └────────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│ And while they are apart                                                    │
│ ┌[ico] Recovery codes only with the …  (o)┐ ┌[ico] Half the tries …     (o)┐ │
│ │      A recovery code is used up …        │ │      The pause after …       │ │
│ └──────────────────────────────────────────┘ └──────────────────────────────┘ │
│ ┌[ico] Changes only on the preferred … (o)┐ ┌[ico] Warn while apart, …  (o)┐ │
│ └──────────────────────────────────────────┘ └──────────────────────────────┘ │
│                                                                             │
│ What happens - with the choices above                                       │
│ When                         │ otp1      │ otp2        │ Sign-ins   │ What it costs │
│ otp1 is switched off or fails│ [GONE]    │ [ANSWERS]   │ otp2 answ… │ none          │
│ otp2 is switched off or fails│ [ANSWERS] │ [GONE]      │ …          │ …             │
│ otp1 loses the network       │ [STEPS…]  │ [ANSWERS]   │ …          │ …             │
│ otp2 loses the network       │ …         │ …           │ …          │ …             │
│ Only the link between …      │ [ANSWERS] │ [ANSWERS]   │ both answer│ (amber) …     │
│                                                                             │
│ ✓ The last time apart (date - date) codes let in without …: otp1: 12 · …    │
└─────────────────────────────────────────────────────────────────────────────┘
                     [ Save the changes ] [ Put them back ]  1 change not saved
```

Below 720 px the two node tiles stack, the link between them turns horizontal, the switches
go one under the other; the choices wrap (an auto-fit grid, 240 px minimum). The four
switches are always two by two (never three and one alone). The table of what happens has
**fixed column widths** (25 / 13 / 13 / 17 / 32 %, at least 760 px, scrolled sideways in its box
below that): laid out by their words its columns moved with every switch, the costs being
longer or shorter with each choice.

### 11.2 Behaviour

- **Draft**: the card keeps a draft (`SPLITC.draft`) made from the server's view; every click
  changes the draft and redraws (the arbiter fields redraw only when left, so the cursor
  stays). A draft different from the view registers a pending change with the page's
  common save bar (`pendingSet('split', {pane: 'ha', save, reset})`); equal again, it
  withdraws it. **Nothing is sent before Save**; *Put them back* drops the draft.
- **Changed marks**: a field whose draft differs from the saved value gets the class
  `changed` (the page's usual amber edge); a choice card shows the draft's choice.
- **Arbiter first tried**: choosing *The node that still sees the network* shows the
  arbiter box. *Try it from every node* sends the arbiters as typed (`try`), then polls
  every second (up to 20 s) and lists each node's result as it comes. Save to `arbiter`
  (from another mode) is blocked on the page and refused by the server unless the last
  try was of exactly these arbiters and every node reached its own. Typing in a field
  forgets the last try.
- **What happens** is recomputed from the draft on every change (`splitScenarios()`): five
  rows, the preferred node first; each cell a tag (`answers` green, `steps aside` amber,
  `gone`/`cut off` grey); the last two columns sentences coloured by outcome (green fine,
  amber a risk, red no sign-ins), each risk a sentence of its own.
- **Live**: the card is fetched with the pane (and with the pane's own refresh); the node
  tiles show the stored state rows; a tile older than 60 s is dimmed ("its word has not
  come over yet" / "nothing heard from it").
- **Who may**: only a full administrator changes anything; everyone else sees it disabled.
- **The page stays where it is**: the card is drawn again whole on every change; around it
  the scroll position of every scrolled box is kept and put back (`scrollHeld` / `scrollBack`
  of the page; `drawSplit` wraps `drawSplitIn`). Without it the card is empty for a moment,
  the pane is short, and a switch clicked half-way down sends the page to the top (otp 1.0.218
  and 1.0.219 did). Test it with a real mouse click on the switch, not a script's click.

### 11.3 The texts, English and Czech

Every string of the card, as the page's translation file has it. Strings with a node's name
are patterns (`{0}`).

| English | Czech |
|---|---|
| When the nodes lose each other | Když se uzly ztratí |
| Two nodes that cannot reach each other each take the other for gone and go on alone (split brain): a code may then be let in on both halves, the wrong tries are counted on each half apart, and what is changed on each half goes its own way. Without a third machine it cannot be ruled out - but which node goes on, and what holds meanwhile, is chosen here. Each node watches the other’s database every two seconds. | Dva uzly, které se navzájem nevidí, považují jeden druhého za mrtvý a pokračují každý sám (split brain): kód pak může projít v obou polovinách, špatné pokusy se počítají v každé polovině zvlášť a co se změní na každé straně, jde vlastní cestou. Bez třetího stroje se to vyloučit nedá – ale který uzel pokračuje a co mezitím platí, se volí tady. Každý uzel kontroluje databázi toho druhého každé dvě sekundy. |
| one database - nothing to choose | jedna databáze – není co volit |
| apart now | teď odděleně |
| together | spolu |
| apart | odděleně |
| Both nodes open one database: whatever one node writes the other sees at once, so a code can never be let in twice, and the nodes cannot go two ways. Nothing here is needed - this is for two nodes that replicate. | Oba uzly otevírají jednu databázi: co jeden zapíše, druhý hned vidí, takže kód nikdy neprojde dvakrát a uzly se nemohou rozejít. Nic z toho tu není potřeba – je to pro dva uzly, které se replikují. |
| this page | tato stránka |
| preferred | upřednostněný |
| not heard from | neozývá se |
| stepped aside | ustoupil stranou |
| answers | obsluhuje |
| cannot reach the other node | nevidí druhý uzel |
| reaches the other node | vidí druhý uzel |
| arbiter | arbitr |
| changes on the pages wait here | změny na stránkách tu čekají |
| half the tries | poloviční pokusy |
| its word has not come over yet | jeho stav sem ještě nedorazil |
| nothing heard from it - it is down, or the link is | nic od něj nepřišlo – je dole, nebo spojení |
| Who answers while they cannot reach each other | Kdo obsluhuje, když se uzly nevidí |
| As until now: both nodes go on | Jako dosud: pokračují oba uzly |
| Each node goes on alone and answers everything. With every switch below off nothing of this runs at all - no question to the other node, no arbiter, nothing written: exactly as before. | Každý uzel pokračuje sám a obsluhuje vše. Se všemi přepínači níže vypnutými neběží vůbec nic z toho – žádný dotaz na druhý uzel, žádný arbitr, nic se nezapisuje: přesně jako dřív. |
| as until now - not watched | jako dosud – nesleduje se |
| not watched | nesleduje se |
| nothing is watched - as before: it goes on alone whatever happens to the other | nic se nesleduje – jako dřív: pokračuje sám, ať se s druhým děje cokoli |
| Exactly as before 1.0.218: nothing of this runs. | Přesně jako před 1.0.218: nic z toho neběží. |
| Both nodes go on; the switches below hold while they are apart - the other node’s database is watched for it. | Pokračují oba uzly; přepínače níže platí, zatímco jsou odděleně – kvůli tomu se sleduje databáze druhého uzlu. |
| The other node’s database is watched every two seconds. | Databáze druhého uzlu se kontroluje každé dvě sekundy. |
| Nobody is ever turned away while one node answers | Dokud odpovídá aspoň jeden uzel, nikdo není odmítnut |
| A code may be let in on both halves | Kód může projít v obou polovinách |
| The wrong tries are counted on each half apart | Špatné pokusy se počítají v každé polovině zvlášť |
| Changes made on each half go their own way | Změny na každé straně jdou vlastní cestou |
| The node that still sees the network | Uzel, který stále vidí síť |
| Each node asks its arbiter - its default gateway, or an address given. The node that reaches neither the other node nor its arbiter is the one cut off: it steps aside. | Každý uzel se ptá svého arbitra – své výchozí brány nebo zadané adresy. Uzel, který nevidí druhý uzel ani svého arbitra, je ten odříznutý: ustoupí stranou. |
| A node cut off from the network stops at once | Uzel odříznutý od sítě hned přestane obsluhovat |
| A node really gone: the other goes on alone | Když uzel opravdu vypadne, druhý pokračuje sám |
| When only the link between the two nodes breaks, both still answer | Když se přeruší jen spojení mezi uzly, obsluhují dál oba |
| Only the preferred node | Jen upřednostněný uzel |
| While they cannot reach each other only the preferred node answers; the other steps aside. | Dokud se nevidí, obsluhuje jen upřednostněný uzel; druhý ustoupí stranou. |
| Never two halves answering | Nikdy neobsluhují dvě poloviny |
| If the preferred node itself is gone, nobody answers until it is back - or this is changed | Když vypadne sám upřednostněný uzel, nikdo neobsluhuje, dokud se nevrátí – nebo dokud se tohle nezmění |
| as before | jako dosud |
| The preferred node | Upřednostněný uzel |
| Answers alone with Only the preferred node; the only node where changes are made while apart; makes the report afterwards. | Obsluhuje sám při volbě Jen upřednostněný uzel; jediný uzel, kde se během oddělení dělají změny; po spojení sestaví report. |
| Apart after (seconds) | Odděleně po (sekundách) |
| How long the other node’s database must not answer before the nodes count as apart. Shorter: sooner safe; longer: a short hiccup of the network changes nothing. | Jak dlouho nesmí databáze druhého uzlu odpovídat, než se uzly považují za oddělené. Kratší: dřív v bezpečí; delší: krátký výpadek sítě nic nezmění. |
| Each node’s arbiter: what it asks to tell “the other node is gone” from “I am the one cut off”. Empty: its default gateway. Addresses are pinged; name:port is tried over TCP instead (for a network that drops ping). Up to five, any one answering is enough. Give something both nodes reach by different ways than they reach each other - the router, the VPN concentrator. | Arbitr každého uzlu: koho se ptá, aby rozlišil „druhý uzel vypadl“ od „odřízli mě“. Prázdné: jeho výchozí brána. Adresy se pingají; jméno:port se místo toho zkouší přes TCP (pro síť, která ping zahazuje). Nejvýš pět, stačí, když odpoví kterýkoli. Zadejte něco, k čemu se oba uzly dostanou jinou cestou než k sobě navzájem – router, VPN koncentrátor. |
| Try it from every node | Vyzkoušet ze všech uzlů |
| every node reaches its arbiter | každý uzel vidí svého arbitra |
| not every node reaches its arbiter | ne každý uzel vidí svého arbitra |
| needed before saving | nutné před uložením |
| asking… | ptám se… |
| no answer | bez odpovědi |
| its default gateway | jeho výchozí brána |
| replies | odpovídá |
| cannot be asked | nelze se zeptat |
| no arbiter: no default gateway - give one | žádný arbitr: chybí výchozí brána – zadejte ho |
| And while they are apart | A zatímco jsou odděleně |
| Recovery codes only with the other node asked | Záchranné kódy jen s potvrzením druhého uzlu |
| A recovery code is used up for good: while the other node cannot be asked whether it was used there, it is refused - and not counted as wrong. The codes of the app keep working. | Záchranný kód se spotřebuje navždy: dokud se nedá zeptat druhého uzlu, jestli tam nebyl použit, odmítne se – a nepočítá se jako špatný. Kódy z aplikace fungují dál. |
| Half the tries while apart | Poloviční pokusy během oddělení |
| The pause after wrong codes and the lockout come after half their tries on each node - both halves together then allow what one node does. | Pauza po špatných kódech i zámek přijdou na každém uzlu po polovině pokusů – obě poloviny dohromady pak dovolí tolik, co jeden uzel. |
| Changes only on the preferred node while apart | Změny jen na upřednostněném uzlu během oddělení |
| On the other node the pages show everything and change nothing (tokens, clients, settings) until the nodes see each other again - nothing goes two ways. This card can always be changed. | Na druhém uzlu stránky vše ukazují, ale nic nemění (tokeny, klienty, nastavení), dokud se uzly znovu neuvidí – nic se nerozejde. Tuto kartu lze měnit vždy. |
| Warn while apart, report afterwards | Upozornit během oddělení, report potom |
| An alert while the nodes cannot reach each other; once together again, a report of the codes let in without the other node asked - and of any let in on both. | Upozornění, dokud se uzly nevidí; po spojení report kódů, které prošly bez dotazu na druhý uzel – a těch, které prošly na obou. |
| What happens - with the choices above | Co se stane – s volbami výše |
| When | Kdy |
| Sign-ins | Přihlášení |
| What it costs | Co to stojí |
| gone | vypadl |
| steps aside | ustoupí stranou |
| cut off | odříznutý |
| none | nic |
| no sign-ins | žádná přihlášení |
| nobody reachable answers | neobsluhuje nikdo dosažitelný |
| both answer | obsluhují oba |
| a recovery code may pass on both | záchranný kód může projít na obou |
| an app code may pass on both within its 30 s | kód z aplikace může projít na obou během svých 30 s |
| twice the wrong tries | dvojnásobek špatných pokusů |
| changes on both halves go two ways | změny na obou stranách se rozejdou |
| Only the link between the two breaks (both still see the network) | Přeruší se jen spojení mezi nimi (oba dál vidí síť) |
| The last time apart | Poslední oddělení |
| codes let in without the other node asked: | kódy puštěné bez dotazu na druhý uzel: |
| let in on both: | puštěné na obou: |
| Try the arbiter from every node first: a node that cannot reach its arbiter would step aside the moment the other is away | Nejdřív vyzkoušejte arbitra ze všech uzlů: uzel, který na svého arbitra nedosáhne, by ustoupil stranou, jakmile by druhý vypadl |
| kept - each node follows it within seconds | uloženo – každý uzel se tím do pár sekund řídí |
| A recovery code cannot be used while the two servers cannot reach each other - use the code of the app | Záchranný kód nelze použít, dokud se oba servery nevidí – použijte kód z aplikace |
| the nodes cannot reach each other and this is not the preferred node | uzly se nevidí a tento uzel není upřednostněný |
| the preferred node answers while the nodes are apart | upřednostněný uzel obsluhuje, dokud jsou uzly odděleně |
| neither the other node nor the arbiter can be reached - this node is the one cut off | nedosáhne na druhý uzel ani na arbitra – odříznutý je tento uzel |
| the arbiter cannot be asked from here - this node answers | arbitra se odsud nelze zeptat – tento uzel obsluhuje |
| the arbiter is reached - this node answers | arbitr odpovídá – tento uzel obsluhuje |
| both nodes answer while they are apart (no rule chosen) | oba uzly obsluhují, dokud jsou odděleně (žádné pravidlo nezvoleno) |
| Who answers while the nodes are apart | Kdo obsluhuje, když jsou uzly odděleně |
| The arbiter | Arbitr |
| Apart after | Odděleně po |

| pattern | Czech |
|---|---|
| {0} is switched off or fails | {0} se vypne nebo selže |
| {0} loses the network | {0} ztratí síť |
| {0} answers everything | {0} obsluhuje vše |
| nobody answers until {0} is back | nikdo neobsluhuje, dokud se {0} nevrátí |
| whatever still reaches {0}: | co se ještě dostane na {0}: |
| Arbiter of {0} | Arbitr uzlu {0} |
| the first node ({0}) | první uzel ({0}) |
| arbiter: its gateway {0} | arbitr: jeho brána {0} |
| its gateway {0} | jeho brána {0} |
| stepped aside: {0} | ustoupil stranou: {0} |
| the two nodes cannot reach each other: changes are made on {0} only until they do (Settings -> High availability -> When the nodes lose each other) | uzly se navzájem nevidí: změny se dělají jen na {0}, dokud se neuvidí (Nastavení → Vysoká dostupnost → Když se uzly ztratí) |

### 11.4 The HTML

Inside the High availability pane, after the VIP card:

```html
    <div class="card full" id="ha-split-card" hidden>
      <h2>When the nodes lose each other <span class="right" id="ha-split-state"></span></h2>
      <p class="note">Two nodes that cannot reach each other each take the other for gone and go on alone
        (split brain): a code may then be let in on both halves, the wrong tries are counted on each half
        apart, and what is changed on each half goes its own way. Without a third machine it cannot be
        ruled out - but which node goes on, and what holds meanwhile, is chosen here. Each node watches
        the other’s database every two seconds.</p>
      <div id="ha-split"></div>
    </div>
```

### 11.5 The CSS

It uses the page's design tokens only: `--line`, `--panel`, `--panel2`, `--accent`,
`--info-bg`, `--ok`, `--ok-bg`, `--warn`, `--crit`, `--crit-bg`, `--tx`, `--tx-mut`,
`--tx-dim`, `--rad` (10 px), and the existing classes `tag` (`ok`, `warn`, `crit`, `dim`,
`violet`), `set-grid`, `btnrow`, `note`, `muted`, `small`, `mono`, `changed`, `sw` (the
switch). Light and dark themes come from the tokens.

```css
/* When the nodes lose each other - split brain (1.0.218) */
.split-now{display:grid;grid-template-columns:1fr auto 1fr;gap:12px;align-items:stretch;margin:6px 0 4px}
.split-node{border:1px solid var(--line);border-radius:var(--rad);padding:12px 14px;background:var(--panel2);
  display:flex;flex-direction:column;gap:6px;min-width:0}
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
.split-why{margin-left:20px}
.split-link{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;
  padding:0 6px;color:var(--ok)}
.split-link.broken{color:var(--crit)}
.split-link::before,.split-link::after{content:"";flex:1;width:2px;min-height:10px;background:currentColor;opacity:.35}
.split-link.broken::before,.split-link.broken::after{background:repeating-linear-gradient(currentColor 0 4px,transparent 4px 8px);opacity:.7}
.split-h{margin:22px 0 10px}
.split-choices{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px}
.split-choice{text-align:left;padding:14px 16px;border:1.5px solid var(--line);border-radius:12px;background:var(--panel);
  color:var(--tx);cursor:pointer;display:flex;flex-direction:column;gap:8px;font:inherit;transition:border-color .15s,background .15s}
.split-choice:hover:not(:disabled){border-color:var(--accent)}
.split-choice.on{border-color:var(--accent);background:var(--info-bg);box-shadow:0 0 0 1px var(--accent) inset}
.split-choice:disabled{cursor:default;opacity:.8}
.split-choice-head{display:flex;align-items:center;gap:8px}
.split-choice-k{font-weight:700;font-size:15px}
.split-choice-head .tag{margin-left:auto}
.split-choice-s{font-size:13px;color:var(--tx-mut);line-height:1.45}
.split-ic{display:inline-flex;align-items:center;justify-content:center;width:32px;height:32px;border-radius:9px;
  background:var(--info-bg);color:var(--accent);flex:none}
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
  border-radius:var(--rad);background:var(--panel)}
.split-opt.on{border-color:var(--accent);background:var(--info-bg)}
.split-opt.changed{box-shadow:0 0 0 1px var(--warn) inset}
.split-opt .sw{margin-left:auto;flex:none}
.split-opt-txt{min-width:0}
.split-opt-k{font-weight:650;font-size:14px}
.split-opt-s{font-size:12.5px;color:var(--tx-mut);margin-top:3px;line-height:1.45}
.split-scen td{vertical-align:top}
/* Columns of fixed widths (1.0.221): laid out by their words, they moved with every switch -
   the costs are longer or shorter with each choice. */
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

### 11.6 The JavaScript

The whole card. It stands on the page's helpers, whose contracts are:

| helper | contract |
|---|---|
| `$(id)` | `document.getElementById` |
| `el(tag, cls, text)` | a new element with the class(es) and text (text content, translated by the page) |
| `clear(node)` | removes the children |
| `noI18n(node)` | marks a node not to be translated (names, addresses); returns it |
| `api(name[, body])` | GET (no body) or POST JSON to the page's API relay `?api=name`; a Promise of the JSON, rejected on `ok: false` |
| `toast(words, 'good'|'bad')`, `oops(err)` | a short message; an error said |
| `busy(button, on)` | a button's busy state |
| `switchBox(on)` | a switch: `._input` the checkbox, `._get()` its value |
| `textBox(value, placeholder, cls)` | an `<input type=text>` |
| `selectBox([[value, words], …], value)` | a `<select>` |
| `formField(label, input, help)` | a labelled field (`.set-item`) with its help under it |
| `cmdButton(words, icon, cls)` | a button with an icon |
| `iconMarkup(name, size)` | an SVG icon's markup: `net`, `globe`, `pin`, `key`, `lock`, `edit`, `bell`, `check`, `close`, `info`, `clock`, `pulse`, `flag` |
| `listTable(headers, rows, rowFn, cls)` | a table; `rowFn(row)` returns a `<tr>` |
| `ago(t)`, `stamp(t)`, `num(n)` | "5 min ago", a date and time, a number |
| `dressButtons(node)` | gives the buttons in it their icons |
| `pendingSet(key, {pane, save, reset})`, `PENDING`, `markDirtyCount()` | the page's common save bar: `save()` returns a Promise of true (done) or false (not) |
| `ADMIN` | true for a full administrator |

It is called from the pane's loader: `loadSplit(ha)` with the High availability view
(`ha.mode` set when the node is one of a cluster).

```javascript
/* ==========================================================================
   When the nodes lose each other - split brain (1.0.218, docs/split-brain.md)
   ==========================================================================
   One card on High availability: what the two nodes do now, who answers while
   they cannot reach each other (three choices drawn as cards), what else holds
   meanwhile (four switches), and a table of what happens in each kind of
   failure - worked out from the choices as they are made, before saving. The
   choices wait for the save bar at the bottom, as every other setting. */
var SPLITC = {view: null, draft: null, tried: null, timer: null};
var SPLITC_MODES = [
  {k: 'off', icon: 'net', t: 'As until now: both nodes go on',
   s: 'Each node goes on alone and answers everything. With every switch below off nothing of this runs at all - no question to the other node, no arbiter, nothing written: exactly as before.',
   good: ['Nobody is ever turned away while one node answers'],
   bad: ['A code may be let in on both halves', 'The wrong tries are counted on each half apart',
         'Changes made on each half go their own way']},
  {k: 'arbiter', icon: 'globe', t: 'The node that still sees the network',
   s: 'Each node asks its arbiter - its default gateway, or an address given. The node that reaches neither the other node nor its arbiter is the one cut off: it steps aside.',
   good: ['A node cut off from the network stops at once', 'A node really gone: the other goes on alone'],
   bad: ['When only the link between the two nodes breaks, both still answer']},
  {k: 'priority', icon: 'pin', t: 'Only the preferred node',
   s: 'While they cannot reach each other only the preferred node answers; the other steps aside.',
   good: ['Never two halves answering'],
   bad: ['If the preferred node itself is gone, nobody answers until it is back - or this is changed']}
];
var SPLITC_OPTS = [
  {k: 'split_scratch', icon: 'key', t: 'Recovery codes only with the other node asked',
   s: 'A recovery code is used up for good: while the other node cannot be asked whether it was used there, it is refused - and not counted as wrong. The codes of the app keep working.'},
  {k: 'split_halve', icon: 'lock', t: 'Half the tries while apart',
   s: 'The pause after wrong codes and the lockout come after half their tries on each node - both halves together then allow what one node does.'},
  {k: 'split_freeze', icon: 'edit', t: 'Changes only on the preferred node while apart',
   s: 'On the other node the pages show everything and change nothing (tokens, clients, settings) until the nodes see each other again - nothing goes two ways. This card can always be changed.'},
  {k: 'split_report', icon: 'bell', t: 'Warn while apart, report afterwards',
   s: 'An alert while the nodes cannot reach each other; once together again, a report of the codes let in without the other node asked - and of any let in on both.'}
];

function loadSplit(ha) {
  var card = $('ha-split-card');
  if (!card) return;
  var cluster = !!(ha && ha.mode);
  card.hidden = !cluster;
  if (!cluster) return;
  api('split').then(function (v) {
    SPLITC.view = v;
    if (!SPLITC.draft) SPLITC.draft = splitFresh(v);
    drawSplit();
  }).catch(function () { /* the card stays as it was */ });
}
function splitFresh(v) {
  var c = v.conf || {}, arb = {};
  (v.nodes || []).forEach(function (n) { arb[n.name] = n.arbiter || ''; });
  return {mode: c.split_mode || 'off', prefer: c.split_prefer || '', after: Number(c.split_after_s) || 20,
          split_scratch: !!Number(c.split_scratch), split_halve: !!Number(c.split_halve),
          split_freeze: !!Number(c.split_freeze), split_report: !!Number(c.split_report),
          arb: arb};
}
function splitChanged() {
  var a = SPLITC.draft, b = splitFresh(SPLITC.view || {});
  return JSON.stringify(a) !== JSON.stringify(b);
}
function splitTouched(noDraw) {
  if (splitChanged()) {
    pendingSet('split', {pane: 'ha', save: splitSave, reset: function () { SPLITC.draft = null; SPLITC.tried = null; loadSplit({mode: 1}); }});
  } else if (PENDING.split) { delete PENDING.split; markDirtyCount(); }
  if (!noDraw) drawSplit();
}
function splitArbTried() {
  /* The arbiters as they are in the form, each node's answer good. */
  var t = SPLITC.tried, d = SPLITC.draft;
  if (!t || !t.done) return false;
  return Object.keys(d.arb).every(function (n) {
    return t.asked[n] === d.arb[n] && t.got[n] && t.got[n].verdict === true;
  });
}
function splitSave() {
  var d = SPLITC.draft, v = SPLITC.view || {}, c = v.conf || {};
  if (d.mode === 'arbiter' && c.split_mode !== 'arbiter' && !splitArbTried()) {
    toast('Try the arbiter from every node first: a node that cannot reach its arbiter would step aside the moment the other is away', 'bad');
    var b = $('split-try'); if (b) b.scrollIntoView({block: 'center'});
    return Promise.resolve(false);
  }
  var arbChanged = {};
  (v.nodes || []).forEach(function (n) { if ((n.arbiter || '') !== d.arb[n.name]) arbChanged[n.name] = d.arb[n.name]; });
  var body = {action: 'save', checked: d.mode !== 'arbiter' || splitArbTried() || c.split_mode === 'arbiter',
              conf: {split_mode: d.mode, split_prefer: d.prefer, split_after_s: d.after,
                     split_scratch: d.split_scratch ? 1 : 0, split_halve: d.split_halve ? 1 : 0,
                     split_freeze: d.split_freeze ? 1 : 0, split_report: d.split_report ? 1 : 0},
              arbiter: arbChanged};
  return api('split', body).then(function (r) {
    toast(r.message, 'good');
    SPLITC.view = r.view; SPLITC.draft = null; SPLITC.tried = null;
    SPLITC.draft = splitFresh(r.view);
    drawSplit();
    return true;
  });
}
function splitTry(btn) {
  var d = SPLITC.draft, asked = JSON.parse(JSON.stringify(d.arb));
  busy(btn, true);
  api('split', {action: 'try', targets: asked}).then(function (r) {
    SPLITC.tried = {id: r.id, asked: asked, got: {}, nodes: r.nodes, done: false};
    var tries = 0;
    var poll = function () {
      api('split', {action: 'poll', id: r.id}).then(function (p) {
        var got = p.nodes || {};
        Object.keys(got).forEach(function (n) { if (got[n]) SPLITC.tried.got[n] = got[n]; });
        var all = (r.nodes || []).every(function (n) { return SPLITC.tried.got[n]; });
        tries += 1;
        if (all || tries > 20) { SPLITC.tried.done = true; busy(btn, false); }
        drawSplit();
        if (!all && tries <= 20) setTimeout(poll, 1000);
      }).catch(function (e) { busy(btn, false); oops(e); });
    };
    setTimeout(poll, 600);
  }).catch(function (e) { busy(btn, false); oops(e); });
}
function splitPreferred() {
  var d = SPLITC.draft, v = SPLITC.view || {};
  if (d.prefer) return d.prefer;
  return v.preferred || ((v.nodes || [])[0] || {}).name || '';
}
/* Each kind of failure, with what each node does and what it costs - from the choices. */
function splitScenarios() {
  var d = SPLITC.draft, v = SPLITC.view || {};
  var names = (v.nodes || []).map(function (n) { return n.name; });
  if (names.length < 2) names = [names[0] || 'node 1', 'the other node'];
  var P = splitPreferred(), A = names.indexOf(P) >= 0 ? P : names[0];
  var B = names.filter(function (n) { return n !== A; })[0];
  var rows = [];
  var serve = {k: 'ok', w: 'answers'}, aside = {k: 'warn', w: 'steps aside'},
      gone = {k: 'dim', w: 'gone'}, cut = {k: 'dim', w: 'cut off'};
  var twice = [];
  if (!d.split_scratch) twice.push('a recovery code may pass on both');
  twice.push('an app code may pass on both within its 30 s');
  if (!d.split_halve) twice.push('twice the wrong tries');
  if (!d.split_freeze) twice.push('changes on both halves go two ways');
  var safe = function (w) { return {k: 'ok', w: w}; }, risk = function (w) { return {k: 'warn', w: w}; },
      down = function (w) { return {k: 'crit', w: w}; };
  /* The other node really gone. */
  [[A, B], [B, A]].forEach(function (pair) {
    var dead = pair[0], left = pair[1];
    var leftDoes = (d.mode === 'priority' && left !== A) ? aside : serve;
    var cells = {}; cells[dead] = gone; cells[left] = leftDoes;
    rows.push({t: dead + ' is switched off or fails', cells: cells,
               out: leftDoes === serve ? safe(left + ' answers everything') : down('nobody answers until ' + dead + ' is back'),
               risk: leftDoes === serve ? safe('none') : down('no sign-ins')});
  });
  /* One node cut off from the network (clients and arbiter out of its reach too). */
  [[A, B], [B, A]].forEach(function (pair) {
    var off = pair[0], left = pair[1];
    var offDoes, leftDoes;
    if (d.mode === 'arbiter') { offDoes = aside; leftDoes = serve; }
    else if (d.mode === 'priority') { offDoes = off === A ? cut : aside; leftDoes = left === A ? serve : aside; }
    else { offDoes = cut; leftDoes = serve; }
    var cells = {}; cells[off] = offDoes; cells[left] = leftDoes;
    var ok = leftDoes === serve;
    rows.push({t: off + ' loses the network', cells: cells,
               out: ok ? safe(left + ' answers everything') : down('nobody reachable answers'),
               risk: !ok ? down('no sign-ins') : (offDoes === aside ? safe('none') : risk(['whatever still reaches ' + off + ':'].concat(twice)))});
  });
  /* Only the link between them. */
  var linkA = serve, linkB = serve;
  if (d.mode === 'priority') linkB = aside;
  var cells = {}; cells[A] = linkA; cells[B] = linkB;
  rows.push({t: 'Only the link between the two breaks (both still see the network)', cells: cells,
             out: safe(linkB === aside ? A + ' answers everything' : 'both answer'),
             risk: linkB === aside ? safe('none') : risk(twice)});
  return {rows: rows, A: A, B: B};
}
/* Drawn again where it is (1.0.220): emptied for a moment, the pane was short and a
   switch clicked half-way down sent the page to the top. */
function drawSplit() {
  var host_ = $('ha-split'), held_ = host_ ? scrollHeld(host_) : null;
  var r_ = drawSplitIn();
  if (held_) scrollBack(held_);
  return r_;
}
function drawSplitIn() {
  var host = $('ha-split');
  var v = SPLITC.view, d = SPLITC.draft;
  if (!host || !v || !d) return;
  var may = !!ADMIN;
  var st = $('ha-split-state');
  var apart = (v.nodes || []).some(function (n) { return n.fresh && n.state && n.state.apart; });
  if (st) {
    clear(st);
    if (!v.active) st.appendChild(el('span', 'tag dim', 'one database - nothing to choose'));
    else if (!v.engaged) st.appendChild(el('span', 'tag dim', 'as until now - not watched'));
    else st.appendChild(el('span', 'tag ' + (apart ? 'crit' : 'ok'), apart ? 'apart now' : 'together'));
  }
  clear(host);
  if (!v.active) {
    host.appendChild(el('p', 'note', 'Both nodes open one database: whatever one node writes the other sees at once, so a code can never be let in twice, and the nodes cannot go two ways. Nothing here is needed - this is for two nodes that replicate.'));
    return;
  }
  /* ---- now ---- */
  var now = el('div', 'split-now');
  (v.nodes || []).forEach(function (n, i) {
    var s = n.state || {};
    var tile = el('div', 'split-node' + (s.role === 'aside' ? ' aside' : '') + (n.fresh ? '' : ' stale'));
    var top = el('div', 'split-node-top');
    top.appendChild(noI18n(el('b', '', n.name)));
    if (n.me) top.appendChild(el('span', 'tag dim', 'this page'));
    if (n.name === splitPreferred()) top.appendChild(el('span', 'tag violet', 'preferred'));
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
      tile.appendChild(el('div', 'muted small', 'nothing is watched - as before: it goes on alone whatever happens to the other'));
    } else if (n.fresh) {
      line(!s.apart, s.apart ? 'cannot reach the other node' : 'reaches the other node',
           s.apart ? '(' + ago(s.since) + ')' : '');
      var arbs = s.arbiters || [];
      if (arbs.length) arbs.forEach(function (a) { line(a.ok, 'arbiter', a.target + (a.words ? ' - ' + a.words : '')); });
      else line(null, 'arbiter: ' + (s.gateway ? 'its gateway ' + s.gateway : 'none - no default gateway'));
      if (s.why && s.apart) tile.appendChild(el('div', 'split-why muted small', s.why));
      if (s.frozen) tile.appendChild(el('div', 'split-why small', 'changes on the pages wait here'));
      if (s.halved) tile.appendChild(el('div', 'split-why small', 'half the tries'));
    } else {
      tile.appendChild(el('div', 'muted small', n.alive ? 'its word has not come over yet' : 'nothing heard from it - it is down, or the link is'));
    }
    now.appendChild(tile);
    if (i === 0 && (v.nodes || []).length > 1) {
      var link = el('div', 'split-link ' + (apart ? 'broken' : 'whole'));
      link.innerHTML = iconMarkup(apart ? 'close' : 'net', 18);
      link.appendChild(el('span', 'small', apart ? 'apart' : 'together'));
      now.appendChild(link);
    }
  });
  host.appendChild(now);
  /* ---- who answers ---- */
  host.appendChild(el('h4', 'split-h', 'Who answers while they cannot reach each other'));
  var choices = el('div', 'split-choices');
  SPLITC_MODES.forEach(function (m) {
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
    b.onclick = function () { d.mode = m.k; splitTouched(); };
    choices.appendChild(b);
  });
  host.appendChild(choices);
  var asBefore = d.mode === 'off' && !d.split_scratch && !d.split_halve && !d.split_freeze && !d.split_report;
  var said = el('p', 'split-said ' + (asBefore ? 'same' : 'new'));
  said.innerHTML = iconMarkup(asBefore ? 'check' : 'info', 15);
  said.appendChild(el('span', '', asBefore ? 'Exactly as before 1.0.218: nothing of this runs.'
    : (d.mode === 'off' ? 'Both nodes go on; the switches below hold while they are apart - the other node\u2019s database is watched for it.'
                        : 'The other node\u2019s database is watched every two seconds.')));
  host.appendChild(said);
  /* ---- its details ---- */
  var g = el('div', 'set-grid split-fields');
  var names = (v.nodes || []).map(function (n) { return [n.name, n.name]; });
  var pref = selectBox([['', 'the first node (' + (v.preferred || '?') + ')']].concat(names), d.prefer);
  pref.disabled = !may;
  pref.onchange = function () { d.prefer = pref.value; splitTouched(); };
  var pf = formField('The preferred node', pref, 'Answers alone with Only the preferred node; the only node where changes are made while apart; makes the report afterwards.');
  if (d.prefer !== ((v.conf || {}).split_prefer || '')) pf.classList.add('changed');
  g.appendChild(pf);
  var after = textBox(String(d.after), '20', '');
  after.type = 'number'; after.min = 5; after.max = 300; after.disabled = !may;
  after.onchange = function () { d.after = Math.max(5, Math.min(300, Number(after.value) || 20)); splitTouched(); };
  var af = formField('Apart after (seconds)', after, 'How long the other node’s database must not answer before the nodes count as apart. Shorter: sooner safe; longer: a short hiccup of the network changes nothing.');
  if (d.after !== Number((v.conf || {}).split_after_s || 20)) af.classList.add('changed');
  g.appendChild(af);
  host.appendChild(g);
  if (d.mode === 'arbiter') {
    var box = el('div', 'split-arb');
    box.appendChild(el('p', 'note', 'Each node’s arbiter: what it asks to tell “the other node is gone” from “I am the one cut off”. Empty: its default gateway. Addresses are pinged; name:port is tried over TCP instead (for a network that drops ping). Up to five, any one answering is enough. Give something both nodes reach by different ways than they reach each other - the router, the VPN concentrator.'));
    var ag = el('div', 'set-grid');
    (v.nodes || []).forEach(function (n) {
      var s = n.state || {};
      /* Its placeholder put in the page's language (the value never is). */
      var t = textBox(d.arb[n.name] || '', s.gateway ? 'its gateway ' + s.gateway : 'its default gateway', 'mono');
      t.disabled = !may;
      /* Typed into without the card drawn again (the cursor stays); drawn when left. */
      t.oninput = function () { d.arb[n.name] = t.value.trim(); SPLITC.tried = null; splitTouched(true); };
      t.onchange = function () { drawSplit(); };
      var f = formField('Arbiter of ' + n.name, t);
      if ((n.arbiter || '') !== (d.arb[n.name] || '')) f.classList.add('changed');
      ag.appendChild(f);
    });
    box.appendChild(ag);
    var row = el('div', 'btnrow');
    var tb = cmdButton('Try it from every node', 'pulse', '');
    tb.id = 'split-try';
    tb.disabled = !may;
    tb.onclick = function () { splitTry(tb); };
    row.appendChild(tb);
    if (splitArbTried()) row.appendChild(el('span', 'tag ok', 'every node reaches its arbiter'));
    else if (SPLITC.tried && SPLITC.tried.done) row.appendChild(el('span', 'tag crit', 'not every node reaches its arbiter'));
    else if ((v.conf || {}).split_mode !== 'arbiter') row.appendChild(el('span', 'small muted', 'needed before saving'));
    box.appendChild(row);
    if (SPLITC.tried) {
      var res = el('div', 'split-tried');
      (SPLITC.tried.nodes || []).forEach(function (n) {
        var got = SPLITC.tried.got[n];
        var r = el('div', 'split-line ' + (!got ? 'muted' : got.verdict === true ? 'good' : 'bad'));
        r.innerHTML = iconMarkup(!got ? 'clock' : got.verdict === true ? 'check' : 'close', 14);
        r.appendChild(noI18n(el('b', '', n + ': ')));
        if (!got) r.appendChild(el('span', '', 'asking…'));
        else (got.targets || []).forEach(function (x) {
          r.appendChild(noI18n(el('span', 'mono small', x.target + ' ')));
          r.appendChild(el('span', 'small', x.ok === true ? 'replies' : x.ok === false ? 'no answer' : 'cannot be asked'));
          if (x.words) r.appendChild(el('span', 'small muted', ' (' + x.words + ') '));
        });
        if (got && !(got.targets || []).length) r.appendChild(el('span', 'small', got.error || 'no arbiter: no default gateway - give one'));
        res.appendChild(r);
      });
      box.appendChild(res);
    }
    host.appendChild(box);
  }
  /* ---- while apart ---- */
  host.appendChild(el('h4', 'split-h', 'And while they are apart'));
  var opts = el('div', 'split-opts');
  SPLITC_OPTS.forEach(function (o) {
    var item = el('div', 'split-opt' + (d[o.k] ? ' on' : ''));
    var sw = switchBox(d[o.k]);
    sw._input.disabled = !may;
    sw._input.onchange = function () { d[o.k] = !!sw._get(); splitTouched(); };
    var ic = el('span', 'split-ic'); ic.innerHTML = iconMarkup(o.icon, 18);
    var txt = el('div', 'split-opt-txt');
    txt.appendChild(el('div', 'split-opt-k', o.t));
    txt.appendChild(el('div', 'split-opt-s', o.s));
    item.appendChild(ic); item.appendChild(txt); item.appendChild(sw);
    if (!!Number((v.conf || {})[o.k] === undefined ? (o.k === 'split_report' ? 1 : 0) : (v.conf || {})[o.k]) !== d[o.k]) item.classList.add('changed');
    opts.appendChild(item);
  });
  host.appendChild(opts);
  /* ---- what happens ---- */
  var sc = splitScenarios();
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
    /* Each piece a sentence of its own, so that each is put in the page's language. */
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
  /* ---- the last report ---- */
  var rep = v.report;
  if (rep && rep.at) {
    var p = el('div', 'split-report ' + (rep.twice_n ? 'bad' : 'good'));
    p.innerHTML = iconMarkup(rep.twice_n ? 'flag' : 'check', 16);
    var words = el('span');
    words.appendChild(el('b', '', 'The last time apart'));
    words.appendChild(noI18n(el('span', '', ' (' + stamp(rep.since) + ' - ' + stamp(rep.at) + ') ')));
    var taken = Object.keys(rep.taken || {}).map(function (n) { return n + ': ' + num(rep.taken[n]); }).join(', ');
    words.appendChild(el('span', '', 'codes let in without the other node asked:'));
    words.appendChild(noI18n(el('span', '', ' ' + (taken || '0') + ' · ')));
    words.appendChild(el('span', '', 'let in on both:'));
    words.appendChild(noI18n(el('span', '', ' ' + num(rep.twice_n || 0))));
    if ((rep.twice || []).length) words.appendChild(noI18n(el('span', 'mono small', ' - ' + rep.twice.map(function (x) { return x.name + ' (' + x.kind + ')'; }).join(', '))));
    p.appendChild(words);
    host.appendChild(p);
  }
  dressButtons(host);
}
```

## 12. Porting it to another application - checklist

For an application with the same kind of cluster (two nodes, each its own database
replicating both ways, a shared settings store, an admin page with a save bar):

- [ ] **Settings** of 3 with their ranges; `split_arbiter` per node.
- [ ] **The watch** (4): a thread, 2 s; a connection of its own to the other node's
      database with short timeouts, the question waited for in a helper thread; `apart`
      after `split_after_s`; events on both transitions; the state row every 10 s.
      Replace "the other node's database" with whatever the application asks before it
      lets a one-time thing through - "apart" must mean exactly "that check cannot be done".
- [ ] **The arbiter** (5): `host:port` over TCP (refused counts as reached), else ICMP via
      a datagram socket, a raw socket, `ping`; "cannot be asked" never steps a node aside.
      The default gateway from `/proc/net/route`.
- [ ] **The decision** (6) as a pure function - test it alone.
- [ ] **Stepping aside** through the one gate the application already has for
      maintenance (the service stops answering, the VIP/health check fails, the pages
      stay). Flush that gate's cache on every change of role.
- [ ] **Recovery codes / one-time things that live long**: refuse while apart or while the
      other cannot be asked - before anything is written, not counted as a failure.
- [ ] **Limits**: every read of a "tries before pause/lockout" setting through
      `split_limit()`.
- [ ] **Freeze**: one check in the API dispatcher, before the route, POST only, with the
      list of what stays allowed (sign-in, this card, the cluster, maintenance, restarts).
- [ ] **Report**: write down what was let in while the other could not be asked (keyed so
      that the same thing on both nodes has the same key), compare after together on one
      node, keep the last report, alert.
- [ ] **Alerts**: one problem per node apart, one for "let in on both" (24 h).
- [ ] **API** of 9 (GET view, POST save/try/poll), the try made by every node for itself.
- [ ] **The page's relay passes it on**: in otp's `web/admin/index.php` the name `split` is in
      both `$reads` and `$writes` (`'split' => '/api/split'`). Without it the card shows its
      title and nothing else (otp 1.0.218 shipped so; 1.0.219 mended it) - test the card
      through the real relay, not with its view handed to it.
- [ ] **The card** of 11: HTML, CSS, JS as they are; the helpers of 11.6 mapped to the
      application's own; the texts of 11.3 into its translation files.
- [ ] **Docs**: this file.
- [ ] **Tests** of 13, the cluster ones with the network really cut (iptables).

## 13. Tests

**In one process** (`tests/split/t_split.py`, SQLite, the other node and the arbiter played
by the test - `split_step(store, now, peer=True|'error words', arbiter=True|False|None)`):

- the decision of every mode (together always serves; off; priority; arbiter reached / not
  / cannot be asked);
- "as until now" is the default, and in it nothing runs: the other node never asked, never
  apart, no row written, no limit changed, nothing frozen, no alert, no maintenance;
- one node or one shared database: never apart;
- priority: 5 s of 20 not apart; 30 s apart and aside; `maintenance_now()` says it
  (`split: true`); the state row; together again serves; the preferred node serves while
  apart;
- arbiter: reached serves, lost steps aside, back serves;
- half the tries: 10 → 5 and 3 → 2 while apart; five wrong codes lock at half;
- freeze: a POST refused on the non-preferred node, GET / sign-in / the card not; the
  preferred node goes on; together nothing frozen;
- recovery codes: refused apart (not counted, not used up); refused together when the
  other cannot be asked this moment; let in when asked;
- the report: a code let in without the other asked is written down; the same on the
  other node's row → found as twice, kept, rows gone, alert;
- the alert while apart;
- the arbiter: TCP listening / refused (reached) / silent (not); ping of 127.0.0.1;
  the parser (addresses, name:port, [v6]:port, bare v6, five at most); the gateway;
- the API: the view; arbiter without try refused; save of mode, preferred node, a switch,
  each node's arbiter; a bad arbiter refused; the card's pieces on the pages.

**On the two-node sandbox** (`tests/hasb/full/t_ha_split.py`), the link cut with iptables
(the replication and the direct question both go over it):

- together: both state rows "serve", no alert;
- link cut, mode off: both apart after `split_after_s`, both serve, alerts on both;
- mode priority: the other node steps aside (RADIUS silent there, the preferred answers),
  heals by itself when the link is back;
- mode arbiter with each node's own arbiter (two TCP listeners): a node whose arbiter is
  gone steps aside, the other serves; arbiter back - serves again;
- recovery code refused while apart on both; half the tries; a change refused on the
  non-preferred node;
- the report after the heal: a TOTP code let in on both halves while apart found by name;
- nothing left behind: settings back, the link whole, replication running.

## 14. For the administrator

**Which to choose**

- *As until now: both nodes go on* (the default) - with every switch off nothing runs,
  exactly as before 1.0.218. Keeping the mode but switching on *Warn while apart, report
  afterwards* and *Recovery codes only with the other node asked* is the gentlest step: the
  nodes still both go on, but you learn of a split and recovery codes are safe.
- *The node that still sees the network* - the usual choice when each node has a default
  gateway (or the VPN concentrator) it reaches by the network, not by the other node. A
  node cut off from the network goes silent by itself; a node really dead does not stop
  the other. Add *Half the tries* and *Recovery codes only…* for the case where only the
  link between the nodes breaks.
- *Only the preferred node* - when two answering halves must never happen and a person is
  there to change it if the preferred node dies for long (switch the mode to *Both nodes go
  on*, or make the other node preferred - the card can always be changed, even frozen).

**Before choosing the arbiter mode**: *Try it from every node*. Each node must reach its
arbiter. A network that drops ping: give `host:port` of something listening (the router's
HTTPS, the VPN concentrator's 443, a DNS server's 53).

**While apart** (the card says *apart now*, an alert came):

1. Look at the two tiles: which node cannot reach the other, which reaches its arbiter,
   which answers.
2. Mend the link (the replication's port 5432 both ways, the network between the nodes).
3. They find each other within two seconds of the other database answering; the node that
   stepped aside answers again by itself; the report comes 30 s later.
4. Read the report: a code *let in on both* means one person's code was accepted twice -
   usually a retry of the VPN to the other node, rarely an attacker who had the code.

**What it does not do**: tell "the link broke" from "the other node died" with no arbiter
(nothing can, with two nodes); hold the VIP address on one node only when VRRP cannot pass
(the node that steps aside lets it go; one that serves keeps it); protect a cluster of one
shared database (it needs none).
