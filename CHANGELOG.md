# otp — what changed

Every change is a new version: the number is in `otp.py` (`otp --version`),
on the pages (bottom of the enrolment page, Settings → About), in the name of
the folder and of the archive.

## 1.0.151 — 29 October 2026

**The space between cards**
- A card drawn after a block of cards with a holder of its own (Network:
  *New settings* and *Taken back unless kept*) touched it: the space between
  cards now holds there too. Every pane and tab of the administration was
  measured for it.

## 1.0.150 — 29 October 2026

**Settings where they belong**
- *A new network goes back unless kept within* is on Settings → Network, and
  *A firewall change goes back unless kept within* on Settings → Firewall and
  access, each under *Taken back unless kept* - not on Sign-in protection.

**RADIUS keeps its pace while the server works**
- The daemon's copies of the database - *Back up now*, the copy before a
  restore or an upgrade, the backups sent to the destinations - are made by a
  process of their own (`otp --dump-copy`): made in the daemon, a big copy
  took a third of RADIUS's pace for minutes. Measured: 364 answers a second,
  none lost, p99 345 ms while a 700 000-row copy was made.
- RADIUS has four connections of its own to PostgreSQL and MariaDB (it had
  one): every sign-in waited for the one before it there, and one row held
  by a lock held them all.
- *Give the disk back* (VACUUM FULL, OPTIMIZE) in a cluster puts this node
  out of RADIUS meanwhile - the other node answers; alone, the page says that
  sign-ins wait for it.

## 1.0.149 — 29 October 2026

**Back up now on every node of a cluster**
- Settings → Backups → *Back up now* makes the backup of every node, as the
  schedule does: the node the page is on at once, the other within a minute
  (each node its own backup to every destination). A backup to chosen
  destinations only stays this node's.

**A deep look at security, failures and load: what was found is fixed**

*Security*
- The command line run as root (the root console's *What is in it* and
  *Put it back* on a listed backup among others) copied the file named into a
  folder already the otp account's: a link planted in the backups folder let
  that account read any file of root's, and one put into the folder during
  the copy had root overwrite any file. A file the otp account can reach is
  now opened by that account itself; any other is copied by its descriptors
  into a folder of root's, handed over only once it is filled. Going back
  below 1.0.149 is refused from now on.
- The console's *Upgrade this node from a package* runs a package through
  root's upgrade helper - its signature checked before anything of it is
  unpacked or run; a folder only when it is root's alone, said as unchecked.
  The console's live log no longer follows a link nor hangs on a FIFO.
- Root's helper changes pg_hba.conf, its copies and the database link's
  certificate in PostgreSQL's folders by descriptor, never by name: whoever
  runs as postgres could have pointed a name at a file of root's.
- A test of somebody's sign-in tries a person's password 5 times in 15
  minutes at most (it was 80 in 5); a test sent to another RADIUS server needs
  that server's secret - this machine's own is used for 127.0.0.1 only.
- The second step of the administrators' sign-in hands a new session once
  given; switching it on ends the other sign-ins already open. Errors say
  the directory's and the database's details only to an administrator past
  the second step.
- A remote backup destination moved to another server needs its password
  typed again: *Try it* sent the saved one to the new server.
- A realm keeping its tokens under the name alone - bare, or with the
  suffix `*` or none - next to such a realm of another directory is refused:
  one person's token signed in the other directory's account of that name.
- Recovery codes rest after 20 wrong tries from one place, and for everybody
  only after 100 from everywhere: a stranger who knew a name could switch off
  that person's recovery codes for a day.
- nginx without auth_request takes no upload over 32 MB (it took 4 GB from
  anybody on the allow list before the page could refuse it).

*Always answering, never refusing the right people*
- A database that is there but does not answer - locked, full, a statement or
  a lock wait run out - is now treated as one gone: no answer, so the VPN asks
  the other node. It refused everybody with a right code.
- RADIUS's own connection to PostgreSQL and MariaDB waits 8 s for a statement
  and 3 s for a lock (it was 120 s and 10 s): past that the request is left
  unanswered instead of holding every sign-in behind it.
- Putting a backup back puts the node into maintenance for the whole of it:
  the VPN asks the other node instead of waiting or being refused.
- A copy or a dump is not made when it would fill the disk under the
  database (128 MB and the database's size must stay free).
- Sign-in protection forgets places no longer counted, and publishes the
  blocked and the busiest 500 only: many IPv6 /64s grew memory and the list
  shared between the nodes without end.
- The first sign-in of a directory administrator in a cluster is made by
  one node only: on both at once replication stopped on a duplicate.
- A client that signs its requests is held to it also when the database
  does not answer just then (the request is not answered).
- A mail or SMS token put back from a token backup takes its recovery codes
  again.

*Under load, with a slow or half-dead directory*
- A directory server that takes the connection but leaves its searches
  unanswered is passed over for 30 s and the next server asked, as one that
  does not connect: it held every RADIUS worker, realms without a directory
  too, and the second server was never asked.
- One directory takes at most half of the RADIUS workers at once; a request
  past that is refused at once as the directory's trouble - a slow directory
  no longer stops the realms that do not ask it.
- A request waiting longer than 10 s (it was 15) is not worked on: the VPN
  has asked again or asked the other node by then.
- RADIUS's own connection to the database: PostgreSQL and MariaDB give up a
  statement after 5 s and a lock wait after 2 s, SQLite a busy file after
  3 s - then no answer, never a refusal.
- Old log rows are taken away 1000 at a time with a pause between, and
  SQLite's write-ahead log is cut back after it and kept under 64 MB.

## 1.0.148 — 29 October 2026

**The console at login: no "on" beside the switch**
- Settings → About → *The console at login*: the switch alone shows on or
  off; words beside it only while a node is being switched or has not said
  yet.

## 1.0.147 — 29 October 2026

**The console at login: saved with the save bar**
- Settings → About → *The console at login*: the switch only shows what it
  will be and waits on the save bar at the bottom, as every other setting -
  the node is switched by *Save the changes*, not at the click; *Put them
  back* takes it back.

**More bugs fixed**

*High availability*
- What one node does for both - the hourly tidying, the repair of the database link's
  certificates and a new authority for it when the old one nears its end, putting back a
  firewall change not kept - is now done by one node alone: the first by
  name of the nodes heard from. Both nodes used to write the row for it, and
  when both made it at once, replication stopped on a duplicate key.
- *Encrypt the link* and *switch it off* tell the other node only over a row
  it already has; a row new on both nodes at once stopped replication.

*Sign-in and codes (fixes of 1.0.146's own changes)*
- The count of wrong passwords per name could be got round on the pages'
  and the portal's sign-in with a name such as `a>CORP\novak` - each prefix
  counted on its own. Only the administrators' tests keep their own count now.
- Requests at the same moment no longer get more codes sent than
  `code_send_max`: the limit is checked again as the send is written.
- A number dialled at home with its 0 is never taken as one with its
  country code (`0491 12345678` with +49 stays +49 491 12345678).
- "The recovery codes are not taken for a day" is written also when two
  nodes counted past the limit at once.

*Network*
- A change of the network waiting for a restart that never comes is given
  up after an hour: checked where the new address is on the machine all the
  same, else the other node gets this one's address back, maintenance ends,
  and restart / power off and new changes work again. Telling the other
  node runs on the network's own thread.

*Backups*
- Putting a backup back keeps who is signed in now: the sign-ins in the
  copy came back with it - one signed out since opened the pages again.
- A settings file without the secrets keeps the key of the pages'
  certificate only where it belongs to the certificate in the file; beside
  another certificate nginx would not start. It says which came without it.

*Install*
- config.json of a new install is made with its owner and mode set on the
  open file, never by name - the otp account can no longer swap a link in
  between the steps.
- `--python PATH` and `--system-python` are remembered: the next upgrade -
  from the pages too - tries that Python first instead of the newest.

*Logs and SMS*
- An error of the minute's work (the upgrade, the web address, a new
  address, the cluster's history) is written once an hour while it stays
  the same, not every minute.
- An SMS gateway that answers with the text it was sent no longer puts the
  code into the events and the log.

## 1.0.146 — 29 October 2026

**A second deep look through the whole program: bugs fixed**

*RADIUS and the codes*
- Two nodes no longer write the same row for "a code was just sent" and the
  recovery-code guard: each node keeps its own row (`NAME@@NODE`), so
  logical replication never stops on a duplicate key.
- Sign-in protection: a single trusted IPv6 address trusts its /64 (requests
  are told apart by their /64); a directory that could not be asked is the
  server's trouble, not a guess, and is not counted against the place.
- A phone number written as `420603123456` (country code, no +) is no longer
  made `+420420603123456`.
- The Teltonika debug log no longer holds the text of an SMS with its live
  code.

*Realms, clients, directories*
- Taking away a realm that a client takes alone is refused (that client would
  have taken every realm); the import that replaces everything switches such
  clients off instead.
- A directory renamed keeps its realms (any case) and the administrators'
  sign-in directory; the one administrators sign in against cannot be taken
  away. Saving a client, realm or directory someone else just took away says
  so instead of making a new one; switches sent as text are read as on/off.
- Taking away an administrator account takes its second step with it - a new
  account of the same name starts without it.
- The command line keeps a client's, realm's or directory's on/off, position
  and timeout when it saves one again, writes those changes to the events,
  and no longer takes an abbreviated option for another.

*Pages and API*
- A request on a kept-alive connection no longer reads the previous one's
  body; a database fault says only "cannot be reached" to someone not signed
  in.
- Settings import: firewall rules of a node this machine does not have are
  left out (and said) instead of stopping the import; per-node settings are
  kept after the shared ones.
- Token files with a name `/` or `\` cannot be written (export and import
  quote it); token imports refuse names the program would not make.
- The firewall trial's first change keeps the rules as they were to go back
  to; a token administrator is no longer shown a firewall page that fails.
- Online upgrade: an address that does not answer, a package cut off or a
  check that takes too long is said, not an error 500. A package to go back
  to cannot be started from the pages once going back is switched off.
- Certificate lists (mail server, SMS gateway, directory): adding nothing
  no longer empties the list; only *Take all away* does.
- Moving a firewall rule up or down is written to the events.
- Network trial: a reboot the root helper did not answer is waited for, a
  failed job puts the other node's address back and leaves maintenance; a
  job stalled past its time is said.
- The portal says plainly when no way of getting codes is open for the
  account.

*Install, console, backups*
- install.sh writes config.json in place of a link only by replacing it;
  `--uninstall --yes` without a terminal refuses instead of doing nothing;
  Ctrl+C during an upgrade rolls it back as a failure; chrony's config is found
  on Debian too.
- The console: packet text shown without colour is made safe, the token list
  is no longer cut at 1000, *Install from package* checks the version in the
  package's otp.py; `--upgrade-follow` keeps its progress line.
- Old FreeRADIUS import: a `#` inside quotes is kept, a block inside a client
  (`limit { }`) no longer ends it, and one client it cannot take no longer
  stops the rest.
- The scheduled remote backup is not skipped for the day when the database
  was away at that minute; folders a stopped backup or restore left behind
  are taken away at start (6 hours old); SFTP/SCP to an IPv6 address works.

## 1.0.145 — 29 October 2026

**Going back: the list of versions tidied**
- Each version one row - the version and *yes* on the left, *What changed* and
  *Go back to X* side by side on the right; on a narrow screen the buttons go
  below as a whole instead of being squeezed.
- The versions it may not go back to are folded below, the reasons said once
  there, each version with a short word (*below 1.0.139*; the whole reason when
  the pointer rests on it) - a long reason no longer stretches every row.

## 1.0.144 — 29 October 2026

**Going back to an older version: switched on in Settings, with what changed**
- Settings → Upgrades → *Offer going back to an older version*
  (`upgrade_downgrade`), off by default: off, the pages show nothing of going
  back and the API refuses it; on, the card *Going back to an older version*
  is there. On the server, root can always: `otp --downgrade`.
- Each version in its list has *What changed*: what came in it, and - folded
  - what going back to it gives up, the versions after it up to this one.
  Read from the CHANGELOG.md installed beside otp.py (install.sh puts it there
  now), or from the package at the address where it is not there.

## 1.0.143 — 29 October 2026

**Going back to an older version - only a safe one**
- Settings → Upgrades → *Going back to an older version*, `otp --downgrade
  VERSION|FILE` (and `--downgrade-check`), the console's Upgrades → *Go back
  to an older version*. Never by putting the database back: the tables stay as
  they are, whatever their size, and the older version runs on them.
- Refused below the highest floor (`DOWNGRADE_FLOOR`, now 1.0.139) of any
  version that ran on this database (kept per node in the database) and of any
  installed on this machine (`/usr/local/lib/otp/downgrade-floor`, root's
  alone - the otp account cannot lower it, so the server cannot be taken back
  to a version with a fixed hole); and when the database has a NOT NULL column
  without a default that the older version does not know.
- The package is checked as an upgrade's; the nodes go back one at a time,
  each in maintenance, as in an upgrade. Root's helper puts an older version
  in only when going back is asked for, and never below its floor.
- The console's *Upgrade this node from a package file* refuses an older
  package and points to going back.

## 1.0.142 — 29 October 2026

**From the web: choose the version to go to**
- Settings → Upgrades → From the web: with more than one version at the
  address newer than the one running, a list beside the buttons lets you choose
  which one *Upgrade to X now* and *Only fetch it* take - the newest is chosen.
  With only one newer version the page is as before. Each is checked as before
  (its signature, every file); an older one is never offered nor taken.

## 1.0.141 — 28 October 2026

**The console at login, switched on the pages**
- Settings → About → The console at login: a switch for each node - on, root
  signing in at the machine's console or over SSH lands in `otp --console`;
  off, the ordinary shell. Full administrators; the node's own root helper
  writes /etc/otp-console-login (as `otp --console-at-login on|off` does), and
  each node says how it is within a minute - a change made on the command line
  shows too. Every switch is written in Events.

## 1.0.140 — 28 October 2026

**A network on trial goes back whole**
- Before a new network is put in on trial, the node keeps what it has: the
  root helper the connection's whole NetworkManager profile (every address -
  the second ones too - routes, MTU, DHCP or set by hand), the host name,
  /etc/hosts and the IPv6 switch; the daemon this node's own settings
  (radius_bind, mail_helo, isemon_hostname, db_host, ha_address) and the
  pages' certificate. Not kept in time, exactly that comes back - until now
  only the first address, the gateway and DNS were asked for again, and the
  certificate and settings were worked out again the other way round.
- A network from DHCP can be put on trial and go back too.
- Going back to a short host name (otp1) is no longer refused by the root
  helper.
- After the reboot - going back or not - the job checks and says, step by
  step: replication both ways, the link between the databases encrypted and
  checked (verify-full) on both nodes with this node's certificate naming its
  address, and the web address (keepalived) set up again.

**High availability**
- `otp --ha-setup` on a node whose daemon never ran yet made a bundle without
  the key that seals the tokens; the second node wrote an empty secrets.key
  and its daemon could not start. The key is made first now, and
  `--ha-join` refuses a bundle without one.

## 1.0.139 — 28 October 2026

**Remote backups are locked with the password you typed** (important)
- Until now the password of the backups was used as it is kept in config.json,
  sealed: the backups were locked with that sealed text, not with the password
  typed on the pages. They opened only on the machine that made them; on a new
  machine (`--restore-bundle`, the page, `openssl enc -d` as RESTORE.md says)
  the password did not open them. Now the password typed locks them.
- Backups made before 1.0.139 still open on the machine that made them (otp
  tries the old way too). **Make a new remote backup after the upgrade**: only
  that one opens anywhere with your password.
- A backup that is not locked is no longer put back where a password is in play
  (one set, or typed): otp never sends one unlocked, so it was put there by
  somebody else.
- SFTP/SCP: with both a password and a key with a passphrase, each prompt gets
  its own answer (the password went to the key, and the key failed). The SCP
  folder takes no characters a shell reads (use SFTP for those).

**Security**
- `otp --ha-setup`: db_name and db_user are checked before they are written
  into pg_hba.conf as root (a value with a space or a new line in config.json
  wrote a line of its own there).
- A token administrator can no longer make a token for a person who has one in
  use under another name RADIUS would then stop using (another suffix of the
  realm, or the same account in another realm on the same directory) - a full
  administrator's to do, as replacing a token is.
- Administrators' second step: a sign-in left waiting from before the account
  set its second step up can no longer set up its own over it.
- The command line and the console: names, reasons and attributes that came in
  a RADIUS packet are shown with their control characters as \xNN - escapes in
  them cleared the screen, set the title or wrote the clipboard of the
  terminal (`otp --log`, `--request`, the console's live views).
- Telling the other node a new address: where the link's certificate names the
  old address, the other node is reached checked by the cluster's authority -
  no longer unchecked, nor in the clear.
- `--add-client` without `--secret` no longer takes OTP_PASSWORD as the shared
  secret (it is OTP_SECRET). `--radtest USER CODE SERVER PORT -` and
  `--bind-pw -` ask for the secret instead of taking it on the command line;
  the help shows these.
- The directory sign-in test on the pages is counted (as a radtest is) and
  written in the events.

**RADIUS**
- A right code is no longer refused because a second answer to the same
  question (a retransmit, or the other node) counted a try meanwhile.
- RADIUS no longer waits for a page saving a setting while that page waits for
  a slow query (`client seen`, written once a minute a client).
- Moving to another database no longer takes RADIUS off its own connection for
  the whole move.
- The short pause after wrong codes works with `rate_limit_tries` above 50;
  sign-in protection works with `radius_guard_tries` above 1000 and
  `radius_guard_names` above 500.
- Sign-in protection: a Calling-Station-Id with a port (203.0.113.5:51234,
  [2001:db8::5]:51234) is counted as its address - it was a new place at each
  connection and never blocked. A code used once already (the same request
  sent to the other node) is not counted as a guess.

**High availability and the network**
- Going back after a network trial works when the old host name is a short one
  (it was refused, and the new network stayed).
- The firewall trial: the row its put-back is claimed by is made when the trial
  starts, by one node - made by both at the moment it ran out, it could stop
  replication.
- TLS between the databases: a password with a ? in it no longer breaks
  switching it on or off, and the password stays out of PostgreSQL's log.
- The change of the addresses and the TLS of the link no longer write over each
  other's request to the root helper.
- Putting a copy back that brings another key: the cluster's authority is
  sealed again with that key (it could not be opened after).

**Smaller**
- The console: letters with accents typed in its windows (passwords too) come
  out as typed; Delete on a token, replacing a token in use (asked first) and
  "Try it (and look somebody up)" on a directory work; a filter like
  `a{9999999999}` no longer closes it.
- `otp --tokens --limit=N`, `otp --request 0`, a port in `--radtest` that is
  not a number.
- A search such as `name:,` on the pages no longer ends in an error.
- A reload while config.json is missing keeps the settings in effect (it went
  back to the defaults).
- A body nested too deep is refused as not JSON, not an error.
- Restoring no longer leaves a file open each time.
- Putting a backup back from the page: up to 4 GB, as nginx takes.
- Czech texts that were missing: the enrolment sign-in, the notices when the
  daemon cannot be reached; two window titles showed &amp;.

## 1.0.138 — 28 October 2026

**New versions are looked for at https://github.com/falco81/OTP/tree/main/release**
- The default upgrade_url is the release folder of the OTP repository. A
  value saved as the old default (falco81/Utils/tree/main/otp) is taken as the
  new place; an address of your own stays as it is.
- That folder keeps the last ten versions.

## 1.0.137 — 28 October 2026

**Sign-in protection: guessing from one place blocked (RADIUS)** - Settings →
Sign-in protection, off by default
- Switched on (`radius_guard`), the place each VPN request comes from - its
  Calling-Station-Id, the address the person connects from - is counted:
  too many refusals from one place (`radius_guard_tries`, 20) or too many
  different names refused from it (`radius_guard_names`, 5) within
  `radius_guard_window_min` (15) and it is blocked for `radius_guard_block_min`
  (30). A blocked place is refused at once: nothing checked, and nobody's token
  counts its guesses - a guesser can no longer lock other people's tokens.
  `radius_guard_trusted`: addresses or networks never blocked. The server's
  own trouble (a directory away) is never counted.
- The table under it: every place counted and every token locked, how far each
  has got towards its limit (a bar that fills), how long a block still runs,
  the names tried; a filter by name or address; Clear one, the ones shown, or
  all. The same rows in Accounts → Locked out. Each node counts its own; both
  are shown and cleared.

**Changes that could cut the server off go back by themselves unless kept**
- A node's new network (`net_confirm_min`, 10 min) and a change of the
  firewall or of who may reach the pages (`fw_confirm_min`, 5 min) are put in
  on trial. A banner on every page counts the time down with *Keep it* and
  *Put the old back now*; `otp --change-keep net|fw [--node N]`,
  `otp --change-back ...`, the console (Cluster) and `otp --status` too.
- The network: not kept - or come up without its new address - the node goes
  back to its old network (a restart; the other node of a cluster told the old
  address again: its pg_hba.conf lets both in while the new one is on trial,
  and only the new one once it is kept). The firewall: the rules and the access
  lists as they were before come back on every node.
- The console's settings browser has the new group, and its main screen says
  when a change waits to be kept.

New: docs/sign-in-protection.md.

## 1.0.136 — 28 October 2026

A review of the whole application for bugs and security problems, with the
VPN's sign-ins - the reason otp exists - first: nothing else may hold them up.
Tested under load (RADIUS, the pages, backups, consoles and the command line
at once, and the database stopped for 17 s).

**RADIUS no longer waits behind anything else**
- RADIUS has a database connection of its own (chosen once per statement,
  never waiting for the main one while holding its own; a copy put back
  still holds RADIUS for the whole of it). With one connection for
  everything, a slow page held every sign-in behind it: just after a start,
  the uncached overview of a month took 29 s under load and the VPN timed out
  (160 of 166 requests unanswered). Now, with the same load plus the pages, a
  backup and three command lines running together: no request unanswered,
  p99 0.45 s.
- A database that does not answer is tried again at most every 2 s, not by
  every request in turn (one answer in 10 s, the queue full).
- The command line (and so the console) no longer makes the tables, indexes
  and triggers again on every run - on PostgreSQL that took locks every
  RADIUS write waited behind. Only when this node's database was not made by
  this version yet.
- `otp` runs imported, its compiled form kept: a command takes half the time
  (0.56 s instead of 1.2 s). The console asks for its status every 30 s, not
  at all while a live view, a page or a shell is open, and the web address
  every minute.
- Junk from a client's address with no Message-Authenticator and a password
  that cannot be read with its secret (control characters in it) is dropped
  and noted sparingly, not written down a row each (thousands a second could
  be sent). A password in another encoding than UTF-8 (cp1250) is still
  refused, not left unanswered.
- The narrowest clients of an address all switched off: the address is not
  answered - before, a wider range answered it with its own secret and realms.
  Of two of the same width, the one switched on answers.
- A refusal sent late (radius_reject_delay_ms) is given to the NAS's repeats
  once it went; before, the repeats got nothing and the NAS took the server
  for dead.
- An account's own entry in the directory (disabled, expired, locked) is kept
  15 s, not a minute.
- Codes are sent at most 8 at a time, at most 200 waiting: a mail server that
  hung no longer kept a thread per code without end.
- One housekeeping step breaking no longer skips the rest (backups, the time,
  tidying) with a traceback every 5 s.
- Under systemd only warnings and errors go to the journal as well as to
  otp.log - every line twice, and a slow journald held every thread that logs.

**Security**
- *Export with the secrets* (the pages) is locked with a passphrase made there
  and shown once; importing it asks for it (the command line too:
  `--passphrase-file` or `OTP_PASSPHRASE`).
- A backup of the tokens is always locked (a passphrase of 8 characters at
  least).
- Backups to other machines are never sent unlocked: without the backups'
  password nothing is sent and *Download one made now* is refused - unlocked,
  they hand the key of every token to whoever reads the destination.
- The second step of the administration: an account with mail or SMS codes
  that can no longer be sent is no longer set up anew by whoever has the
  password - it waits for a reset (Accounts, or `otp --reset-2fa NAME`). An
  app code used twice at once is refused the second time.
- The enrolment pages: a code typed back checks the token again - switched
  off, locked or confirmed meanwhile, it is not replaced.
- A test message to a token's phone: one in 30 s, ten an hour.
- The directory's errors (its server names, its TLS) go only to somebody
  signed in.
- The console's choice at login is kept in `/etc/otp-console-login`, where only
  root writes; `/etc/otp` is the otp account's group's, which could have put a
  link there for root to follow (a file overwritten) or a pipe (root's login
  hanging). Written beside it and renamed; read only as a plain file.
- Secrets off the command line, where `ps` shows them: the console's radtest,
  a client's secret and secret settings go by the environment
  (`--secret -`, `--set KEY=@env`, `--radtest NAME -`); install.sh's test
  client too; an SSH key's passphrase goes to ssh-keygen through SSH_ASKPASS.
- The replication password is kept out of PostgreSQL's log when the cluster is
  readdressed (as it was when it is made).
- A backup destination's folder or share with `;` or `"` in it, or one
  beginning with `-`, and an account beginning with `-`, are refused
  (smbclient takes `;` as the next command, ssh `-` as an option).
- A backup put back is unpacked only when it fits on the disk.
- `otp` is started with `python -I`: nothing from the folder it is run in.

**Fixes**
- An upgrade from the pages that hangs is stopped as a whole (install.sh and
  what it started), install.sh's own put-back runs first; before, the deadline
  never fired.
- The console's radtest can answer a challenge (codes by mail or SMS).
- A client changed on the command line or in the console stays switched off
  if it was.
- `otp --set` refuses `ha_*` and, without `--yes`, `db_*`, as the pages do;
  the console says where they are changed. `KEY=@env` without its variable
  set saves nothing.
- A backup from another machine put back is no longer refused at 32 MB: the
  guarded upload takes it (install.sh adds it to an nginx file that has the
  guard).
- install.sh no longer takes the otp account's write on /etc/otp away for a
  moment on upgrade.

## 1.0.135 — 28 October 2026

**The otp console: every menu by arrows and Enter, windows instead of prompts**
- Nothing is typed at a bare prompt any more. Every question is a window over
  the menu: fields moved between with Up/Down (Tab), choices (app / mail /
  SMS, a role, on / off) changed with Left/Right, passwords as stars only, the
  help of the field under them; Enter checks everything before it is run (a
  needed field empty, a number out of its limits, an address or e-mail that
  is none, two passwords not the same, a missing file - it says which and the
  window stays), Esc closes it. Deleting, switching off, putting a copy back,
  a restart, an upgrade ask Yes / No first, No unless chosen.
- Tokens, accounts, RADIUS clients, realms, directories and the backups kept
  here are lists to scroll (arrows, PgUp/PgDn, Home/End, scroll bar, `/` to
  find); Enter on one offers what can be done with it - for a token show,
  switch off / on, unlock, new recovery codes, try a sign-in, delete; for an
  account its password (twice, as stars), its role, off / on, reset its
  second step, delete; a client changed or deleted; a directory tried; a
  backup looked into or put back.
- A command's short answer comes in a window, a long one on the scrolled
  screen. Settings → Change one by its key opens the same window as Browse.
  Cluster → move the web address picks the node from a list; Upgrades → from
  the web lists what is newer, a version is picked, then the progress.
- New accounts and passwords go to `otp --add-user` / `--passwd` through
  OTP_PASSWORD, never on a command line.

**The live views: scrolled, and what is typed is a grep**
- The console opens on the live log, every line (Esc: the menu;
  `OTP_CONSOLE_START=menu` opens on the menu).
- The live log, the live RADIUS requests and the journal are a screen of
  their own: followed at the bottom, Up/PgUp/Home scroll back (paused, the
  new lines counted), End or Enter follow again, Left/Right along long lines,
  a scroll bar on the right; the last 20 000 lines kept.
- Typing filters the lines as `grep -i` does - any case, a regular
  expression or the text as it is - the hits marked; Backspace, Ctrl+U, Esc
  clears it and Esc again goes back. Keys typed quickly are no longer lost
  (the terminal was flushed at each key).

**Which node holds the web address, in the console's top bar**
- The bar shows `VIP 192.0.2.10 on nodeb` (or `VIP off`), and a red line under
  it when no node holds the address or two do. A narrow window shortens the
  bar (the tokens first) or puts it on the line below.

## 1.0.134 — 28 October 2026

**The otp console: long output on a screen of its own, settings changed in a window**
- A command's output longer than the screen opens on a screen of its own:
  arrows, PgUp/PgDn, Home/End (and Space, j/k, g/G) scroll it, a scroll bar on
  the right says where you are and how much there is, Esc / q / Enter go back.
  Drawn in one write a frame, so nothing blinks; a window made bigger or
  smaller is drawn again to its size. Colours kept; lines too long are cut at
  the edge rather than wrapped.
- *Settings → Browse and change*: every setting, in the groups of the pages,
  with its value (set ones bright, defaults dim) and key; arrows, PgUp/PgDn,
  Home/End, `/` to find (n: the next), and a scroll bar. Enter opens a window
  with what it is (its help), what it is now and as it comes, what it may be -
  a switch or a list chosen with the arrows, a number between its limits, a
  text typed (a secret as stars) - checked exactly as the daemon checks it
  before `otp --set` saves it; a wrong value says why and stays open.
- Lines and boxes drawn as UTF-8 characters (`NCURSES_NO_UTF8_ACS`), as PuTTY
  shows them; ASCII where the terminal is not UTF-8.

**Upgrades from the web on the command line and in the console**
- `otp --upgrade-check` looks at upgrade_url now and lists what is there.
- `otp --upgrade-online [VERSION]` fetches the newest (or VERSION), checks its
  signature, asks (`--yes`: does not), upgrades every node one at a time and
  follows it: a bar for the whole and one for each node, drawn again in place
  every second, with what each node is doing - in a cluster too.
- `otp --upgrade-follow` follows an upgrade going on (started anywhere);
  Ctrl+C stops the following, not the upgrade.
- The console's *Upgrades* has all three.

## 1.0.133 — 28 October 2026

**The otp console, checked through**
- The bar at the top said *THIS NODE IS IN MAINTENANCE* of a node in service:
  it took the maintenance record (`{on: false, …}`) for a yes. It now says it
  only when the node is, with why; another node in maintenance is named on a
  line of its own; and a daemon not answering is said in red. The cluster
  (nodes answering, replication) and the tokens in use are read as
  `otp --status --json` gives them - before, they were never shown.
- A question or a command's output starts on a clean screen - not under what
  the last command left there.
- *Make one (enrol)* asks how the codes come (app / mail / SMS) and where they
  go, as `--enroll --by --to` wants; *Move the web address* asks to which node;
  a question left empty goes back to the menu instead of running the command
  half asked; *Settings → Look* searches the help texts as well.

## 1.0.132 — 28 October 2026

**The otp console: Esc everywhere, colour everywhere**
- Esc goes back wherever the console waits: in a menu, in a question (what was
  typed is dropped), at *Enter or Esc - back to the menu*, and in the live
  log, the live RADIUS requests and the journal (q and Ctrl+C too). A password
  or a secret typed is shown as stars only.
- Every output in colour (colorama): each table's heading, and its cells by
  what they say (active, on, accept green; off, rejected, failed red; waiting,
  maintenance yellow; never, - and times dim; addresses magenta) - the colour
  never shifts the columns; every other line too: "key: value", addresses and
  times. The same for `otp ...` typed by hand on a colour terminal; JSON,
  `--no-color`, `NO_COLOR` and anything not a terminal stay plain.
- The live log starts from the end of the file without reading all of it.

## 1.0.131 — 28 October 2026

**The otp console: menus by the arrows**
- A text screen (curses): arrows or j/k, Enter or → to choose, Esc, ← or
  Backspace back, numbers to jump, Home/End, PgUp/PgDn, `!` a shell, `q` to
  leave. Only what changes is written - nothing blinks - and a window made
  bigger or smaller (PuTTY included) is drawn again to its new size. The bar
  at the top (version, machine, the service, node, cluster, tokens,
  maintenance, problems) is asked for every 20 s in the background. Arrows sent
  as ESC [ A by terminals that ignore the keypad mode work too.
- The live log in colour: the level, what it is about, addresses, accepted and
  rejected words, warnings and errors whole.

**Message texts**
- The save bar is at the end of the editor, as at the end of any other page:
  scrolled to the bottom it is there, and once something is changed it sticks
  to the bottom of the editor.

## 1.0.130 — 28 October 2026

**The otp console** (new: docs/console.md)
- `otp --console`: the whole of otp by its menus on the server's screen or
  over SSH - status and checks, the live log (coloured, filtered, following
  rotation), the live RADIUS requests, tokens, the administration's accounts
  and their second step, settings (search, change, export), RADIUS clients,
  realms and directories, the cluster, the web address and maintenance,
  backups, upgrades and the service itself. Each action is the `otp …` command
  it shows; `!` opens a shell and comes back, `q` leaves for the shell.
  Colour with colorama, English.
- It opens by itself when root signs in at the console or over SSH
  (`/etc/profile.d/zz-otp-console.sh`) - never for a command run over SSH,
  scp/sftp or a script. `otp --console-at-login on|off|status`; install.sh
  switches it on the first time and an upgrade leaves the choice alone.

**Settings, the menu on the left**
- Opened, it is exactly as tall as shut, item for item: a pointer that opened
  it over one item stays over that item (a longer name was wrapped onto two
  lines and moved everything below it).

**Message texts**
- The save bar is out of the way until something is changed, as below the end
  of any other page, and then at the bottom; the words above the editor are
  shorter.

## 1.0.129 — 28 October 2026

**Message texts: only the editor scrolls**
- The heading of the pane and the list of messages stay where they are; the
  editor on the right is the one thing that scrolls (its own bar), and the
  page itself does not - the save bar stays under it. On a low screen the
  list gets a thin bar of its own when it does not fit; under 900 px wide it
  is one column and the page scrolls, as before.

## 1.0.128 — 28 October 2026

**Message texts: one scroll bar**
- The list of messages and the editor no longer scroll each on its own: the
  page scrolls, and the list - shorter now, one line a message - stays in
  view beside the editor. The administration's four messages are a group of
  their own (*The administration*) under their short names.

## 1.0.127 — 28 October 2026

**The second step: by e-mail and SMS**
- *Send a code* on the sign-in page sent the code and then showed nothing -
  the page had no place for its message and stopped there. Now it says where
  the code went, right under the button, and the box for the code appears;
  Enter in the address box sends it.
- The codes have their own words, not the VPN's: four new messages in
  Settings → Message texts - *The administration: a sign-in code by mail /
  by SMS* and *…checking an address / a number* - with their own mail
  (band, greeting, what it is, the warning, the foot, the plain text) and SMS,
  in the language of the sign-in page.

**On the command line**
- `otp --admin-2fa on|off|status` switches the second step for every account,
  or says how it stands: the ways offered, who has set it up, who will at
  their next sign-in.

## 1.0.126 — 28 October 2026

**The second step fits on one screen**
- While it is asked, the sign-in page's picture and welcome line go; the ways
  are one row (App · E-mail · SMS), the QR code is smaller, and the code and
  its button sit side by side - as do the address or number and *Send a code*.

## 1.0.125 — 28 October 2026

**A second step for the administration pages** (new: docs/admin-second-step.md)
- `admin_2fa` (Settings → Accounts, off by default): after the password every
  account of these pages - local or from the directory - gives a code of its
  own (not a VPN token). The ways offered: an authenticator app
  (`admin_2fa_app`, the default), a code by e-mail (`admin_2fa_mail`, while
  mail is set up), a code by SMS (`admin_2fa_sms`, while SMS is set up).
- The first sign-in sets it up on the sign-in page: the app's QR code and its
  six digits, or an address / a phone number proved by a code sent there.
  Afterwards the code is asked each time; an app code is good once, codes sent
  at most every 30 s and five per sign-in. Until the step is given the
  sign-in can do nothing else, and the pages taking a file see no role.
- Wrong codes count as wrong passwords (Accounts → Locked out); every step is
  an event.
- Accounts: a column *Second step* and a button to reset it (the account's
  sign-ins end; it sets it up again at the next sign-in). On the command line
  `otp --reset-2fa NAME`, and `otp --users` shows the column.

## 1.0.124 — 28 October 2026

**A password being typed is dots only**
- Everywhere a password, a passphrase or a secret is typed (settings, the
  directories, the clients' shared secrets, backups, the database with its
  key, the load balancer guide…), only dots are shown while typing - not the
  last two characters. Those show only on one that is kept, as the daemon
  sends it (dots and its last two), after a save or when the page is opened.

## 1.0.123 — 28 October 2026

**Refreshing by itself never takes anything from under the person using the page**
- A list opened, a box typed in, a switch just turned, the mouse held down on a
  button, a help panel being read or words selected: the card it is in stays
  exactly as it is (the same elements, never taken out of the page - a list
  taken out closed), and everything around it is drawn new. A card whose shape
  changed meanwhile is drawn the moment it is left. What was changed and not
  saved goes over into a card drawn again; folds left open stay open.
- Everywhere a pane refreshes itself: Time, Network, Restart and power off,
  Lockouts (every second), High availability (nodes, checks, replication, the
  addresses, each node's own settings, the web address), Certificates and TLS,
  Firewall and access, Outgoing mail, Upgrades. Before, some stopped refreshing
  altogether while a box had the focus; others closed an open list.
- Overview, Log and Events wait while a box drawn in them is being used (no
  longer only half a minute).

**One save bar, at the bottom, where something is saved - and only there**
- Shown on every pane with a setting, and on Firewall and access, High
  availability (the web address), Time, Message texts and the enrolment pages'
  looks; never on a pane that does things at once (Network, Restart and power
  off, Backups' jobs, Export and import…). It no longer turned up on Network
  now and then (its form looked like settings) and went with F5.
- Time: the time servers are saved with the bar (was a button of their own).
- Message texts: saved and thrown away with the bar (were buttons of their
  own); Ctrl+S presses it.
- High availability: *Save the new addresses* is *Change the addresses* - it
  does it at once.

**The database: downloaded with its key, and put back with it**
- *Download* (a kept copy or dump) and *Download it* / *Download one* (made
  now) ask: **with the key** - one `NAME.with-key.tar` holding the copy or dump
  and the key that opens its tokens, locked with a passphrase given there (10
  characters at least; the lock of the cluster's bundle) - or **without** it.
  Before, a dump never had the key and a copy only while showing keys was on.
- *Restore from this file* takes such a file: it asks for the passphrase,
  shows what is in it, and puts back the database and its key together - as a
  job the page follows (a big database took longer than the page waited).
  The passphrase never goes into an address: the file is made first and
  fetched with a ticket good for ten minutes, once.

**Upgrades from the web**
- *Settings → Upgrades → From the web*: `upgrade_url` (default
  https://github.com/falco81/Utils/tree/main/otp - a GitHub folder, a page or
  listing linking to packages, or one package) is looked at once a day
  (`upgrade_check`) and on *Look now*. A newer `otp-X.Y.Z.tar.gz` is offered:
  *Upgrade to X now* fetches it, checks its signature like a package sent by
  hand, and upgrades the nodes one at a time; *Only fetch it* stops before.
  Nothing is put in by itself. docs/upgrades.md.

**Hide this**
- On what is over and only says how it went: a restart or power-off (it went by
  itself after half an hour), an upgrade, a job on the database or of the
  cluster (the bar stayed until F5), a test mail, the SMS gateway's test, a
  try of a backup destination.

## 1.0.122 — 28 October 2026

**install.sh: chrony**
- On a fresh install and on every upgrade (also one started from the pages,
  node by node in a cluster), chrony is installed where it is missing,
  systemd-timesyncd is stopped if it runs, chronyd is enabled and started and
  `timedatectl set-ntp true` is set. The machine's own /etc/chrony.conf
  (AlmaLinux's pool) is used as it is; without any time server in it the
  installer says so. Before, Settings → Time showed *chrony is not
  installed* until otp was told to set the time servers.

## 1.0.121 — 28 October 2026

**The web address (VIP) after a node's address is changed**
- After Settings → Network changed a node's address, keepalived on it could
  stay *not well* (*no interface here holds …*) until *Try again* was pressed:
  its part was asked of root before the restart, when the machine did not
  have the new address yet, and a failed request was asked again only by hand.
  Now:
  - the interface for the web address is found by the web address's network
    when none holds the node's own address (yet);
  - the change of network asks for the web address again after the restart
    and waits for it (a step of its own: *the web address (keepalived) set up
    for …*) before the node comes out of maintenance;
  - a request that failed before a restart is asked again once by itself
    after it.

## 1.0.120 — 28 October 2026

**Settings → Time** (new: docs/time.md)
- Each node's clock as chrony sees it: how far off the time servers, synchronised
  or not, the source it follows, stratum, last correction, frequency, root
  delay and dispersion, leap status, time zone and its own time; how far apart
  the two nodes are; every source with its state, stratum, poll, the last eight
  tries, when last heard and its offset. *Step it now* (chronyc makestep).
- The time servers for the whole cluster, when otp is to set them: servers and
  pools with iburst, prefer and NTS; the two nodes as sources for each other;
  makestep, minsources, the networks the nodes serve the time to (opened in
  the firewall by itself), the time zone. Each node writes them into
  /etc/chrony.conf between marks (the file's own lines commented out, and put
  back when otp stops setting them) and restarts chronyd.
- A clock not synchronised, or more than a second off, is a problem on the
  overview and in otp --status.

**High availability → Each node's own settings**
- Says where the rest of a node's own setup is: its network, IPv6 and host
  name in Settings → Network (IPv6 on makes RADIUS listen on :: by itself),
  its clock in Settings → Time.

**Settings, the menu**
- In groups that say what is in them: RADIUS, Tokens, Mail (Mail, Outgoing
  mail), Access (Accounts, Certificates and TLS, Firewall and access), Server
  (Network, Time, High availability, Restart and power off), Data (The
  database, Backups, Export and import), Monitoring and updates (isemon,
  Upgrades, About) - not everything under "This installation".

**Settings → Network**
- A finished change (*The network of … is changed*) has a *Hide this* button,
  and goes by itself 6 hours after it was done (a day when it failed) - it
  stayed for a day before.
- *The web address is meant to be in another network* is shown only when the
  new address is outside the web address's network, with why it matters.

## 1.0.119 — 28 October 2026

**Settings → Network** (new: docs/network-and-power.md)
- Each node's IPv4 address with its prefix, gateway, DNS servers, search
  domains and host name (FQDN), as NetworkManager has them, read on either
  node's pages; and a form for new ones. *Check it* lists what will happen.
- *Change it and restart* is done by the node itself, followed on the page step
  by step with a progress bar: in a cluster the other node is told the new
  address first (its pg_hba.conf, its subscription, its ha_peer), this node's
  ha_address, the settings that named the old address or host name (RADIUS's
  address, the mail greeting, the isemon name) and its own certificate where it
  was made here are made again, maintenance moves the web address to the other
  node, NetworkManager, the host name and /etc/hosts are set and the node
  restarts. Back up it checks its new address, replication both ways and the
  link between the databases (its certificate made again for the new address),
  and comes back into service by itself. The node keeps its name in otp
  whatever the machine is called (pinned in config.json first).
- IPv6 (dual stack), switched on per node: by hand or automatic; RADIUS listens
  on IPv4 and IPv6 (::), nginx answers on both, the firewall covers both.
  Replication between the databases stays on IPv4. The web address takes an
  IPv6 address of its own (High availability → …and its IPv6 address), moved by
  the same VRRP instance (virtual_ipaddress_excluded) and listened on by nginx.
- A page whose own node restarts waits for it, counting; where it was opened
  at the node's old address or name, it goes to the new one.

**Settings → Restart and power off**
- Restart or power off this node, the other, or both: one after the other (each
  in maintenance while it restarts - RADIUS and the pages never stop), both at
  once, or both switched off. Each node does its own part when its turn comes,
  so either node's pages follow it: going down, restarting, up again, with a
  countdown; the page reloads when its own node is back.

**RADIUS**
- Listening on :: where IPv6 is switched off on the machine falls back to IPv4
  (0.0.0.0), said in the log, rather than listening on nothing.

## 1.0.118 — 28 October 2026

**RADIUS**
- The second request of a sign-in with a second window (the code typed after a
  code by mail or SMS, or asked for from the app) shows what the first request
  checked: *checked with the first request (ID): found CN=…; the directory
  password; a member of CN=VPN,…*. The account, its password and its groups are
  checked once, in the first request - for a realm's own suffix and its other
  suffixes alike; the second carries only the code.

## 1.0.117 — 25 October 2026

**One person, several suffixes** (new: docs/realms-and-suffixes.md)
- A realm takes other suffixes too: *…and also the names ending in @*
  (`otp --add-realm NAME --aliases a.local,b.cz`). `novak@dpmo.local` is then
  the token `novak@dpmo.cz` - in RADIUS, on the enrolment pages and in *Make a
  token*. Looked up by UPN, the name is tried under each of the realm's
  suffixes.
- Tokens made under such a suffix before go on working; the realm's editor lists
  them and *Move them under @…* renames them (key, recovery codes, history),
  leaving any that would land on a token already there.
- Fixed: the enrolment pages kept using a token the same account had in another
  realm on the same directory (signed in as falco@dpmo.local, the token
  falco@dpmo.cz), and RADIUS then refused falco@dpmo.local - *No token is
  enrolled*. RADIUS now finds that token too, where both realms read the same
  directory by sAMAccountName, and the decision says so.
- Writing another realm's suffix as one of a realm's own offers to take that
  realm in, in one step: its suffixes, its groups (after the realm's own), the
  clients allowed it.
- The list of realms shows the other suffixes under the one each takes.

## 1.0.116 — 25 October 2026

**Who is locked out** (Settings → Accounts → Locked out)
- Also what the database counts for every node: the codes sent to a person or
  an address ("too many codes were sent") and tokens locked after wrong codes -
  how many of how many, the time left, *Clear* one or *Clear them all*. Written
  into Events.
- "too many codes were sent - wait N min" says how long is really left, not the
  whole window.

## 1.0.115 — 25 October 2026

**The enrolment pages**
- Replacing a token with a confirmation asked for: *Cancel - keep the old
  token* right under the new one. The new token is thrown away; the old one and
  its recovery codes stay as they were (written into Events).
- The page says what leaving it does: nothing - the old token goes on working,
  and the next sign-in shows the new one waiting, to confirm or throw away.
- *I want to get my codes another way* on a line of its own, not glued to the
  button beside it.

## 1.0.114 — 25 October 2026

**The enrolment pages**
- *Your recovery codes*: the box for the code looks like every other box on the
  page - a field with its label, half the card wide, the button to send a code
  beside it, as tall as it.
- The words under a token of codes by e-mail or SMS are in Czech too.

## 1.0.113 — 25 October 2026

**Codes by SMS** (docs/codes-by-mail-and-sms.md, "When a code does not arrive")
- *Test the connection* under the Teltonika gateway: signs in with what is
  saved and lists its modems - operator, network, band, signal (quality, RSSI,
  RSRP, RSRQ, SINR), the SIM, which modem sends the codes - with how long each
  step took. Nothing is sent. Written into Events.
- A sign-in the Teltonika leaves unanswered ("The read operation timed out") is
  asked again once by itself; a send is still never repeated.
- New debug switch *...every code sent by e-mail and SMS* (on with *Debug
  log*): every request to the SMS gateway and its answer with how long it took,
  how long a code waited for the one before it, every line of the conversation
  with the mail server. Passwords, the gateway's token and the messages are
  never written.

**The enrolment pages**
- The name at the top opens *About you*: what the directory said at sign-in -
  the name, account and UPN, e-mail, mobile and phone, department and job
  title, the realm and the groups of it that let the person in, when the
  account ends and when the password was set, and their token.
- *People may look at their recovery codes again* (Settings → The enrolment
  pages; off unless switched on): after signing in, a card shows the person's
  recovery codes - the used ones crossed out - once they type a code from the
  token (the app's, or one sent to them now). The directory password alone
  never shows them. Each look is written into Events.

## 1.0.112 — 24 October 2026

**Who is locked out** (Settings → Accounts → Locked out; docs/operations.md, section 18)
- Every address and name with wrong attempts still counted - signing in to
  these pages or the enrolment pages, codes typed there, password changes, the
  tests: locked out (with the time left, counting down) or still counting
  (how many of how many, and when they are forgotten), which names were tried
  from an address and from which addresses a name was tried, on which node.
- *Clear* forgets one; *Clear them all* forgets every one, on every node. The
  other node clears its part within five seconds. Both go into Events.

**Realms**
- The list always shows what people may choose: a realm of the app alone showed
  no tag at all, as if it had lost it.

## 1.0.111 — 24 October 2026

**Backups**
- *How to put it back* (Settings → Backups): the RESTORE.md every backup
  carries, as a backup made now would have it - read on the page (each command
  with a copy button) and *Download RESTORE.md*, to keep apart from the backups.
  No secret is in it.

## 1.0.110 — 24 October 2026

**Two machines with one name** (docs/renaming-and-readdressing.md)
- Fixed: a node could take the other node's name. The settings page drawn by
  otp2 was saved through the web address after it had moved to otp1: measured
  against otp1, otp2's name in the box looked like a change and otp1 saved it.
  Both then wrote one heartbeat - the other was *gone*, the web address *on both
  nodes at once*.
- A machine's own settings (its name, its database) are saved only on the node
  the page was drawn by; any other node refuses them (409, nothing saved). A
  node's own setting saved from the page goes to the node that drew it.
- When another node answers than the one that drew the page, the settings are
  drawn again from it, and the page says so.
- A name another node is answering with is refused (pages and `otp --set`).
- Every heartbeat carries the machine it came from: two machines with one name
  are said on every page (problems), in `otp --ha-status` and in the log.
- A restart under a new name carries nothing over when another machine is
  answering with that name.
- Fixed: after the web address moved, the save bar could count changes nobody
  made (the boxes of one node measured against another's values) and save
  them.

**Backups**
- *What was sent* can be cleared (*Clear the list*), or one line taken off it.
  The backups themselves stay where they went; Events says who did it.

## 1.0.109 — 24 October 2026

**Backups to another machine** (Settings → Backups; new: docs/remote-backups.md)
- One file brings any loss back - one server or a cluster, onto a machine
  installed from nothing: the whole database (tokens, clients, realms,
  directories, accounts, every setting, the certificates and keys of the pages,
  the web address, the firewall, the texts, the authority of the database link,
  the logs), the key that opens the tokens, this machine's config.json and the
  files it names, a manifest with the SHA-256 of each, and RESTORE.md - the exact
  steps, filled in with what the backup is.
- Locked with *The password of the backups* (kept sealed in the settings;
  *Make a strong one*): AES-256-CBC, PBKDF2-SHA256, 600 000 rounds - opened by
  otp, or by openssl alone on any machine. RESTORE.md and a .sha256 go beside
  it, not locked.
- Destinations, as many as needed: a folder (a mount), FTP, FTPS (explicit or
  implicit; the server's certificate checked against the system's authorities,
  an authority of your own or a pinned fingerprint; a client certificate made
  here or brought as PEM or PFX), SFTP and SCP (OpenSSH; an ed25519 key made
  here or your own with its passphrase, an SSH certificate, or a password; the
  server's host key trusted once and checked after), SMB (account, domain,
  SMB3 encryption). Keys and certificates as on isemon: Make, Use my own,
  Download (written into Events), Forget, the public half to copy with the line
  to run on the server. *Try reaching it* signs in, writes a file, finds it and
  takes it away again.
- *Back up now*, *Download one here*, a schedule (daily or weekly, at a time),
  how many are kept at each destination and for how long; each node of a
  cluster sends its own. *What was sent* lists every backup and what each
  destination said.
- Putting one back: from a destination's list, or a file sent from the page,
  or on the command line - `otp --restore-bundle FILE [--yes]` on a fresh
  install. A copy of what is replaced is made first.
- Command line: `otp --rbackup-now`, `otp --rbackup-status`,
  `otp --restore-bundle`, `--passphrase-file`, `--keep-node-name`.
- install.sh installs openssh-clients and samba-client for them (best effort).

**A test SMS that takes long says why**
- *Send a test* on a token's card and the test SMS in Settings count the
  seconds on the button while they wait, and the answer says how long each
  step took: signing in to the Teltonika, finding its modem, and the modem
  sending it - RutOS answers only once the modem has given the SMS to the
  network. Sign-in codes were never held up by it: they are sent in the
  background.

**Message texts**
- The list of messages stays where it is; only the editor beside it scrolls.
- Czech for the page's description and "When the name is not known".

## 1.0.108 — 24 October 2026

**The web address said "on no node" while a node held it**
- VRRP was working - keepalived moved 192.168.42.34 as it should and the
  table of nodes said *holds it* - but the card above it said *on no node*.
  1.0.106 brought a second function of the same name as the one that tells
  which addresses this machine has; it took the old one's place everywhere,
  could not run `ip` from the service (no /usr/sbin in its PATH) and answered
  "none". The old one (it reads the kernel's own list) is back; the addresses
  card has a function of its own name.

## 1.0.107 — 24 October 2026

**TLS between the databases can be switched off again**
- *Switch TLS off…* in the green bar (Settings → High availability →
  Replication) and `otp --ha-tls-off --yes`. The steps run the other way round
  so replication never stops on them: both databases let the other node in
  without TLS too (hostssl → host), both links go back to Database → TLS, then
  the cluster's certificates leave both PostgreSQLs (ALTER SYSTEM RESET: ssl
  as postgresql.conf says) and /etc/pki/otp/ha-ca.pem goes. Switched off, the
  nodes no longer put it back by themselves; *Repair* turns it on again.

**The Database page says how the link to the other node is protected**
- Under *Encryption to the database server*: encrypted and checked
  (verify-full) by the High availability page's own setting, with a link
  there. That field is this daemon's connection to its own PostgreSQL and
  stays empty - after the link was encrypted it looked as if nothing had
  happened.

**Fixed**
- *The addresses of the two nodes*: "This machine has: ?" - the service's
  PATH has no /usr/sbin, so `ip` was not found.

## 1.0.106 — 24 October 2026

**A node renamed or given a new address: put right in place** (new:
docs/renaming-and-readdressing.md)
- *Settings → High availability → The addresses of the two nodes* and
  `otp --ha-readdress [--ha-address NEW] [--ha-peer NEW]`: on the node whose
  address did not change, the other node's new address moves this node's
  pg_hba.conf line (host/hostssl kept, the old file kept beside it), its
  subscription and config.json over, and the other node is told straight into
  its database and puts its own side right by itself - its address in
  config.json, a new certificate for the link. The firewall, keepalived and
  nginx follow by themselves. Before this, a new address meant taking the
  pair apart and building it again.
- The page warns when config.json names an address this machine no longer
  has; `otp --ha-readdress` alone shows the addresses as the node has them.
- A renamed node starts its link steps again under the new name.

**The link between the databases**
- A node whose certificate lacks the name the other node reaches it by is
  told so by the other node and makes itself a new one at once - not at its
  next look ten minutes on. (On otp1 the look at start did not catch it.)
- *Start the steps again* in the bar when they have run for more than three
  minutes; `otp --ha-tls` (how it is, each node's step, when certificates
  end) and `otp --ha-tls-repair` (the button) on the command line.

## 1.0.105 — 24 October 2026

**The link between the databases: stuck on "does not match host name"**
- Each database's certificate named its node's address only as an address.
  libpq 13 - the one RHEL/Alma 9 has, and the daemon uses to try the other
  node - reads names alone, so the try failed ("server certificate for "otp2"
  (and 2 other names) does not match host name "192.168.42.33"") and both
  nodes waited at "link verify-full". Replication went on as before,
  unencrypted. Every address is now in the certificate both as an address and
  as a name.
- Nothing to press after the upgrade: each node sees at start that its
  certificate lacks a name, makes a new one and goes through the steps again;
  a node that gave up meanwhile starts again as soon as the other node has put
  its side right. A node waiting at the link step for more than two minutes
  also looks whether its own certificate is what is wrong.
- The names a certificate must have also come from the cluster's own list of
  nodes (the address each one is heard at), not only from the other node's
  setting.

## 1.0.104 — 24 October 2026

**The link between the two databases: encrypted and checked with one button**
(Settings → High availability → Replication)
- The orange bar that said the link is not encrypted has a **Repair** button.
  On a running cluster, on both nodes, nothing stopped: the cluster gets its
  own authority, each PostgreSQL a certificate from it (put in by the root
  helper, reloaded - not restarted), each node moves its link over to
  verify-full once it works against the other, and then each PostgreSQL lets
  the other node in over TLS only (host → hostssl in pg_hba.conf). The bar
  follows each node's step; one that does not work stops there and says why,
  with nothing in use changed.
- The link has settings of its own (ha_tls, ha_tls_ca in config.json): the
  daemon's connection to its local PostgreSQL is left as it is. The old advice
  to set Database → TLS to verify-full would have broken that connection.
- Certificates renew themselves 45 days before they end; the authority is
  replaced two years before it ends, the old one trusted beside the new one.
- It looks after itself: every ten minutes, at start and after a database is
  put back, each node checks its PostgreSQL's certificate, the authority file
  and its link, and goes through the steps again when anything is not right
  (a reinstalled or rejoined node, a PostgreSQL set up anew, a certificate run
  out while the machine was off). Repair also mends a link whose certificate
  ran out and stopped replication.
- Backups: the authority is in every copy of the database (its key sealed);
  putting a copy back keeps the authority the running cluster has, and a copy
  from before it makes a new one that both nodes take. Each node's progress is
  not taken from a copy (it describes the machine).
- A node joined again does not put a plain host line back in front of a
  hostssl one in pg_hba.conf.

**Certificates of the pages after a restore**
- nginx's certificate is compared with the one saved in the database, not only
  written once: missing or different (a machine put back from its own backup,
  nginx set up again, a file changed by hand) it is put in again, and the event
  says so.

**Fixed**
- Settings: "Put them back" did nothing while a value was changed - the
  changes were never forgotten, so the page was not drawn again.

## 1.0.103 — 24 October 2026

**Realm groups that can be read, however many there are** (Settings → Realms)
- Each group of a realm is a card of its own: its name (the CN) to read, its
  whole DN under it, wrapped, never cut short; a "the whole DN" / "a name
  alone" mark; its place in the order numbered, moved with arrows (the first
  group the person is in answers); edit and remove beside it.
- A group's own answer lines show only when it has some - otherwise one small
  "+ its own answer" link, so a long list stays a list.
- The list counts its groups; past six it gets a search box and scrolls inside
  the section instead of stretching the window.
- The realms table shows the groups as chips by name with the whole DN on
  hover; past three, "+N more" opens the rest and "fewer" folds them again.

**The ways of getting a code each in its own colour**
- The app violet, e-mail blue, SMS orange - the same in the realms table, the
  tokens list, a token's detail and everywhere else a token's kind is shown.

**Fixed in the administration pages** (a walk through every page)
- In English the administration pages stopped loading: the token list stayed
  empty and no button worked. A text looked up in a translation that was not
  loaded failed; it now comes back as it is.
- "The mail is" (HTML / plain text) on a mail token's card was never saved.
- The person picker offered names no realm takes (a userPrincipalName with
  another suffix: pkolar@corpnet.loc for the realm corpnet.cz) - the token
  made under it was refused by the VPN. Such names are no longer offered.
- An account that must choose its own password got a page of dashes and
  "change your password first" errors; the form for a new password now opens
  by itself (with the new one asked twice and a way to sign out).
- The overview offered an older package as one "ready to be put in" - now
  only a newer one.
- "Open the Log" in the Let in / Refused popups opens the Log filtered to
  them, for the last 24 hours.
- The Log's disabled "Last" button said to sort by a heading that does not
  sort; it says to shorten the window or narrow the search.
- The time picker stays inside the window on a phone (it scrolls, opens
  upwards when there is more room); the HA node table scrolls on its own.
- Making a token: an address typed by hand for e-mail came back empty after
  switching to SMS and back.
- The Test tab: the first step of a mail/SMS token (a challenge) counted as a
  wrong password and after about 16 tests locked every administrator of that
  address out for 3 minutes. Challenges no longer count, and an address may
  take 100 failed tests (still 20 per administrator and person).
- A broken config file gives "the file is not JSON" instead of the browser's
  own error; "that is not a phone number" now says how to write one.
- Czech for texts left in English: the note after making a mail/SMS token,
  the enrolment steps, events (where codes go, language, mail format, test
  message, restore), the SMS test, the database check, a refused directory
  reading account. The notes column of the tokens list no longer squeezes
  to a word a line.

**Message texts: every word people get, edited as it will look** (Settings →
Tokens → Message texts)
- Every mail and SMS this server sends - the sign-in code by mail, checking an
  address, a token with its QR code, the sign-in code by SMS, checking a
  number - and what the VPN's second window asks, in Czech and in English.
- A mail is shown as it arrives, in the window of a mail program: click into
  any of its texts and write, with a toolbar as in a word processor - bold,
  italic, underline, a colour, a link, formatting taken away, undo. What is
  filled in when it is sent (the code, the name, the account, the minutes...)
  stands in blue chips, put in from the toolbar or under each box, and cannot
  be broken by typing. The layout - the band, the box with the code, the QR
  code, the warning - stays as it is, so the mail looks alike in every mail
  program, Outlook included.
- An SMS is written beside a phone showing it, with its length counted: how
  many SMS it makes, GSM or Unicode, accents taken out where that is set.
  The VPN's questions beside a window showing them, counted in bytes (253 at
  most, as RADIUS carries them).
- *Put back as it comes* for a whole message in one language, and for each
  text alone: back exactly as it was before it was changed. *Preview* with
  sample values, *Send a sample* to an address or a number - both with what
  is not saved yet. Texts left empty leave their block out of the mail.
- Kept in the database, only what differs from the default: every node of a
  cluster sends the same words within seconds, and two administrators saving
  at once are told rather than one overwriting the other. If the database
  cannot be asked, the defaults are sent - never nothing.
- What is written is checked: only the values a text may have, braces on
  their own refused, the formatting kept to what mail programs show alike
  (everything else taken out, its words kept).
- The verification mail has its own greeting, band and foot now (they were the
  sign-in mail's), and the token mail's band text is no longer fixed in code.
- The plain text version of a token mail showed `&#8205;` inside every account
  name and doubled `&amp;`: it is made from the plain values now.

**Mail through the outgoing mail**
- Every mail goes through the outgoing mail - the codes, the tokens' mails,
  the samples, the test mail. With mail sent straight to the recipient's
  server, the test mail can still be sent *straight, this once* to see every
  step of the conversation.
- With mail switched off nothing waiting is tried or given up (codes past
  their time aside), as the page says.
- A mail refused for good stays "refused", not "given up", when its time runs
  out; asking again for a code past its time says so.
- A mail server answering byte by byte is cut off at its deadline: each read
  had its own timeout, so the deadline did not hold.

**The enrolment pages**
- Replacing a mail or SMS token by the app, then reloading: the new token
  could not be confirmed - the box to confirm it and *Keep the old one* are
  there now.
- A waiting app token can be given up for another way (*Choose another
  way*).
- Wrong codes on the pages (checking an address, confirming, replacing) are
  counted per person, with a wide limit per address: one person's typos
  locked out everybody behind the same address, and right codes were refused
  as "too many wrong passwords". Each limit says what it counts. Codes not
  sent because of the per-person limit no longer use up the address's.
- *Send it again* after a reload keeps the language chosen.
- "No signal or no mail?" says the one that fits.

**The administration and the API**
- A NUL or another control character in a token's name lost its key for
  good (enrolling, renaming): refused now.
- An issuer too long for a QR code replaced the token's key and then failed:
  the picture is made first, and free-text settings have a length (issuer 64)
  and no control characters.
- A search ending in `!`, `NOT` or a bracket broke; now it says so under the
  box.
- Lists, objects, true/false, NaN or Infinity where text or a number goes are
  refused with a word (a name sent as a list made a token called `['x']`);
  numbers out of the database's range, and 1e400 through the pages, are a
  400, not a 500.
- Taking away a client, realm or directory that is not there says so, instead
  of "gone" and an event about "None"; a directory's port is 1-65535.
- Python's "invalid literal for int()" is said in words.

**The command line and the installer**
- `--upgrade` set /etc/otp to 2755: the daemon could no longer save its
  config.json after any upgrade. A folder there already keeps its mode.
- `--restore`, `--backup-info`, `--import-config`, `--export-config`,
  `--import-legacy` and `--import-totpcgi` read and write their files as root,
  before the service's account takes over: in /root they failed with
  "Permission denied", the documented recovery included.
- `--import-legacy`: a setting out of range is brought into it (a window of 25
  stopped the import half done), settings set here already are kept unless
  `--replace`, and a client at an address another client has is left out.
- `--unlock` gives the recovery codes back too, and writes an event.
- `--rejects` and `--json` alone do what they say, never start the daemon;
  `--check --json` runs the checks and exits as `--check` does.
- The installer reloads nginx once the guard for big uploads is in.
- `--help` no longer shows defaults twice; a missing folder for
  `--import-totpcgi` is an error.

**Czech**
- Short patterns no longer swallow sentences ("the port 1812 is se používá",
  "timed mimo provoz"); texts with tags are matched; plurals and some 150
  messages, events and mail and SMS steps translated; hints of boxes drawn
  later and long help for screen readers in Czech.

## 1.0.102 — 24 October 2026

- **A group picked in the directory is kept as its whole DN** - for a realm
  (*Lets in*) and for who may enrol (*May enrol*), as the administrators'
  groups already were. It is then the one group picked, matched as it is,
  with nothing to look up; the list of chosen groups shows its name, the
  whole DN on hover. Groups written earlier by their name alone still work
  (1.0.101: the one group that name is in the directory).
- **A full administrator sees the last two characters of every password
  again** - the shared secrets of the RADIUS clients, the directory's
  reading account, the database, the mail server, the SMS gateway - so that
  "the one I set" can be told from another. Every other role sees dots
  alone, and the settings' passwords not at all; an export without its
  secrets carries dots only.

## 1.0.101 — 24 October 2026

A security review of the whole application: eight separate reviews (RADIUS,
LDAP and realms, the administration, the enrolment pages, HA and upgrades,
load and concurrency, the pages, the cryptography), most findings checked on
a running pair of nodes. Nothing was found that lets anybody in when the
database, the directory, mail, SMS or the other node fails, nor any way
round the roles. What was found is fixed here.

**Codes used once - also on two nodes**
- With two replicating databases, the same code sent to both nodes at the
  same moment was let in on each; and replication, which writes whole rows,
  could write an older copy of a token over a newer one - a used recovery
  code came back. Every one-time use (a code's time step, a recovery code,
  an answered question) is now a row of its own in `token_once`, never
  changed, and a node looks in the other node's database before it lets a
  code in. Tested: one code to both nodes at once - let in once; replication
  paused - a code used on one node is refused on the other.

**Guessing codes**
- A lock after 10 wrong codes set the count back to 0: 10 more guesses every
  quarter of an hour, for ever (~870 a day against a realm that asks for the
  code alone). The count now goes on; each lock is twice as long as the one
  before (15 min, 30, 60 … up to a day), and every lock is an event. The
  token's card says until when it is locked, with *Unlock it*.
- Directory password + code: a guessed recovery code after a right password
  counted nothing, past the pause and the lockout. Each request where no way
  of splitting the password gave a right code and the directory refused it
  now counts towards the token's recovery codes: past 20 in a day they are
  not taken for a day (an event says so; *Unlock it* gives them back). The
  directory is still asked once, and codes from the app go on working.
- Each wrong code gets its own number (two at once both read "11" and the
  lock at the 10th was skipped); confirming a new token locks the same way.
- Answers to one mail/SMS question sent at the same moment were all
  compared - the 3 tries were 16. A try is now taken before the code is
  looked at.
- The pause between wrong codes is counted together by both nodes.

Every change was then checked by a review of its own, which found twelve
mistakes in the fixes themselves - fixed before this was released.

**The directory**
- **A group given by its name alone matched any group of that name anywhere
  under the base** - one an OU's administrator could make - for the realms,
  the enrolment pages and the administrators' roles. It is now the one group
  that name is: its sAMAccountName (unique in a domain), or a cn only one
  group has. Two of one cn: neither, said in the log - give the full DN.
- An administrator from the directory switched off here signed in again
  under another spelling of the name (`falco`, `falco@corp.cz`, `CORP\falco`).
  One person is now one account, found by the DN.
- Computer accounts (`PC123$`) are not people: refused.
- Locked out in AD, the password expired, or a state that cannot be read:
  refused where the realm checks accounts (`msDS-User-Account-Control-Computed`).
- `DOMAIN\name@realm` and `name@x@realm` are not names (each made a second
  token for one person).
- Names alone (`bare`) only within one directory.
- A directory server that hangs is passed over for 30 s: every sign-in of
  every realm no longer waits out its timeout first.
- An empty password, an empty DN, a control character in a password, an
  empty result code from the server: refused.

**The administration and the enrolment pages**
- *Showing keys* switched off now holds for downloading the database too: the
  copy goes without the key that opens the tokens.
- The codes in the subjects of code mails are dots in the outgoing-mail list
  (every role could read them there).
- Secrets show as dots only - their last two characters were shown.
- Sending codes from the enrolment page counts against the page's limit, and
  per destination; a code confirmed or proven is taken once even when two
  requests come together; confirming has a limit of its own.
- The same answer for a right password without a role as for a wrong one, and
  the same time for a name that is not there.
- An imported account whose password, role or state changes is signed out.
- IPv6 counted per /64 in the sign-in limits; another site's Origin refused.

**Load**
- The database connection has time limits (a statement 120 s, a wait for a
  row 10 s, a dropped line 30 s): one waiting statement held every sign-in.
- The Log, its search suggestions and the events read through a connection of
  their own: four searches of the whole log held RADIUS for 2-5 s and the
  health check failed - now ≤ 10 ms.
- Checking, the statistics and giving room back run on their own connection.
- The API closes a connection silent for a minute and takes 256 at most.
- A mail server answering byte by byte is given up after 4× its timeout; the
  outgoing-mail queue reads only the open mails every 10 s.
- At most one page waits for the other node's firewall, two for its test.

**RADIUS**
- An Accept never goes without an attribute it should carry: refused instead.
- A repeat of a request answered meanwhile gets the answer.
- That a NAS signs its requests is remembered in the database, per node
  (restarts, the other node); a new client must sign them unless let off.

**On the machine**
- Root (the command line, the installer) writes into the folders the otp
  account can write without following a link, through the open file.
- A token key that was never sealed is sealed at start and refused after.
- `$` in name checks let a newline through: `\Z`.

**Said plainly on the pages**
- The SMS gateway without HTTPS or without its certificate checked.
- Replication between the nodes without TLS checked (verify-full).

## 1.0.100 — 24 October 2026

- **Every click-through shows what it filters by.** A bar of the requests
  chart, a name, a reason, a client or an address in the overview, *Its
  requests* of a token or of a check: the Log opens with it written into
  the search box in the words it takes (`name:falco@x.cz`, `reason~"…"`,
  `from:10.1.2.3`), the result and the client in their filters, and the
  time picker set to the hour (or the window) clicked - not a window kept
  out of sight while the picker still said "last 24 hours". Each can be
  changed or cleared like anything typed.
- **Search and Clear beside every search box** - tokens, the Log, events,
  enrolment, the outgoing mail, and the restore of a backup: Search looks
  for what is typed and chosen (as Enter does), Clear empties the box and
  puts every filter of that list back (the time to the last 24 hours); it is
  lit while anything is filtered.
- **Restoring a backup, a token here already is decided one by one**: each
  has its own *keep the one here* / *replace it*, with *Keep every one
  here* and *Replace every one* for all of them; the line below says how
  many will be restored, how many replace the one here and how many are
  kept; replacing asks once more, naming them.
- The header says which node answered the page on every tab, not only on
  the overview.
- A locked backup asks for its passphrase when it is opened (and again,
  saying so, when the one typed does not open it).
- Search and Clear stand beside the search box with its suggestions, not
  wrapped under it.
- The restore's result and counts in Czech, with the right plural forms.

## 1.0.99 — 24 October 2026

- Settings → About: **what it runs on**, a column a node of the cluster -
  otp; Python, where it is, and its modules (psycopg2 with its libpq,
  PyMySQL, colorama); the OpenSSL and SQLite under it; the database server,
  pg_dump, mariadb-dump; nginx, php-fpm, the command line's PHP; the system,
  its kernel and architecture, systemd, OpenSSL, keepalived, iptables,
  firewalld. What is not the same on every node is marked. The other node's
  comes with its heartbeat (asked of the machine once an hour).
- And the pages' own PHP, as php-fpm runs it on the node that answered the
  page: its version, how it runs, OPcache, the web server, and every
  extension it has loaded with its version.

## 1.0.98 — 24 October 2026

What the review of 1.0.94 left open:

- **nginx no longer takes 4 GB from anybody on the admin networks.** A
  database put back and a new version go to `/admin/upload/` now, where
  nginx asks the daemon whether a full administrator is signed in
  (auth_request) before it reads a byte of the body; anybody else is
  answered at once, having sent 64 kB. Everything else on the admin page
  is held to 32 MB. Put into the nginx file that is there by install.sh
  (and every upgrade), where nginx has auth_request; nginx is asked first
  and the file left as it was if it does not take it - the pages then send
  the old way, as before.
- In a cluster, the time a RADIUS client was last heard from (written once
  a minute) no longer goes into the client's own row: logical replication
  sends a row whole, and that write on one node could put back a shared
  secret changed on the other at the same moment. It is kept per node now,
  and the pages show the latest of both.
- The enrolment pages: *Send it again* is there after the page is reloaded
  during the check of an address too - the address is the one the server
  keeps for that check.
- A directory server sending a damaged answer is said at once, not waited
  for until the whole timeout (up to 30 s a request).

## 1.0.97 — 24 October 2026

- **otp runs on the newest Python the distribution offers.** On RHEL,
  Rocky and AlmaLinux 9 the system's python3 is 3.9; install.sh (and every
  upgrade, from the pages too) now installs `python3.12` from AppStream
  with the database driver for it (`python3.12-psycopg2`, or
  `python3.12-PyMySQL`) and runs otp on it - faster (3.11 and 3.12 are
  some 25 % quicker than 3.9 at this kind of work), and supported by Red Hat
  for longer. Tried in order: 3.13, 3.12, 3.11, then the system's python3;
  a Python is taken only once it has shown it runs otp with the driver the
  database needs - otherwise the next one, and the old one stays.
- The choice is the link `/usr/local/lib/otp/python`: the service starts
  it, and the `otp` command is now a small script that starts otp.py on
  it (a link to otp.py ran it on whatever python3 was first in PATH). The
  root helpers (upgrades, the web side) stay on the system's python3.
  `--python PATH` picks one; `--system-python` keeps the system's.
- Checked on Python 3.9, 3.12 and 3.13: no deprecation warnings on 3.12;
  otp keeps running on 3.8 and newer.

## 1.0.96 — 24 October 2026

- **A whole backup of the tokens, and its restore.** Settings → Bringing
  tokens over: every token chosen - of every kind: the app, codes by
  e-mail, codes by SMS - as one file (`otp-tokens-NODE-DATE.json`) with its
  key, its recovery codes (used and not), how its codes come and where to,
  its language and mail form, its state, its note and owner. Chosen with the
  words of the token list, a state and a kind. Locked with a passphrase
  (scrypt, as the HA bundle) - or one made up on the page, shown once. A
  full administrator's, where keys may be shown; every backup written down.
- The restore reads it here or on another otp - which does not need this
  machine's sealing key: the backup is dropped where the .totp files are,
  the passphrase asked for if it is locked, and what it holds is shown -
  every token with its kind, where its codes go, its recovery codes left,
  its state and whether this server has one already - searched with the
  words of the token list, picked one by one or all shown, and restored,
  replacing the ones here or not.
- totpcgi's .totp files, and ZIPs of them, are read as before; the .totp
  export stays for totpcgi.
- **Mail straight to the recipients' servers with STARTTLS failed** on
  Python 3.9 (RHEL/Rocky/Alma 9): "server_hostname cannot be an empty
  string". The connection is made to the address looked up, and the
  Python 3.9 smtplib then had no name to check the certificate against -
  every receiving server offering STARTTLS (most do) was refused; the same
  through a relay given by its name. The name is set now. (Python 3.12+
  set it by itself, which is why it did not show everywhere.)
- The outgoing mail is searched with the words every list takes - fields
  offered as one types with what they hold (`to:`, `state:`, `kind:`,
  `name:`, `said~`, `tries:>2`, `node:`), `a,b`, `-not`, `*`, `~`,
  `(a OR b)` - the same search box as the tokens, the Log and the events.

## 1.0.95 — 24 October 2026

- **The outgoing mail.** Every mail goes through it - a token's QR code, a
  code to sign in with, a code to check an address. What the receiving side
  does not take at once - greylisting's "try again later" (451), a server
  away, a full mailbox - waits and is tried again by itself: after 1, 2, 5,
  10, 15 and 30 min, then every hour, for *Try a mail not delivered for*
  (24 h by default); a code to sign in with every minute while it is good.
  What the receiving side refuses for good (5xx) is shown as failed, not
  tried again.
- Settings → Outgoing mail: every mail with its state (waiting, being sent,
  sent, failed, given up), the tries, when the next one is, what the server
  said - and each try step by step. Counts by state, a filter and a search
  (`to:*@example.cz`, `state:waiting`, `kind:code`, `name:novak*`, or any
  word). A mail sent again now, or taken away - one, or every waiting /
  sent / failed one. A badge beside *Outgoing mail* says what waits or
  failed.
- In a cluster both nodes see one list (kept in the database they share,
  under keys of their own - no numbering two nodes could both give out). A
  mail is sent by the node it was made on; when that node is gone for
  5 min the other takes it over; either node's pages send one again or take
  it away.
- What a mail holds (a QR code, a key, a code) is sealed while it waits and
  thrown away once it went or was given up; the list keeps only who, what,
  when and what was said, for *Keep the list of mails sent for* (14 days).
- A token's mail not taken at once says so on the page: it waits and goes
  by itself. A code by mail greylisted is no longer "could not be sent":
  it arrives a minute later. The mail test on Settings → Mail still goes
  straight, to show every step.

## 1.0.94 — 24 October 2026

A review of the whole application, part by part. What was found and mended:

**Security**
- A token administrator could send somebody's sign-in codes elsewhere
  (changing where a mail or SMS token in use sends them): a full
  administrator's to do now, as replacing the token is. A token
  administrator could also take a token in use away and make it anew - the
  way round that same rule: taking away a token in use is a full
  administrator's, switching it off stays theirs.
- The enrolment pages: a token switched off or locked out by an
  administrator could be switched on again by its owner, "replacing" it with
  a code sent to it. Refused now at every step; a code is also sent to the
  old token only when the pages may replace tokens at all.
- A test made on the other node tried directory passwords without the limit
  a test on this node has.
- The code typed back on the enrolment pages: counted also for many requests
  at once.
- A code sent by mail or SMS is no longer taken once its token was taken
  away, made anew for the app or set to send elsewhere meanwhile.
- After a lockout ran out, one wrong code locked the token again for
  another 15 min - one guess a quarter kept its owner out. Counted from
  nothing again after the pause.
- Codes sent at once by several requests could pass the limit of codes per
  person: counted with a conditional write now.
- Mail: with "STARTTLS where offered", a server (or anybody on the way)
  offering no STARTTLS got the relay's password in plain text. Not sent
  without TLS now.
- install.sh wrote some of its files under /etc/otp through a path the otp
  account could swap for a link meanwhile (root writing over any file): it
  writes beside them and renames now.
- otp_web.py: an asking file the otp account made a link or a folder was
  never removed, and the helper was started again and again until systemd
  gave up on it (and with it TLS, VIP and firewall changes). The PostgreSQL
  log is checked again once opened.

**Reliability**
- A config.json that cannot be read (a typo in it) started the daemon on
  the built-in defaults - an empty SQLite of its own, every person refused,
  a node quietly out of its cluster. It stops now, saying why; a reload
  keeps the settings in effect.
- The database's TLS settings (db_tls, db_tls_ca) were left out of the test
  before a database setting is saved, of the cluster's bundle and of the
  move to another database.
- A rebuild from the other node that failed after emptying the tables put
  the node back in service with nothing in them; it stays in maintenance
  now until a rebuild goes through.
- A database password with "?" in it broke the replication subscriptions.
- Realms older than the switch for nested groups lost nested groups.
- The reload on SIGHUP (logrotate, every night) ran inside the signal
  handler, where it could lock up the main loop: done in the loop now. The
  daemon also notices a rotated otp.log by itself - logrotate's reload was
  refused to the otp account, and the lines went into a deleted file.
- Heartbeat and hourly work timed with a clock that cannot step back.
- The daily copy was lost when the database was away at that moment.
- The nodes picked the winner of a replication conflict by a comparison
  that followed the database's collation, and could pick differently.
- Restoring a copy could give the tables the other node's numbering for a
  moment; moving SQLite to PostgreSQL stopped on a NUL in an old row; new
  columns are pushed to the other node every hour, not once.
- IPv6 switched off on the machine with an IPv6 RADIUS address killed the
  daemon at start; said now, as a port in use is.
- `otp --tls-hsts 0` (any option given 0) started the daemon in the
  foreground.
- A file with secrets written over one already there kept its old mode;
  the HA bundle is created 0600 from its first byte; the sealing key is
  written whole before it appears.
- Mail settings with a line break in them are refused when saved.
- Changing anything of TLS on the pages dropped HSTS; a missing value is
  the two years nginx is shipped with.
- `--no-db-restart` is remembered for later upgrades (`--db-restart` allows
  it again); install.sh stops on PHP older than 8.0; the pip fallback works
  with RHEL 9's pip.
- Config import: the TLS settings and the web address are checked as the
  pages check them; an empty picture upload no longer deletes the logo.
- Pausing one direction of replication is refused when the request reached
  the other node than the page showed (behind a balancer).

**The pages**
- Settings: a certificate pasted for the SMS gateway disappeared from its
  box on coming back to the tab while the bar still counted it; a change
  made while a save was on its way could be lost; a certificate pending for
  a directory that is gone blocked every later save.
- The live lists (overview, requests, events) held back under the reader
  stayed stale until the next change; now drawn on the next tick.
- "No" on some questions closed the window behind them (throwing away a
  staged token, switching a token off, dropping a certificate request).
- The current code of a token showed an expired code when the next one did
  not come; the enrolment search ignored its time window; an upgrade
  package dropped twice was uploaded twice; the portal said "not in use"
  of a new app token while the old one went on working.

## 1.0.93 — 24 October 2026

- Tokens, finding one by where its codes go: a phone number is found
  however it is typed - 603 364 754, 603364754, +420 603 364 754, 00420…
  - the digits compared with the token's number, its country code in front
  or not. A mail address, or a part of it, is found too. Both in the plain
  search and next to other words of a search (`kind:sms 603364754`), where
  the address and the number were not looked in before; `to:603364754`
  finds the number that ends so, `to~364` one that holds it.
- The search box says it: "a name, a note, a mail address, a phone number".

## 1.0.92 — 24 October 2026

- The Teltonika gateway's certificate, read from it and imported, was still
  refused ("unable to get local issuer certificate"): a TRB sends only its
  own certificate, signed by an authority of its own ("ca") it never shows,
  and a certificate that is no root was not taken as one to trust. Every
  certificate imported for the gateway is now trusted by itself (a partial
  chain), and the strict checks meant for web servers are left out.
- After *Read it from the gateway*, a certificate whose signer the gateway
  did not send is said to be trusted as it is.

## 1.0.91 — 24 October 2026

- Making a token whose codes are sent: *Sent to* is filled in from the
  directory for the kind chosen - the mail address for e-mail, the mobile
  (or telephoneNumber) for SMS - as soon as the person is picked or their
  name is typed whole, and swapped when the kind is changed. It can always
  be changed; what is typed by hand stays. Under the box it says where the
  value came from, or that the directory has none for them.
- The enrolment pages say the same under the address or the number they
  fill in from the directory: that it can be changed.

## 1.0.90 — 24 October 2026

- The Test tab, a test made on the other node - the real cause at last:
  the other node looked for tests asked of it with a range of the key
  (`k >= 'radtest:ask:otp2:' AND k < 'radtest:ask:otp2;'`), and in a
  PostgreSQL made with the system's language collation (en_US.UTF-8,
  cs_CZ.UTF-8 - the usual on Rocky/RHEL) ':' and ';' are left out of the
  first comparison, so the range was always empty: the test sat in its
  database and was never taken. The first characters are now compared as
  they are (substr), whatever the collation. (1.0.87's message - "has the
  test in its database but did not take it" - is what showed it.)

## 1.0.89 — 24 October 2026

- The Teltonika gateway, *Check its certificate* on: the certificates it is
  checked against are imported right under it - the gateway's own one,
  read from it with *Read it from the gateway* (shown with its fingerprint
  first, trusted only with Save the changes), or the root and the chain of
  the authority that signed it, pasted or read from a file (PEM or DER).
  Each one is listed with whom it is, who signed it, until when it is good
  and its fingerprint, and taken out by itself. Kept in the database: the
  other node of a cluster has them too, and Export and import carries them.
- With certificates imported, only they are trusted; a gateway written as
  an address (192.168.1.1) is not checked for a name, one written as a name
  is. With none, the authorities of the machine, and the name.
- A certificate that does not pass says so and what to do, rather than a
  bare TLS error - and nothing is sent.

## 1.0.88 — 24 October 2026

- Settings → Codes by e-mail and SMS, drawn anew: in sections - *The
  codes* (how long, how many), *What they say* (language, a mail's form)
  and *SMS* - four even columns, each box the same width. What one way of
  sending needs (the Teltonika gateway, an HTTP gateway, a modem on this
  machine) sits together in a panel of its own under the choice, there
  only while that way is chosen - no longer a page of greyed-out boxes
  scattered among the others.

## 1.0.87 — 24 October 2026

- The Test tab, a test made on the other node: the request is written
  straight into that node's database and its answer read from there, not
  left to replication - when replication towards that node stood still or
  lagged, the test was never seen there and the page waited its 25 s in
  vain. Replication is used only when that database cannot be reached.
- When the other node still does not answer, the page says why: it took
  the test but did not finish it (a slow directory or RADIUS there), it has
  the test but did not take it (is otp running there, and which version),
  or its database could not be reached and replication is not running.

## 1.0.86 — 24 October 2026

- Settings: *Codes by e-mail and SMS* moved from *This installation* to
  the *Tokens* group, right under *The tokens*.

## 1.0.85 — 24 October 2026

- Tokens, the table: two new columns. **Codes** says how the codes come -
  the app, by e-mail or by SMS - and for a sent code where to (the address
  or the number). **Language** says the language of the codes and, for a
  mail token, whether the mail is HTML or plain text; what only follows the
  settings is shown muted.
- Tokens, finding: a new choice beside the state (every kind, the app,
  codes by e-mail, codes by SMS), and new words for the search -
  `kind:mail`, `to:*@example.cz`, `lang:en`, `mail:text`. The free search
  looks in the address or the number too. The line above the table counts
  the tokens of each kind once there is a sent one.
- The token's window fits the screen without scrolling: for a token whose
  codes are sent, the mail's form sits under the language in *Signing in*,
  and *Send a test* and *The app instead* share one row.

## 1.0.84 — 24 October 2026

- The Test tab, a test made on the other node: the code of a second window
  goes there with its State (it was left behind, and the answer refused).
  While it waits, the page says it is asking that node through the
  database, for up to 25 s.

## 1.0.83 — 24 October 2026

- Enrolling on the enrolment pages, the person chooses the language of the
  codes (and of the VPN's question), the language of the page offered, and
  for codes by e-mail whether the mail is HTML or plain text, the setting's
  choice offered. The mail that checks the address comes already in the
  language and the form chosen. An administrator changes both in the token's
  window, as before.

## 1.0.82 — 24 October 2026

- A token has a **language of its own**: the mail or SMS of its codes and the
  words of the VPN's second window are in it. Enrolling on the enrolment
  pages, a token takes the language of the page the person chose; an
  administrator changes it in the token's window (*Signing in → Language*),
  or leaves it to the setting.
- A mail with a code is **HTML or plain text**: Settings → Codes by e-mail
  and SMS → *A mail with a code is* (HTML, in the look of a token's mail, the
  plain text beside it - or plain text alone), and for one token in its
  window (*The mail is*).

## 1.0.81 — 24 October 2026

- SMS through a **Teltonika gateway** (TRB140, RUT… - RutOS), the box zigmon
  sends its texts through: Settings → Codes by e-mail and SMS → *How SMS is
  sent: a Teltonika gateway*. Its address, HTTPS (its own certificate taken
  unless checking is switched on), its user and password (sealed), and its
  interface - RutOS 7's own API (a login for a five-minute token, the modem
  asked once, `POST /api/messages/actions/send` with +420…) or the older
  Post/Get service (`/cgi-bin/sms_send` with 00420…). Sending only. As
  zigmon learned it: one message at a time with a short gap, tried again
  only where the request certainly never reached the box, and a box that
  took the message and did not answer in time is not "failed" - sending it
  again would be a second SMS. *Send a test SMS* works with it.
- *Without accents (one SMS, not two)*, on by default: a letter with an
  accent makes the whole SMS 70 characters a part; "kód" becomes "kod" and
  the code goes in one message - for every way of sending SMS.
- Fixed: since 1.0.76 the RADIUS lines for isemon (radius-detail) were not
  sent - "could not be written down: 11" in otp.log. The words of the codes
  (1.0.76) had taken the name the RADIUS packet types are kept under; the
  requests themselves were answered and written into the log as ever.
- `otp --radtest` finishes a second window: after an Access-Challenge it
  shows the words of it, asks for the code and sends it with the State, as
  the VPN client does. The Test tab does the same: a box for the code under
  the Access-Challenge, sent back with its State.

## 1.0.80 — 24 October 2026

- The enrolment pages, changing where the codes go: *Send me a code* is a
  button of full size beside the box the code goes into, said what it is for
  (the code proves the change is the person's own), and the box says "the
  code from the mail" / "from the SMS" rather than "a code from the old
  token". It no longer sits glued to *Go on*.

## 1.0.79 — 24 October 2026

- The mails of the codes (a sign-in code, an address checked on the
  enrolment pages, a test) look like a token's mail with its QR code: the
  blue band with the issuer and "VPN · Two-step sign-in", the white card,
  the greeting by the person's name, the code large in a grey box, how long
  it is good for, the warning in orange (or a note in blue), the footer -
  built of tables with the styles on each element, as Outlook shows them
  too. The plain text stays beside it for mail programs that show only that.

## 1.0.78 — 24 October 2026

- Mail → *Try it* sends two more samples, in the language picked beside: the
  mail of a sign-in code (a token whose codes come by e-mail) and the mail
  that checks an address on the enrolment pages - each with a code that
  opens nothing.

## 1.0.77 — 24 October 2026

- Active Directory: *Take old, weak certificates* on a directory - for
  domain controllers whose certificate has a 1024-bit key or a SHA-1
  signature, or that speak TLS 1.0 only ("EE certificate key too weak").
  OpenSSL's security level goes down for that directory alone; the
  certificate is still checked against its authority and the server's name
  (an old authority's certificate without the extensions Python 3.13
  insists on is taken too). The refusal now says which switch helps. The
  list of directories marks one that takes weak certificates. Command line:
  `--add-directory NAME --weak-certs on`.

## 1.0.76 — 24 October 2026

- **Codes by e-mail and SMS, and the VPN's second window** (RADIUS
  Challenge/Response, as Cisco Secure Client on ASA/FTD shows it). A realm
  says what people may choose - the app (as always), a code by e-mail, a
  code by SMS - and every kind works side by side; nothing changes for the
  app's tokens unless the realm is put in the new mode *the directory
  password; the code in a second window*.
  - A mail or SMS token holds where its codes go and recovery codes - no key
    anybody scans. Signing in: the directory password (and the groups) is
    checked, a code is sent, an Access-Challenge with a State and the words
    "Type the code sent to …" goes back; the code (or a recovery code) comes
    in the second request. Good for 300 s and once, 3 tries, at most 5 codes
    in 15 min per person, every wrong one counted towards the lockout; a
    wrong password sends nothing.
  - Kept in the database, so the answer may reach either node of a cluster;
    only a keyed hash of the code is kept. The other node's tables get the
    new columns at start, so a rolling upgrade does not stop replication.
  - The enrolment pages: who passes the realm's groups chooses a way; for
    e-mail and SMS the address or number from the directory is offered, a
    code proves it, and only then is the token made, with its recovery
    codes. Changing the address, the number or the way: the password and a
    code sent to the current one, or a recovery code.
  - SMS through a gateway's HTTP API (URL, GET/POST, JSON or form body,
    headers, a sealed key) or a GSM modem on the machine (a file into the
    spool of smstools3 / gammu-smsd). Settings → *Codes by e-mail and SMS*,
    with a test SMS.
  - Administration: the realm's *People may choose*; Make a token → *The
    codes come from*; a token's window with where its codes go, a test
    message, and *The app instead*; the log's *asked for the code*.
  - Command line: `--enroll NAME --by mail|sms --to ADDRESS`,
    `--add-realm … --methods totp,mail,sms`, `--mode challenge`.
  - [docs/codes-by-mail-and-sms.md](docs/codes-by-mail-and-sms.md).

## 1.0.75 — 24 October 2026

- High availability: the table of commands is folded away under *The
  commands*, as the balancers' guides are - opened when wanted.
- Seven more pictures for the sign-in, about the one-time passwords
  themselves: the authenticator app with its codes; how a code is made (the
  key and the time, HMAC, six digits - TOTP, RFC 6238); the six digits with
  the 30 seconds running down; the name, the password and the code; the VPN
  asking for the code; the codes in time with a step either side; recovery
  codes for when the phone is gone. In the pages' own colours, light and
  dark, moving slowly (and not at all with reduced motion).

## 1.0.74 — 24 October 2026

- High availability → *Looking after it from the command line* lists the web
  address's (VRRP) commands too: `--web-status`, `--vip-set` with
  `--vip-fqdn` / `--vip-vrid` / `--vip-iface`, `--vip on|off`, `--vip-move`,
  `--vip-return`, `--maintenance`, `--web-retry`, and keepalived's own
  `systemctl` / `journalctl` / `ip -br addr` for when the address does not
  come or does not move.
- A token's window, *The person*: the boxes of *Move to* and *Note* are the
  same width and their buttons too, so both lines end in one column.

## 1.0.73 — 24 October 2026

- Upgrade watched over the web address (VRRP): the page goes on by itself
  through every switch, there and back, with no F5. What stopped it:
  - one 401 for a moment (a node restarting, or one that has just got the
    address) made the PHP throw the session's cookie away and the page reload
    in the middle of the upgrade. Now the cookie stays, and the page asks
    whoami again (three times, two seconds apart) before it goes to the
    sign-in - a session really gone still does, within a few seconds;
  - in a tab in the background the next question was never asked again;
    now it waits and goes on when the tab is shown;
  - one answer that did not say "running" (from the node whose copy is a
    moment behind), or an error after one, ended the asking for good; now it
    asks every 3 s while it runs and for two minutes after, every 15 s
    otherwise, and an error is asked again, without a limit;
  - nginx's 502/503/504 while a node restarts count as "not reached";
  - the previous upgrade's plan, from a node a moment behind, is not drawn
    over the one running; answers to an older question are dropped.

- The picture on the sign-in waits for *Save the changes* as every other
  setting: a press on a picture, an upload, *Back to the default* and *Take
  my own picture away* only mark the change (the picture to come is outlined
  and tagged "after saving", the tab with a change has a dot), the save bar
  shows it, and nothing is changed before the save - *Put them back* drops it.
- Settings → The enrolment pages: the card of the sign-in's picture and the
  one under it have the same gap between them as every other card (the
  previews' hidden template stood between them and took it away).

## 1.0.72 — 24 October 2026

- The pictures of the two sign-ins are set apart: *The picture on the
  sign-in* has a tab for the enrolment pages and one for the administration,
  each with its own pick, its own picture of your own and its own *Back to
  the default* (the phone for the enrolment pages, RADIUS - the code - Active
  Directory for the administration, as each came; both can be picked for
  either). The switch "show it on the administration too" of 1.0.71 is gone:
  what it showed stays shown until the administration's own is picked. The
  exported configuration carries both (`art`, `logo`, `admin_art`,
  `admin_logo`); a file from 1.0.71 is read as it meant.

## 1.0.71 — 24 October 2026

- The picture on the sign-in can be picked: Settings → The enrolment pages →
  *The picture on the sign-in* shows five drawings with a preview (the
  phone as before, a 30-second clock, two keys for one door, the QR code and
  the app, a padlock with six digits), *No picture*, and a picture of your
  own (a logo: PNG, JPEG, GIF, WebP or SVG up to 512 KB; an SVG with a script,
  an event handler or a link out is turned away, and it is served with a
  policy that runs nothing). *Back to the one otp came with* returns the
  default at once; a picture of your own stays kept, to be picked again
  without uploading it, until *Take my own picture away*. It can be shown on
  the administration's sign-in too. All of it is kept in the database: both
  nodes of a cluster show the same picture, and it is in every backup and in
  the exported configuration (`logo`, `art`).
- Firewall: *Read it again* under the whole firewall works for the other node
  too - asked through the database, its root reads it and it is back on the
  page in a few seconds. A node also writes its whole firewall again every 10
  minutes, so one lost on the way (a rebuild, a restore) no longer leaves the
  other node's page with INPUT only.

## 1.0.70 — 23 October 2026

- Upgrade over the web address (VIP): the page no longer jumps back and forth
  when the address moves between the nodes during the upgrade. Each node's
  steps only go forward on the page (an answer from the other node that knows
  less does not undo what was already shown), the plan's state is worked out
  from the steps, *What root said last* keeps each node's own words with a
  switch between the nodes, and the "asking again" note has a line of its own
  so the table below no longer moves.

## 1.0.69 — 23 October 2026

- The upgrade's table keeps its columns where they are: they jumped about
  with every redraw as the bars and their words changed. "What install.sh
  said" stays open across the redraws.

## 1.0.68 — 23 October 2026

- Firewall: at the bottom, *The whole firewall* - each node's whole filter
  table as `iptables-save` shows it, every chain, OTP-IN and the jump to it
  marked (on firewalld, `firewall-cmd --list-all`). Root reads it after every
  change it makes and again on *Read it again*; the other node's is kept in
  the database, so either node's page shows both.

## 1.0.67 — 23 October 2026

- The upgrade on the pages shows how far it is: a bar for the whole and one
  for each node - waiting, taken out of service, install.sh by its sections
  (the one running is named under the bar), checking, done; red where it
  failed. The node being upgraded writes which section install.sh has
  reached, so the other node's page shows it too.
- Each node's own settings: also the RADIUS ports and the node's copies of
  the database (whether, when, how many); grouped; each node shows the value
  really in effect on it - its own (marked, with a way back to the
  cluster's), one from its config.json (marked), or the cluster's (dimmed);
  switches flipped in place; the cluster's value itself can be changed (it
  could not, in a cluster); the buttons stand one under the other.
- RADIUS: a changed port opens only that socket again - changing the
  authentication port had closed accounting for good (its port was taken
  again while the old reader still held it).
- install.sh --upgrade: the health check's rate limit was added a second time
  where the pages had put the access list in front of it; nginx refused that,
  and with it every other change the upgrade brings to the nginx file.

## 1.0.66 — 23 October 2026

- Behind the web address (VIP), an upgrade's progress stood still when the
  address moved to the other node, until the page was reloaded: an answer on
  its way was lost with the move and the page waited for it for good. Every
  question the pages ask now has a deadline (20 s, 150 s for changes; 8 s
  while an upgrade runs) - the browser then drops the dead connection, and
  the next question reaches whichever node holds the address. The upgrade
  and the rebuild of a node say "the web address is moving - asking again"
  and carry on by themselves.
- A copy's machine details say the database port in use (5432 / 3306)
  where config.json leaves it to the engine's default.

## 1.0.65 — 23 October 2026

- *Download* beside a kept copy (Settings → The database) now puts the key
  that opens its tokens - the `.key` beside it - inside the downloaded file,
  as *Download it* already did for a copy made at once: every copy taken
  from the pages is one file with everything in it. The file kept in
  `/var/lib/otp/backups/` itself is unchanged, its key beside it.

## 1.0.64 — 23 October 2026

- New guide: [docs/backup-and-recovery.md](docs/backup-and-recovery.md) -
  what there is to keep and where it is, copies against dumps, the key of the
  tokens, a backup plan (off the machine, the key apart, restore tests), and
  recovery step by step for one server and for a cluster: a wrong change,
  data deleted or damaged, a corrupt database, a node reverted to a snapshot
  or "lost", a split network, one node or both lost, the key lost, a failed
  upgrade, nobody able to sign in, a move to new hardware - and installing
  from nothing. Linked from the README and the runbook.

## 1.0.63 — 23 October 2026

- A copy of the database now carries the machine it was made on: its
  `config.json` (the database, the node's name, its place in a cluster -
  the database password left out), the host name and what was in use. It
  is shown before a copy is put back (on the pages and with
  `otp --restore FILE` without `--yes`) and by the new
  `otp --backup-info FILE`. Only to read: putting a copy back never writes
  `config.json`, which belongs to the machine.
- Operations guide: copies and dumps explained side by side - what each
  holds, where each goes back, and which to back up with.

## 1.0.62 — 23 October 2026

Export and import, copies and putting them back, and upgrades - looked at
end to end, on one server and in a cluster, on the pages and on the
command line.

**The configuration as one file - now all of it**
- The export held only the settings, clients, realms and directories. Now
  also: each node's own settings, the accounts of the pages (with their
  password hashes, with the secrets), the certificates and private keys of
  the pages and the web address, the web address, who may reach which page,
  the firewall and the mail server's authorities.
- Import puts all of that in. "Exactly the file" (`--replace`) also takes
  away what is not in the file and puts settings not in it back to their
  defaults; a setting put back to its default is in use at once. The
  account doing the import is never changed. A file of one machine put
  into a machine of another name gives it that machine's certificate.
- On the command line too: `otp --export-config FILE [--with-secrets]` and
  `otp --import-config FILE --yes [--replace]`; the pages take the command
  line's file and the other way round.
- A file with nothing to import says so.

**Copies of the database**
- Tested on SQLite and PostgreSQL, one server and a cluster, pages and command
  line: a copy, a dump, a downloaded copy and a kept copy put back give back
  everything - tokens, recovery codes, clients with their secrets,
  directories, accounts, certificates, firewall - on the same machine and on
  a new one; in a cluster the other node gets it all and replication goes on.
- On the command line a copy without a full administrator in it (one made
  on a server set up there alone) can be put back; it says how to make an
  account. The pages still refuse it.

**Upgrades from any version**
- Tested from every release 1.0.0 - 1.0.61 on SQLite and from releases across
  the range on MariaDB and PostgreSQL: tokens, recovery codes, clients and
  settings come through; copies made by any of them go back into this one.
- In a cluster, while one node is new and the other old, the other node's
  rows are taken as they come (the code step only goes up) - the newer
  guard of 1.0.60 had ignored what the old node changed in that window.
- Documented: operations (section 15) and upgrades.

## 1.0.61 — 23 October 2026

A fourth look for bugs: the PHP pages, nginx and install.sh, the pages'
scripts and their Czech, and what changed lately in the API - plus a fuzz of
every API call with odd values.

**Web pages and nginx**
- A few slow requests from anybody on the admin networks held every PHP
  worker for up to 15 minutes - the pages and the health check with them.
  nginx now takes a body whole before PHP is asked (an upgrade changes
  the installed otp.conf in place).
- `?+api=login` slipped past the sign-in limit: a parameter name of
  anything but letters, digits, _ and - is refused.
- `{}` sent from the page reached the daemon as `[]`.
- A backup the service cannot read (made by root) came down as a "200"
  with an error inside; now a clear refusal. A page closed mid-answer no
  longer writes a traceback.
- The daemon takes its port before it writes the key the pages use.
- install.sh: --admin-allow and the other lists are checked on the upgrade
  path too; a php-fpm pool changed by hand is kept beside the new one.

**Tokens**
- "Switch on" on a token that is not switched off no longer changes it; what
  was kept aside when it was switched off goes with a rename and away with a
  delete or a new enrolment.
- Switching off, on, unlocking, deleting and renaming wait for a confirm of
  the same name running at that moment.
- Recovery codes: one used on the other node at the same moment no longer
  shows as unused in the codes view, the export or after a rename; a rename
  counts the codes left correctly.
- Wrong codes for a waiting replacement no longer pause the token in use.
- "Last from" names the RADIUS client only where it was recorded.
- Ending a sign-in that is gone says so instead of writing "ended the
  sign-in of ?".

**Upgrades, cluster, backups**
- A node marked failed by the other while it waited comes back into
  service by itself; before marking, the other node's database is asked
  directly. Putting the same version in again no longer leaves a node in
  maintenance when it fails before anything was installed.
- The hourly numbering check no longer warns about the other node's rows
  being ahead (the usual thing) - it moves past them quietly.
- Copies take their name exclusively: the daemon and a root --backup in the
  same second no longer write the same file.
- Firewall ports: only ASCII digits.

**The pages**
- Log: past 20 000 rows the pager says "more than" and no false last page.
- A chart bar on a day the clocks change opens exactly that bar; the y-axis
  is as wide as its numbers.
- The time picker's ‹ › stay on whole months / weeks / days.
- A change made while settings were being saved is kept; a secret left as
  dots no longer sticks on the bar.
- Settings search finds Czech words.
- "Not in use while …" follows the choice.
- Firewall, certificates and the web address: a late refresh no longer
  overwrites a newer one.
- "Back in service" no longer leaves two windows; "End it" asks first;
  "Make it" and per-node Save once per press.
- About 50 more texts in Czech.

## 1.0.60 — 23 October 2026

A third look for bugs: the cluster's replication, the firewall and the web
address, and the LDAP and RADIUS protocols.

**Replication between two nodes**
- A row made on both nodes under the same name (one person enrolling on
  each, the same meta key, a first directory sign-in retried on the other
  node) stopped the replication for good on the duplicate. Now the same one
  of the two is kept on both nodes and replication goes on.
- A token changed on both nodes at once: each part keeps the newer change
  and both nodes end up the same - a token switched off is no longer
  switched back on by a sign-in on the other node, a lockout is no longer
  lost, a new key is not overwritten with the old one.
- Recovery codes: new ones made where the list was empty reached the other
  node and were then wiped on both - fixed; one code used on each node at
  the same moment no longer brings either back.
- Never two rebuilds at once (both nodes emptied), and the rebuild asked on
  the page is refused on the other node behind a balancer. Writes waiting
  while a rebuild started are refused properly. `--ha-join` stops the
  daemon while the rows come over.
- Each node checks every hour that its table numbering is ahead of the rows
  (after a restore on the other node).
- The disk test of the tuning page no longer writes a key both nodes share.
- Said in the documentation: within the replication's lag a TOTP code can
  be taken once on each node; send one person to one node where you can.

**Firewall and the web address**
- otp's chain lets in loopback, answers to this machine's own connections
  (LDAP, DNS, mail, replication) and IPv6 neighbour discovery before any
  rule: a DROP rule of yours broke sign-ins and the health check.
- The other node is let in on every port (its answers too).
- 2000 rules at most (200 RADIUS clients refused the whole request before);
  a range counts as two ports, a port with a newline is refused; the
  cluster's addresses come first in the allow lists.
- A failed apply on a machine with no rules before takes otp's chain out
  again; iptables' real message is shown.
- Each change is applied once, not twice.
- The default preferred node of the web address is the same on both nodes.
- "Who may reach the pages" checks your own address everywhere it can be
  set; a host name as the other node is resolved.
- PostgreSQL's log is read without following links, with its time zone.

**LDAP**
- Busy / unavailable / unreadable answers try the next domain controller
  instead of calling the password wrong; a server announcing its shutdown is
  left at once; a malformed answer fails at once.
- One search has a time limit as a whole; a sign-in's groups at most 20
  pages. Ranged memberOf is read.

**RADIUS**
- A Status-Server (or monitoring) no longer makes a client require a
  Message-Authenticator for every later request.
- The accounting port writes refused packets sparingly, and checks a
  Message-Authenticator where there is one.
- Empty attributes, Tunnel-Type values over 3 bytes and vendors with a
  different layout (WiMAX, USR, Lucent, Starent, MS-MPPE keys) are refused
  in the answer's lines instead of going out wrong.
- The test client refuses passwords over 128 bytes, checks the answer's
  length and Message-Authenticator.

## 1.0.59 — 23 October 2026

Errors under load, a fuzz of the RADIUS port and a second review of the
parts not looked at before (enrolment, mail, upgrade, rename, backups, CLI).

**Under load and with the database gone**
- The database unreachable: RADIUS requests go unanswered instead of being
  refused, so the VPN asks the other node (a refusal refused everybody
  until the database was back). The NAS's repeat is tried again.
- Log lines that can come thousands of times a second (database gone, a
  broken packet, a write-down that failed) are written once in a while
  with how many were left out - a 10 s database outage under load wrote
  50 MB of log. Housekeeping waits for the database without a traceback
  every 5 s.
- A User-Name with a NUL byte in it (fuzz) broke every such request and
  its write-down on PostgreSQL: NUL is now replaced before it reaches the
  database.
- Load on both nodes at once: the tokens stay the same on both.

**Enrolment and tokens**
- The enrolment page could bind a person to another person's token of the
  same bare name in a realm on a different directory: only names whose
  realm reads the same directory count now.
- Wrong codes while confirming a replacement no longer lock the token
  still in use; past the lockout count the new key is thrown away.
- Enrol, confirm, cancel and replace for one name go one at a time: a
  confirm landing on a key written meanwhile made an unproven key active.
- A pending token switched off and on waits for its code again instead of
  coming into use.
- The hourly fill of names no longer brings a deleted token back empty.
- A locked token's confirm says "locked out", not "rate limit".

**Upgrade, rename, backups**
- A node running the new version whose checks failed stays in
  maintenance instead of going back into service broken.
- A node that dies mid-upgrade is marked failed by the other after the
  timeout - the plan no longer runs for ever.
- install.sh from the pages has its own 20 min deadline (systemd 25,
  the daemon 30); a stopped helper says so.
- The opt→otp rename remembers each step as it is done: a half-done
  rename no longer leaves config.json with the old names.
- A copy put back without its key says loudly when its tokens do not open.
  The dump download reminds that the key is not in it.
- Copies are written under a temporary name and get a name of their own
  (two in one second overwrote each other); made by root, they belong to
  the service. The nightly dumps count as the latest copy.
- `--ha-resync` is root only; `--ha-join` throws away local tokens only
  with `--discard-local`; `--enroll` over a token in use and
  `--delete-token` ask (or take `--yes`).

**Mail, isemon, the rest**
- Going straight to the recipients' MX, TLS where offered no longer checks
  their certificate (a self-signed one failed every message); "required"
  still does. `mail_dns` is used even with dnspython installed. One 60 s
  deadline over all MX of a domain.
- A TCP isemon target that cannot be reached is left alone for 15 s - 5 min
  instead of holding every line 5 s (the queue filled and local files lost
  lines).
- The pages read the API port from /run/otp/api-port: changing api_port
  no longer breaks them.
- Overview day bars follow local midnight across summer time.
- The sign-in throttle map is tidied at most every 30 s and capped.

## 1.0.58 — 23 October 2026

- Tokens: beside the address a token was last used from, the RADIUS client
  it came through (the ASA, a test client…) - in the list, in the token's
  window and in the overview's "Used last". Kept from now on with every
  sign-in; for the ones before, the client whose address it is. Searchable
  as `client:ASA` (sign-ins from now on).

## 1.0.57 — 23 October 2026

A review of the whole application - security, bugs and speed - and what it
found, fixed. Also: the answer's lines written with help.

**The answer's lines, with help (Settings → Realms)**
- Ctrl+Space (or typing a name) lists what an Access-Accept can carry - the
  standard attributes and those of Cisco ASA/FTD, Cisco IOS/ISE, FortiGate,
  Palo Alto, Check Point, Juniper, Citrix NetScaler, F5, SonicWall, Aruba,
  MikroTik, Microsoft, pfSense, Zyxel - each with what it does, its vendor
  and number, and an example; after "=" the values of a numbered one (VLAN,
  IEEE-802, Administrative-User…). A product to narrow it to, with what that
  product reads (WatchGuard, Sophos, OpenVPN AS, Ivanti, UniFi, Horizon UAG
  too), ready-made lines (VLAN, an ASA group policy, a FortiGate group…),
  and every line checked as it is typed. The group lines have the same.
- About 70 vendor attributes can now be sent (Vendor-Specific); any other as
  `Vendor-<vendor>-Attr-<number> = value`. docs/reply-attributes.md lists
  them product by product.

**Security**
- Root's files could be written into through an IPv6 scope id
  (`fe80::1%…`), which Python keeps with any character in it: addresses are
  now plain addresses only, checked by the daemon and again by root, in the
  firewall rules, the page allow lists, the web address, RADIUS clients and
  certificate names.
- Root no longer trusts what it wrote last in the otp account's folder
  (status.json): every value it uses again is checked again.
- BlastRADIUS: an Access-Request with Proxy-State and no
  Message-Authenticator is refused (as FreeRADIUS's limit_proxy_state); "has
  sent one before" is remembered per address of a client, not per client.
- MS-CHAP, EAP, CHAP-Challenge and Tunnel-Password are never written into
  the log or sent to isemon.
- A realm's or a group's answer that cannot be built refuses the sign-in
  instead of letting in without the attributes that limit it; two accounts
  answering to one name are refused, not one of them taken by chance.
- A token locked out or paused is refused before its directory password is
  tried (no free AD password guessing).
- A token administrator can no longer replace a token in use (and receive
  its new key) or rename one: a full administrator's to do.
- Testing a code (Tokens) and the RADIUS test are counted per administrator,
  as sign-ins are; changing one's own password is counted too; a switched-off
  account is told "wrong name or password", like any other failure.
- Database and cluster settings can no longer be changed through
  Settings or an imported file (only by their own steps); a joining node's
  bundle and name are checked as settings are.
- Looking a person up in the directory needs a token administrator; the
  firewall page a token administrator too; reading PostgreSQL's log is an
  event; the admin allow list cannot be saved shutting out the one saving it.
- The RADIUS shared secret typed into the load balancer guide is not kept in
  the browser; a node name in a question is shown as text.
- Log lines cannot be faked through a user name (a new line continues
  indented).

**Bugs**
- LDAP: a domain controller that takes the connection and then says nothing
  no longer stops every sign-in - the next server is asked.
- A right code sent twice (a NAS asking again, or the other node) is refused
  but no longer counted as a wrong code towards the lockout.
- Two replicating nodes: a code or recovery code used on one could come back
  when the other wrote anything in the same token's row (PostgreSQL sends the
  whole row) - a trigger keeps the newer one.
- Settings and meta written on both nodes at once no longer stop replication
  on a duplicate key (one statement, not SELECT then INSERT).
- Rebuilding a node: nothing else writes meanwhile, the other node's
  subscription is made before this node writes again, and the numbering is
  put right whatever happens.
- The firewall: when anything fails half way, the rules and the files go
  back to what they were; firewalld refusing VRRP is said; files put back
  get their SELinux label.
- The web address's draft is taken from the server until something is
  changed (a later save no longer undid a move or turned the address off);
  edits made while saving are kept.
- A CA pasted for a directory goes to that directory, whichever is picked
  when saved.
- Lists: only the newest answer is drawn; they are not redrawn under
  somebody reading them; a page further back than 20 000 rows is said, not
  shown as page 200 again.
- The time picker: ‹ › by whole days, weeks, months; "yesterday" right
  around a change of summer time; a fixed start stays fixed.
- The overview's bars are on the local clock and there is no empty bar at
  the end.
- Signed out with changes not saved: said once, not "leave the page?" every
  five seconds.
- Smaller ones: a null setting no longer counts as changed; the refused
  setting is the right one; two job watchers, a second timer of the code
  tile, listeners left behind by every token window, "Make it again" pressed
  twice on the enrolment page.

**Speed**
- RADIUS: requests older than any NAS waits (15 s) are dropped after a
  stall instead of being worked through; a flood of made-up packets is
  written down once a minute, not row by row; past 10 000 refusals waiting
  out their delay, more are dropped rather than answered at once.
- PostgreSQL: TCP keepalives, so a connection lost in a failover is found in
  about 20 s; MariaDB: read/write timeouts.
- Search suggestions never group a whole log (30 days at most, never the
  event texts); the overview is kept 20 s; /healthz asks the database at
  most once a second; the event kinds are kept a minute; the enrolment tiles
  are one query.
- Forgetting old records and tidying go in batches with a breath between;
  tidying, directory names and the nightly copy run in threads of their
  own, so the heartbeat never waits for them; one node of two tidies.
- The pages ask for a pane only while it is in front and the tab is
  visible.

## 1.0.56 — 23 October 2026

- Every card of Settings saves through the bar at the bottom, as the
  settings themselves do - checked card by card:
  - High availability → the web address: its address, name, VRRP id, each
    node's interface, where it goes back to, and on/off (now a switch) are a
    draft until **Save the changes**; **Put them back** throws it away.
    Turning it off asks when saved (twice). *Move it here* stays a button:
    it is something done now, not a setting.
  - Active Directory and Mail → the certificate authority: pasted or read
    from a file, it is added on Save the changes (no Add it button).
  - The firewall (1.0.54) goes through the same: one bar for everything
    changed on the page, saved one after the other, stopping at the first
    that is refused.
  Lists edited in a window of their own (clients, realms, directories,
  accounts, a rule) and actions (backups, upgrades, replication) are as
  they were.
- The cluster's History can be cleared (asked twice): what the nodes wrote
  down by themselves is deleted; what was done by hand stays in Events and is
  no longer shown in the History.

## 1.0.55 — 23 October 2026

- The web address showed "holds it" on both nodes, with "On both nodes at
  once: they do not hear each other", though only one held it. Whether a
  node holds the address was asked by binding to it, and since 1.0.51 the
  web address turns net.ipv4.ip_nonlocal_bind on (so nginx can listen on
  it) - with that, the bind succeeds anywhere. It is now read from the
  kernel's own list of the machine's addresses (/proc/net/fib_trie,
  /proc/net/if_inet6). The cluster's History no longer says the address
  came to a node that never had it, and "it stays where it is" follows the
  node that really has it.

## 1.0.54 — 23 October 2026

- Firewall and access waits for the save bar, as the rest of Settings does:
  who may reach the pages, otp's firewall on or off, its rules turned on or
  off, the rules of your own (added, changed, moved, taken away) are a draft
  until **Save the changes**, and **Put them back** throws the draft away.
  A rule is checked by the daemon as soon as it is added or changed. Turning
  otp's firewall on or off still asks first when saved (off asks twice).
  One event says everything that was saved.

## 1.0.53 — 23 October 2026

- A time picker everywhere a list has a time window, as in isemon: the
  Overview (the chart and everything under it), the Log, Enrolment, Events
  (new there - all time by default) and the cluster's History.
  - Quick ranges: the last 15 minutes, hour, 6 and 24 hours, 3 days, week,
    month, 3 months, year (and all time where it makes sense).
  - By the calendar: today, yesterday, this week, last week, this month,
    last month.
  - The last N minutes, hours, days or weeks, typed in.
  - From - to by date and time (to empty: up to now).
  - ‹ and › move the window back and forth by its own length.
  - Each list remembers its window in the browser.
- The Overview's names, reasons, clients and places open the Log on the
  same window as the Overview.
- The API takes the window as `from` and `to` (seconds since 1970) on
  /api/events, /api/enrolment and /api/ha/history, and `since`/`until` on
  /api/dashboard and /api/activity.

## 1.0.52 — 23 October 2026

- Settings → Firewall and access, new:
  - **Who may reach the pages** - the enrolment pages, the administration and
    the health check (/healthz) each for everybody or only from the networks
    given (IPv4 and IPv6). nginx says it page by page (the allow lists of
    otp.conf, the web address's server with them); the other node, the web
    address and the machine itself are always let in.
  - **The firewall** (iptables and ip6tables): turned on, otp keeps a chain
    of its own, OTP-IN, first in INPUT on every node, and in
    /etc/sysconfig/iptables and ip6tables between marks of its own, so it is
    there after a reboot (the file is checked with iptables-restore --test
    before it is written; the rest of it, comments included, is left as it
    was). Turned off, the chain and its jump go and nothing else changes.
  - What otp's functions need is let in by itself and changes with them:
    HTTP/HTTPS (to the networks of the page lists), RADIUS only from the
    RADIUS clients set up, SSH, ICMP/ICMPv6, DHCPv6, and inside the cluster
    always the other node (PostgreSQL replication, its pages) and VRRP once
    the web address is on. The optional ones can be turned off one by one.
  - Rules of your own: accept, drop or reject; TCP, UDP, ICMP, VRRP or any;
    a port, a range or several; from an address or a network; IPv4, IPv6 or
    both; for all nodes or one; in an order of your own, looked at right
    after the other node of the cluster (which nothing can shut out) and
    before the rest of otp's.
  - Each node's state (in place, waiting, failed with root's words, with
    Try again) and the rest of its firewall, read only, IPv4 and IPv6.
  - firewalld running: otp leaves the firewall to it and says what to do.
- docs/firewall.md: the same, and how to do it by hand.
- Settings → High availability → The load balancer: a guide for each kind,
  folded until opened - HAProxy, nginx (with RADIUS over UDP), Apache, F5
  BIG-IP, Citrix NetScaler, keepalived + LVS, Cisco ASA, FortiGate, and how
  to check it. Filled in with this cluster's real node names, addresses,
  RADIUS ports and name, marked in colour, and with what is typed in above
  them (the balancer's address, the name, TLS ended or passed through, the
  health check, the shared secret - which only goes into the text); each
  block has Copy. Whether the nodes already trust the balancer's
  X-Forwarded-For is said, with the command when they do not.
- Replication's errors: the count in the table is a button - what PostgreSQL
  said about it, from its own log (root reads only the lines about logical
  replication), each with a sentence on what it usually means and what to
  do; errors and warnings or everything about replication. **Clear them**
  counts from then on (PostgreSQL's own count goes on).
- **History** (High availability, top): what happened to the cluster, day by
  day - the web address coming and going, a node's health, a node stopping
  and answering again, maintenance, replication paused, stopped, running
  again, new errors, a slot about to be lost - written by the nodes as they
  see it - and what was done by hand, filtered by kind.
- The web address: **where it goes back to** - always back to a node chosen
  (as before; the default is the first node), or **it stays where it is**:
  after a failover it does not come back by itself, only when the node that
  holds it fails or it is moved by hand. On the command line:
  `otp --vip-return NODE|stay`.
- Anything that destroys something is asked twice: the button in the popup
  turns into "Really? This cannot be taken back" with the button again.
  Switching a token off, throwing a new token or an uploaded package away
  now ask first too.

## 1.0.51 — 23 October 2026

- The web address's own certificate is answered on its IP address too, and
  to a client that sends no name - not only for its name. nginx listens on
  the address on both nodes (net.ipv4.ip_nonlocal_bind), so the node that
  takes the address over answers on it at once.
- DH parameters the node has made for itself serve the web address as well
  when the same are chosen: made once, not twice.
- The certificate cards stand level: each says under its name which
  certificate it is, the badge always top right.
- The web address's card shows, node by node, whether its certificate is in
  place, and how far root is when it is still being put in.

## 1.0.50 — 23 October 2026

- The buttons of a certificate's card are all the same size, two by two;
  *Download* and *Stop managing…* are buttons of the same size as the
  others, not two small icons.
- What root is doing on a node shows as a bar with a percentage on its card:
  the steps done, and while DH parameters are made, the time gone against
  the time it usually takes (2048 bits seconds, 4096 bits up to ten minutes).
- DH parameters are made before nginx's file is read, so an upgrade that
  runs while they are being made is never written over with an older copy
  of the file.
- Nothing in the settings menu or on the buttons is cut short any more: an
  open menu wraps a long name; the certificate buttons are named shorter
  (Upload, Request (CSR), Self-signed, TLS settings, Download, Let go) and wrap if they must.
- The box for pasting PEM is much bigger and shows the usual order in it:
  the certificate, the intermediates, the root, the key (any order is taken).
- The web address's card says what it is: the certificate of the cluster's
  VIP, answered on that address whichever node holds it.

## 1.0.49 — 23 October 2026

- The web address (VIP) is set, watched and moved on *Settings → High
  availability*, beside the nodes and the replication; *Settings →
  Certificates and TLS* keeps the certificates (the web address's own
  among them).
- *How it speaks TLS* made clearer: the four choices as tiles that say what
  each means and who can connect, the ciphers each uses shown on demand,
  the protocols of your own as switches, HSTS as one row of choices.

## 1.0.48 — 23 October 2026

- A node renamed (node_name) carries over, at its next start, everything
  kept under its old name: its own settings, its maintenance, its
  certificate and TLS settings, its place in the web address; the old name
  leaves the list of nodes. A rename made before this version: once
  `otp --ha-renamed OLD` on that node.
- docs/operations.md: how to rename a node, and that *What to call this
  installation* is the cluster's name, not a node's.

## 1.0.47 — 23 October 2026

Certificates and TLS
- *Settings → Certificates and the web address*: a card per node and one for
  the web address - the certificate, who issued it, until when (a bar that
  turns orange three weeks before), its names, key, chain and root, whether
  the chain leads to the root, the TLS settings, and whether it is in place.
- Upload a certificate as PEM files (certificate, key, chain, root - any
  order, or all in one) or as PFX / PKCS#12, with a password or without
  (old PFX files too, and keys with a passphrase); or make the request (CSR)
  here - the key stays here - and upload only what the authority sends
  back; or make a self-signed one. The certificates are sorted by
  themselves and the chain checked against the root.
- TLS per node and for the web address: Standard, Mozilla intermediate,
  Mozilla modern or custom protocols and ciphers; DH parameters (RFC 7919
  groups, or made on the node); the server choosing the cipher; HSTS.
- Root puts it in through a new helper (otp_web.py, otp-web.path): every
  value checked, nginx asked before it is reloaded and every file put back
  when it says no.
- Command line: otp --web-status, --tls-import, --tls-preset, --tls-dh,
  --tls-hsts, --tls-for.

The web address (VIP)
- In a cluster, one more address for the pages, on one node at a time,
  held by keepalived (installed by itself). It leaves a node that goes into
  maintenance, is upgraded or rebuilt, whose own /healthz (nginx, PHP, the
  daemon, the database) fails, whose RADIUS stops listening, or that is gone;
  and returns to the node it is meant to be on once that is well. Moved by
  hand on the pages (*Move it here*) or with otp --vip-move; on and off with
  otp --vip. Its own name and certificate (nginx answers it by SNI). RADIUS
  stays active/active on the nodes' own addresses.
- With it off, a load balancer of your own works as before.
- keepalived's check is put in /usr/libexec/keepalived, where SELinux lets
  keepalived run it.

Health checks
- /healthz?check=radius also says whether RADIUS listens (for a balancer of
  UDP 1812/1813); /healthz?check=all also whether replication runs (for
  monitoring).

The cluster on the command line
- otp --ha-compare: every table counted on both nodes, side by side.
- otp --ha-standalone: leave the cluster and go on alone keeping everything -
  replication and its slots taken away, the other node forgotten,
  config.json a single server's again.
- otp --ha-forget NAME: a node off the list.
- otp --ha-resync stops otp on the node while it is rebuilt (its heartbeat met
  the rows coming over) and makes a copy of what was there first.
- otp --ha-status: errors counted earlier no longer mark a running direction
  as failed.

Documents (docs/)
- operations.md - the runbook: a fresh install, PostgreSQL 16 on AlmaLinux 9,
  moving from SQLite, building the cluster, every-day checks, upgrades,
  OS updates, a node down for a while, a split network, a node lost for good,
  "lost" replication, leaving the cluster, changing an address, copies,
  back to SQLite, the key, a lost password, troubleshooting.
- tls-and-vip.md - certificates, TLS, the web address, and what to open in
  firewalld, iptables and nftables.
- load-balancers.md - HAProxy, nginx (and nginx Plus), Apache, F5 BIG-IP,
  Citrix NetScaler, keepalived/LVS, Cisco ASA, with health checks that look
  at the whole node.

Other
- install.sh keeps its copies of nginx's file in /etc/nginx/otp-backups (the
  last ten), no longer beside it in conf.d.

## 1.0.46 — 23 October 2026

- A click on a recovery code that is still free copies it to the
  clipboard, and so does a click on the key beside the QR code (without
  its spaces) - in the administration and on the enrolment pages. The tile
  flashes green and a message says what was copied.

## 1.0.45 — 23 October 2026

- High availability: every line of the Log (requests and checks of a code),
  of the events and of the enrolment pages says which node wrote it - a
  *Node* column in a cluster, in the details of a request or a check, and
  the field `node:` in the search box (`node:otp2`). Lines written before
  this version have none.
- Test: in a cluster the test can be made on any node that answers (*On
  the node*). It is asked through the database both nodes open, the
  password sealed with the key both have, and answered by that node as if
  asked on its own pages; the answer says where it was made.
- Upgrading a cluster: the new column has to be on a node before the other
  sends it rows that carry it. Upgraded from the pages that is so by itself
  (the other node goes first); by hand, upgrade the node that is not
  answering the pages first - until both are, replication waits and then
  goes on by itself.

## 1.0.44 — 23 October 2026

A review of the whole application for bugs; what it found, put right.

Security
- Enrolment pages: somebody with only the directory password could get a
  second token for the same person by signing in under another spelling
  (DOMAIN\\name, another realm on the same directory, other letters' case).
  The token the person has already is the one the session is about now.
- The sign-in limit per name counts the person, not the spelling: DOMAIN\\ro,
  ro@anything and Ro are one name.
- *Code now* needs "show the key of a token" switched on, as the key itself
  does, and every look is written down by the server whatever the page
  says (once per five minutes per person and token).
- Upgrades from the pages: root's helper works on the upgrade folder through
  one descriptor opened once, so the otp account cannot swap the folder for
  a link between two of root's steps; a FIFO put in a file's place no longer
  holds it up; a package's headers are counted as they are read, not all
  read first. install.sh makes the folders inside /var/lib/otp as the otp
  account (root's install -d followed a link there). Release keys a new
  version no longer ships are no longer trusted.
- MariaDB: names are compared byte for byte, as SQLite and PostgreSQL
  compare them; novák@x.cz and novak@x.cz were one token, and one person's
  token was written over the other's. Existing tables are changed once.
- A wrong code on the confirm page counts toward the lockout, not only the
  short pause.
- The replication password never reaches PostgreSQL's log: the other node's
  database is tried first, and a subscription that would fail is not sent.

RADIUS and the directory
- Proxy-State is sent back in every answer (RFC 2865): behind a RADIUS
  proxy every answer was thrown away.
- Status-Server on the accounting port is answered (RFC 5997).
- An answer too long for a packet (too many reply attributes) is a logged
  refusal instead of no answer at all.
- A directory given as [IPv6]:port works.
- A connection to a domain controller that drops during a sign-in is "could
  not be reached", and the next one is asked - not "wrong password".
- Directories reloaded no longer vanish for a moment under a request.
- Wrong codes are counted in the database itself, so two nodes do not lose
  each other's counts.

The database, upgrades, high availability
- Putting back the oldest kept copy works; the safety copy made first
  rotated that very copy away.
- Putting a copy back keeps this machine's maintenance, heartbeats, upgrades
  and jobs (and, in a cluster, the other node's).
- In a cluster a copy sealed with another key is refused before anything is
  replaced.
- A cancelled upgrade finishes the node that had begun: one that drained
  goes back into service, one that installs is checked.
- A node waits for the other to be alive and in service before it leaves
  for its upgrade - never both out at once.
- A node whose install.sh does not finish in 10 minutes is marked failed,
  not done.
- *Forget the package* removes its pieces from the database (it removed
  none), and a new package removes every older one's.
- Rebuilding a node from the other: nothing of its own is written while the
  rows come over (it answers nothing meanwhile), so the copy no longer stops
  on a duplicate key.
- A daily backup set as 3:30 runs (only 03:30 did).
- The disk speed probe measures a real write.
- install.sh --upgrade: a machine installed without the pages is upgraded
  without them; a failed upgrade starts the daemon again and brings the node
  back into service; it never moves the machine's PHP to Remi by itself; a
  retry keeps the first copy of the nginx configuration. --uninstall waits
  for an upgrade going on and says what it leaves (certificate, firewall).

The pages
- A popup over a popup that opened nothing (Back in service, a failed
  request) froze the page; it cannot now.
- *Code now* stops asking once its window is closed.
- *Make new ones* (recovery codes), *Check it* and *Look a name up* are
  shown only to who may use them.
- Saving a client before its realms were read no longer clears the realms
  it may use.
- A role the server refused is not left showing in Accounts.
- The Test tab names an answer that is neither accept nor reject as it is.
- Directory buttons and long buttons wrap at phone width.
- A few untranslated texts translated.

The API and the command line
- Imports check every realm's directory before saving anything, and what
  was saved is in use even when something after it was refused.
- A field of the wrong kind is a 400 with a reason, not a 500.
- Renaming a token follows the same rule for names as a new token.
- /api/portal/me says nothing once the enrolment pages are switched off.
- otp --set-role needs --role and keeps the last full administrator;
  otp --passwd ends the account's sign-ins; otp --restore takes every kind
  of copy, makes a safety copy and uses the key that came with it; bare
  otp shows the status again; --delete-token removes what was kept beside
  the token; --scratch is written down; --tokens --limit is honoured;
  ordinary mistakes are one line, not a trace.

## 1.0.43 — 23 October 2026

- High availability: on a node that is one of two already, *Making it two*
  no longer warns that PostgreSQL is on this machine (127.0.0.1) - with
  replication each node has its own and the other never opens it. The
  check says so in green, and the steps are folded away behind *Show how
  it was made*.

## 1.0.42 — 23 October 2026

- *Try a code*: the marked answer takes the place of the line under the
  row at the same height, so the token window does not grow and gets no
  scroll bar after a try.

## 1.0.41 — 23 October 2026

- *Code now* keeps its size: the tile is as big with the code shown as
  before it, and the other tiles beside it do not move.
- Shown, a click on *Code now* copies the code (without the space) to the
  clipboard; the tile flashes green and a message says so.
- *Try a code* marks its answer: a green "✓ RIGHT" or a red "✗ WRONG"
  label with the reason, and the code box goes green or red until it is
  typed in again.

## 1.0.40 — 23 October 2026

- The token window has a tile *Code now*: pressed, it shows the code the
  phone shows at this moment, with a ring counting down its seconds, and
  goes on to the next code by itself. A full administrator only; every look
  is written in the events.

## 1.0.39 — 23 October 2026

- The buttons at the end of a row in Tokens, the Log and the other lists are
  a cell of the row like any other, as in Settings: no colour or place of
  their own. A table wider than its card scrolls sideways.

## 1.0.38 — 23 October 2026

**Small things on the pages.**
- The database card's window shows what the database holds as a table: what
  each table is, its name, its rows and its room with a bar, biggest first;
  and the copies with their size, when they were made and whether the key is
  beside them.
- *Open Upgrades* (and every card's button to its settings) opens that very
  page of Settings, not whichever one was open last.

## 1.0.37 — 23 October 2026

**The program is called otp - everywhere.**
- Until now it was installed as "opt". From this version on everything is
  otp: the service `otp.service` (`systemctl status otp`), the command `otp`,
  `/usr/local/lib/otp/otp.py`, `/var/lib/otp`, `/etc/otp/config.json`,
  `/var/log/otp/otp.log`, `/var/www/otp`, the accounts `otp`, `otp-web` and
  `otp-www`, nginx's `/etc/nginx/conf.d/otp.conf`, the php-fpm pool, the
  logrotate and polkit files, the SQLite file `otp.db`, the copies and dumps
  (`otp-…`), the package `otp-X.Y.Z.tar.gz`.
- `install.sh --upgrade` from an opt installation renames all of it once,
  keeping every setting, token, account and log: the accounts are renamed
  (so every file keeps its owner), the folders moved, nginx's file kept with
  its host name and allow lists, the certificate kept.
- The databases too: a PostgreSQL or MariaDB on the same machine has its
  database and account opt renamed otp (pg_hba.conf with them). One on
  another machine keeps its names, written into config.json. Replicated, the
  publication, the subscriptions and the slots become `otp_pub` and
  `otp_from_N` on both nodes without stopping or losing a row - whichever
  node is upgraded first, the second finishes it.
- Copies and dumps made under the old name are still listed and put back.
  Nothing else answers to "opt" any more.

**Upgrades from the pages, one node at a time.**
- *Settings → Upgrades*: send the released `.tar.gz` and press *Upgrade*.
  One server is put in and restarted; a cluster is upgraded node by node -
  each taken out of service, upgraded, checked (its database, RADIUS, the
  replicated tables read again) and brought back before the next begins. A
  failure stops it there with what `install.sh` said; *Stop it* leaves the
  rest as they are. `otp --upgrade-status`, `otp --upgrade-cancel`.
- Nothing is installed by the service itself: root does it, through
  `otp-upgrade.path` and `otp-upgrade.service`, after checking the package
  again from a copy of its own. Every release is now **signed** (`MANIFEST`,
  `MANIFEST.sig`, Ed25519): a package changed or signed by a key the server
  does not know is refused, as is one older than what runs.
- The command line works as it always has. This version has to go in on the
  command line once - that installs the units and the release key.
- docs/upgrades.md: both ways, and the operating system too.

**Maintenance.**
- A node in maintenance answers no RADIUS request and its `/healthz` says 503,
  so the VPN and the load balancer use the other one; its pages go on
  working. *Settings → Upgrades*, the Overview, or `otp --maintenance on|off|status`.
- `install.sh --upgrade` takes the node out of service while it works and
  puts it back once the new version answers.

**A cluster: each node's own settings.**
- The address RADIUS listens on, the API port, the mail HELO name, the isemon
  host name and the debug switches are now kept per node (*Settings → High
  availability → Each node's own settings*); before, one node's address was
  given to the other too. Everything else is the cluster's, as before.

**The Overview.**
- The four cards open what they count, as isemon's do: who was let in, why
  people were refused, the tokens (locked out, used last), isemon.
- Four more: this server (version, uptime, RADIUS, problems), high
  availability (nodes, replication), the database (size, the last copy, the
  key) and maintenance and upgrades - each opening its details.

**Moving between databases.**
- After a move, making a copy or a dump was refused for ever: the copy made
  at the start of the move held the move as "going on", and the new database
  kept showing it. Such notes are no longer carried over, and a job whose
  process has gone is taken as ended.
- After *Set it up*, the steps after it did not find the password it had just
  made ("no password supplied").
- The database's address can no longer be saved with the save bar: saved,
  the next restart opened a database nothing had been carried into. The four
  steps are the only way.
- *Start using it* refuses a database that holds an older copy (left by an
  earlier move): empty it and carry everything across first.

**Smaller.**
- `systemctl status otp` works: the unit has the alias `otp.service`.
- Fact tiles wrap long words and addresses instead of running over their
  border.

## 1.0.36 — 23 October 2026

A second detailed pass over the whole program - the server, the pages, the
enrolment pages, PHP and the installer - and what it found.

**RADIUS.**
- On a server listening on `::`, answers to IPv4 clients go back to the
  address the request came from (`::ffff:a.b.c.d`); they were lost.
- A delayed refusal (*Wait before a refusal*) is waited out by one thread for
  all of them, not in a worker: a flood of wrong codes no longer ties the
  workers up sleeping. A delayed answer is not kept as the answer to a repeat.
- A client's allowed realms may have names with spaces, and follow a realm
  that is renamed or taken away.

**Tokens.**
- A wrong code for a token deleted at that moment no longer writes an empty
  token back under its name; switching off, notes, clock drift and *Forget
  them* refuse a name with no token instead of making one.
- Making a token again, or importing one over it, ends a lockout; an import
  also drops a waiting replacement.
- A confirmed replacement no longer shows the old key's last use.
- A new QR code keeps the token's note.
- A `.totp` file must hold a key of at least 80 bits; a file of rubbish was
  imported as a token. A counter (HOTP) file is refused.
- Export with *Steps of clock drift* 0 writes `WINDOW_SIZE 1`.
- `otp --restore` and a configuration read again seal restored tokens to their
  names; `otp --unlock` says so when there is no such token; `otp --check`
  shows each realm's way of signing in.

**The database and the directory.**
- TLS to MariaDB/MySQL checks the certificate when asked to; the dump and
  restore tools use the same TLS settings. A server address may be IPv6.
- A connection lost in the middle of a restore is not quietly reopened
  half-way through the transaction.
- A directory connection used again no longer fails at once on a deadline
  left over from the last question; every page of a search has its own.
- An unreachable directory is asked about a signed-in administrator again in
  a minute, not on every click.
- An error answered to somebody signed in no longer keeps their session alive.

**The administration pages.**
- *Move to* → *No* goes back to the token window.
- *Try* results are green or red; *Try sign-in* keeps its boxes after a
  failure, so a typo can be put right.
- *Print* prints the popup alone, black on white - not the page under it
  eight times.
- A bar of the overview chart shows that hour from the server: right count,
  and every page of it.
- The group finder of a realm empties after an error, so groups of another
  directory cannot be added.
- The mail test is held back only by unsaved mail settings.
- The buttons at the end of a row stay in sight in a narrow window; on a
  phone the pager no longer covers the rows and the tabs stay on one line.
- Every settings page has an icon of its own.
- Czech: some two hundred more answers, events and errors translated; plurals
  right; "Odebrat … away" and "realm je gone" gone.

**The enrolment pages.**
- A code that is not 6-8 digits is said so before it is sent; the reason a
  code was wrong is translated.
- nginx's own answers (too many attempts, server down) are said in words.
- The page's title, the disabled-token text and the hints are translated;
  the key breaks only between its groups on a phone.

**PHP, the installer, the documents.**
- The php2shell check asks php-fpm itself, not the command-line PHP, and reads
  the changelog whole (a `| grep -q` under pipefail could miss the CVE and
  move a fixed PHP to Remi). On Debian the pool goes to the php-fpm that is
  installed, not to the first folder by name.
- php-fpm is reloaded only when otp's pool or the guard changed - other sites
  on the machine are left alone.
- Installing again keeps the nginx file (`--rewrite-nginx` writes it afresh).
- `--dry-run --import-legacy` changes nothing; a copy that broke off is not
  imported. `--uninstall` also removes the polkit rule.
- `/healthz` says when the pages cannot read the API token; a download after
  signing out goes back to the sign-in.
- High availability: how the balancer must pass the client's address
  (`option forwardfor` or the PROXY protocol); with plain `mode tcp` every
  sign-in limit was shared by everybody.

## 1.0.35 — 23 October 2026

**The offer under a box low on the screen is seen.**
- A box near the bottom of the screen - *Move to* in a token's window -
  opens its list of people upwards, as it was meant to. It was pushed below
  the edge of the screen instead, leaving a sliver nobody could see, so the
  list seemed never to come.

## 1.0.34 — 23 October 2026

**Move to offers people as Make a token does.**
- Typing part of a name in a token's *Move to* offers the people of every
  realm's directory, with their full name, mail and whether they have a
  token - as *Make a token* does. It offered nobody: it asked for the realm
  by what comes after the @, and the directories are asked by the realm's
  name. The same slip hid the people in any box once a whole @domain was
  typed after a name.

## 1.0.33 — 23 October 2026

A security review of the whole program (the RADIUS server and the code
check; the pages, the API and PHP; the database, the directory, mail, high
availability and files), load tests, and what they found.

**Signing in to the administration from the directory.**
- With no group given a role, nobody from the directory gets in. Before,
  anybody in the directory could then read every log, token and account.
- A directory administrator is asked about again every ten minutes: switched
  off there, or out of every group with a role, and every sign-in of theirs
  ends; a role that changed changes. Changing the role groups or the
  directory signs everybody from the directory out.
- A password changed or set ends the other sign-ins of that account.
- An unknown name takes as long to refuse as a known one.

**RADIUS.**
- The order is now realm, directory (the account, in use, its groups), the
  password, and the code last. Somebody without the password can no longer
  guess codes or lock a token out; a code is used up only by a request that
  would be let in. In "password then code" realms one wrong attempt counts
  once (the probes that find where the password ends counted three times and
  paused the person after one typo), and one password costs the directory
  one try.
- A client can be limited to the realms it may use (Clients → Realms it may
  use). Without it the name typed chose the realm - and with it how strictly
  the person was checked: user@wifi at the VPN, password alone.
- A realm written with a dot at the end is the same realm; a name with
  nothing before its @ is refused.
- Lockout: after 10 wrong codes in a row, however slowly, a token takes no
  code for 15 minutes (Settings → The tokens). The short pause alone let a
  patient guesser try thousands of codes a day. *Forget them* ends it.
- A refusal goes back without its reason (Settings → RADIUS → Say why in a
  refusal): the VPN could show strangers whether a name has a token, or that
  the code was right and the password not.
- Message-Authenticator: a client that has sent one must go on sending one;
  one of the wrong length is wrong, not missing; answers carry it first.
- The answer goes out before anything is written down: a slow database
  delays the log, not the person, and no longer leaves a request let in
  without its answer. A refusal's delay waits on a timer, not in a worker.
- Junk from anywhere is counted, not written down a row each, and summed up
  once a minute; unknown addresses at most 30 rows a minute.
- The duplicate cache has a hard limit and no longer rebuilds itself.
- Only digits 0-9 are a code (Arabic-Indic digits left a request unanswered
  and unwritten); recovery codes work also when as long as phone codes.
- A realm's reply may carry only reply attributes.
- Two thread races (the client list, the unknown-address table) are gone.

**Tokens.**
- New recovery codes for somebody else follow the rule for showing a key: a
  full administrator, where showing keys is allowed, written down as a
  warning. A token administrator could get working codes for anybody.
- Confirming a new token is throttled like a sign-in, and done one at a time.
- A replacement with a longer period no longer refuses every code after it.
- Every token's sealed key, recovery codes and waiting replacement are tied
  to its name: copied into another person's row in the database, they no
  longer open. Existing tokens are sealed again at the first start (20 000
  in about 4 seconds), and after a restore.

**The pages and the API.**
- `?api=lo%67in` no longer slips past nginx's count of sign-ins; the count
  in the daemon is taken before the password is checked (thirty at once got
  thirty tries, now five) and also per name.
- Details such as a domain controller's name or a bind DN go only to
  somebody signed in; an error inside goes to the log, not to the page.
- A read-only account no longer sees the last characters of secrets.
- The enrolment pages switched off sign out whoever is on them; a wrong
  password or code when replacing a token no longer signs the page out.
- The link in a token's mail is built from the address the pages were
  reached by, not taken from the page.
- An open page signs out after the idle time even while it refreshes itself.
- Events for throwing away a waiting replacement, a note changed, a sign-in
  ended (whose), and the enrolment page's cancel.
- The first password file of the installer is deleted once that password is
  changed.
- Search-as-you-type for numbers (recovery codes) no longer breaks on
  PostgreSQL.

**The database, mail, the directory.**
- Database name, account and host are checked: a name like
  `--result-file=…` was an option to mariadb-dump; control characters in a
  password could add lines to its option file.
- Database TLS: Settings → The database → Encryption (require, verify-ca,
  verify-full and the authority's file), also for the link to the other node.
- A restore is all or nothing: one that broke off half-way left the tokens
  empty.
- A connection lost is retried only for reads, or where nothing was sent: a
  write retried could have used a code twice, then refused it as used.
- Plain searches treat % and _ as themselves; very deep NOT/brackets refused.
- The key that seals the secrets is read once and kept, made with O_EXCL,
  and never made anew where the database already holds secrets sealed with
  a missing one.
- The directory: one deadline for a whole answer, and an answer that does
  not read is a directory error, not a crash.
- Mail straight to the recipients: answers to its DNS questions only from
  the server asked and for the question asked, within one deadline; an
  answer that does not read fails cleanly. TLS to the recipients' servers can
  be required (Settings → Mail).

**Speed.**
- New indexes: the events by kind, the log by packet and by client, the
  sign-ins by kind (the enrolment tab 38 → 0.7 ms, the kinds offered 98 →
  0.2 ms). The overview's chart is counted by the database (1.3 s for a
  month before). Old rows are deleted 5 000 at a time. A client's last-seen
  time is written once a minute, not on every packet; the last address of a
  token in one statement. The API takes 256 connections waiting at once (20
  pages asking at the same moment lost one).
- Measured on one machine (SQLite, 20 000 tokens, 50 clients, 30 realms):
  RADIUS about 630 sign-ins a second with 50 clients at once, p99 104 ms, no
  answer lost; with 30 % wrong codes 580/s; 1 000 enrolments at 40 at once
  beside 10 000 sign-ins, no error, sign-ins p99 230 ms.

**Import.** A ZIP of .totp files can be dropped on *Bringing tokens over* -
a totpcgi folder zipped, or another otp's export (read in memory, with
limits on size and number; names inside are never used as paths).

**The pages.** *Your account* is wider.

**Known and left as it is, for now.**
- Replicated high availability (two databases) cannot make a code strictly
  one-time across both nodes while they are apart; shared mode (one
  database) can. Wrong codes are also counted per node there.
- A group named by its name alone (VPN_USERS) matches any group of that name
  anywhere under the base: pick groups from the directory (whole DN).
- Two realms both naming tokens without the realm share the tokens of
  people of the same name.
- MySQL 8 is not tested (MariaDB is); an account locked in Active Directory
  is refused by its password in password realms, not in code-only realms.

## 1.0.32 — 23 October 2026

**A token replaced on the enrolment pages could not be confirmed when the
settings had changed since it was made.**
- Every token keeps its own digits, period and hash: imported totpcgi tokens
  (SHA-1, 6 digits, 30 s) go on working beside tokens made later with other
  settings - that was always so. But a replacement waiting beside an old
  token was made with today's settings and checked with the old token's:
  an imported SHA-1 six-digit token replaced while the settings said
  SHA-512 and eight digits could never be confirmed. The waiting key now
  keeps its own shape, is confirmed with it, and the token takes it on once
  confirmed. *Show* on the waiting key shows it in its own shape too.
- Checked end to end: an imported SHA-1/6 token signs in, a new token is
  SHA-512/8, the old one replaced is confirmed with an 8-digit SHA-512 code
  and is SHA-512/8 from then on.

**What the hash and the length do, said where they are set.**
- *The hash*, *Digits in a code* and *A code lasts* now say that they are for
  tokens made from now on, and that Microsoft Authenticator and Google
  Authenticator on Android ignore SHA-256/SHA-512 (and Microsoft
  Authenticator eight digits) - their codes would be refused.

## 1.0.31 — 23 October 2026

**The step numbers in a token's mail are pictures.**
- Outlook's own circles (1.0.30) put the digit at the bottom edge, cut in
  half. Each number is now a small picture of the circle with its digit -
  drawn sharp for high-resolution screens, sent inside the mail like the QR
  code (about 2 KB each) - so it looks the same in Outlook, on the web and
  on a phone. With pictures blocked, the number itself is shown instead.

## 1.0.30 — 23 October 2026

**Round step numbers in Outlook as well.**
- Outlook on Windows draws mail with Word, which knows no rounded corners,
  so the numbered steps were squares there. In Outlook they are now drawn
  as VML circles - Outlook's own shapes - and every other mail program gets
  the same circles as before from CSS.
- The blue band at the top is one solid colour in Outlook too: its lighter
  stripes above and below the title are gone.

## 1.0.29 — 23 October 2026

**A token's mail that looks right in Outlook too.**
- Laid out in tables with sizes as attributes, which is all Outlook (it draws
  mail with Word) understands: the numbered steps are round badges beside
  their words instead of a sliver of blue, the QR code sits in a frame, the
  key is one line in a grey box, and the recovery codes are each in a box
  of their own, five to a row - they ran together into one long number.
- The account and the name under the QR code are plain text, not links
  that Outlook made of every name@domain, and are never broken in two.
- The plain-text copy of the mail is unchanged.

## 1.0.28 — 23 October 2026

**The steps of a sending folded away.**
- After making a token with its mail, and after *Send by mail* in a token's
  window, only the line saying how it went is shown - *Sent by mail to …*
  or why not. A click on it (or Enter) unfolds the steps: the MX records,
  the addresses, the server reached, TLS, what the server answered.
  *Settings → Mail → Try it*, which is there for the steps, still shows them.

## 1.0.27 — 23 October 2026

**A token's mail sent again.**
- *The person → By mail → Send by mail* in a token's window: the same
  choices as when it is made - the address, the recovery codes (the ones
  not used yet), Czech or English - and the steps of the sending.
- The address is remembered: wherever the token's mail went last time
  (when it was made, or sent again) is filled in, also when it was not the
  one in the directory; the row says where and when. It goes with the token
  when the token moves to another realm; given to somebody else, it does not.
- The key leaves the machine as when it is shown, so the same rule: a full
  administrator, with showing keys allowed. Every sending is a warning event.

**Where a mail went once it left.**
- *Handed the message over* now says what the receiving server answered -
  `250 2.0.0 Ok: queued as 4Xy…` - after making a token as well as when it
  failed, and the event keeps it: that id is what the receiving side's log
  (an IronPort's message tracking, say) is searched by when a mail never
  turns up although it left.
- *Settings → Mail → Try it* can send *a sample token mail* - the real
  layout, picture and codes, with a made-up key that opens nothing - next to
  the short message: a filter that lets a line of text through can still
  stop a mail with a QR code in it.

## 1.0.26 — 23 October 2026

**An upgrade leaves a good PHP alone.**
- `install.sh` (and `--upgrade`) no longer installs PHP again, switches its
  stream or restarts php-fpm when the PHP there already has the php2shell
  fix: it says so and goes on. Nothing pins a version - newer builds and
  streams come with the system's own `dnf upgrade` / `apt upgrade`.
- A PHP that is there but not fixed only has its own packages upgraded, on
  the stream it is on. Before, the stream was reset to `php:8.3` - which
  would have taken a machine already on `php:8.4` back down.
- A machine with no PHP gets `php:8.3` (`--php-stream`) only when no stream
  is enabled yet.

## 1.0.25 — 23 October 2026

**A popup closes only when told to.**
- A click beside a popup - on the darkened page, or on the window under a
  popup over it - no longer closes it; a stray click used to throw away a
  half-filled form. It closes with its own buttons (Save, Close, No, Back…),
  its ×, or Escape.

## 1.0.24 — 23 October 2026

**The window underneath stays still.**
- With a popup open over a token's window, the window underneath no longer
  jumps: its foot (the history, the Log, *Take the token away*, *Close*)
  lost its layout while it was underneath, wrapped onto two lines and gave
  the cards a scroll bar. Its look no longer depends on being on top.

## 1.0.23 — 23 October 2026

**Mail straight to the recipients: their servers' addresses too.**
- With *DNS servers for the recipients' domains* (`mail_dns`) set, the
  address of each recipient's mail server (A and AAAA, a CNAME followed) is
  asked of those servers as well, not only its MX record - before, only the
  MX went there and the address still came from the system's resolver.
  The connection goes to that address; the certificate is still checked
  against the server's name.
- With `mail_dns` empty, the address comes from the system's resolver
  (/etc/hosts, nsswitch) as before; only the MX question - which the system
  has no call for - is otp's own, sent to the servers in /etc/resolv.conf.
- Nothing else uses `mail_dns`: Active Directory, the SMTP relay, isemon,
  the database and the other node are looked up by the system as always.
- The step says what the address is and who gave it.

## 1.0.22 — 23 October 2026

**Mail straight to the recipients finds their mail servers.**
- The MX lookup asks with EDNS0, takes a cut-short answer again over TCP,
  follows a CNAME and knows a null MX. A DNS server that refuses or fails
  (SERVFAIL) is no longer taken for "this domain has no MX" - which sent
  the mail to the domain's own address (merit.cz:25) and timed out. It goes
  on to the next DNS server, and if none can answer it says which and why.
- The step says which DNS server gave the MX records.
- New setting *DNS servers for the recipients' domains* (`mail_dns`) for a
  machine whose own resolver will not answer; empty means /etc/resolv.conf.
  dnspython is used when it is installed.

**A window over a window.**
- In a token's window, *Show* (QR code and key, recovery codes), *In the
  directory*, the history, *New QR code*, new recovery codes, *Export .totp*
  and *Take the token away* open over it; closing them goes back to the
  token, drawn afresh where something changed. Esc closes only the top one.

**Passwords as isemon shows them.**
- Every password and secret box in the administration - the settings, the
  directory's account, a client's secret, accounts, the database, the Test
  tab, high availability - shows dots and its last two characters, both a
  kept one and one being typed. The sign-in pages keep the browser's own
  password box, so password managers still fill them.

**A person picked stays picked.**
- Once somebody is picked from the offer (or a box comes filled in), the
  offer does not pop up again when the box is clicked or focused - only
  once something is typed or deleted.

## 1.0.21 — 23 October 2026

**A token's window on one screen.**
- Four cards of exactly the same size, two by two: the phone, signing in,
  the recovery codes, the person. Their rows are lower, *Move to* and the
  note sit on one line each.
- When it was made, by whom, last used and from where sit beside the name
  instead of under it.
- The history, *Everything in the Log* and *Take the token away* are in the
  window's foot beside *Close* - no card of their own, and no scrolling on
  an ordinary screen.

## 1.0.20 — 23 October 2026

**Mail: a token's QR code sent to the person it is for.**
- *Settings → Mail*: through your mail server (STARTTLS 587, SMTPS 465, or
  none for a relay inside your network) with no sign-in, the best the server
  offers, PLAIN, LOGIN, CRAM-MD5 or XOAUTH2 (Microsoft 365, Google) - or
  straight to each recipient's domain by its MX record, with no server at
  all. The password is kept sealed with the tokens' key.
- The server's certificate is checked; a private authority is imported the
  same way as for Active Directory (paste or a .crt/.pem/.cer file, one or a
  chain, each listed with its whole fingerprint and removable on its own).
- *Try it* sends a short mail by the same road and shows every step:
  connection, TLS, sign-in, hand-over.

**Make a token: find the person, send it by mail.**
- *For* offers the people of the realms' directories as one types; picked,
  their mail address is read from the directory into *To* (it can be
  changed).
- *Send it by mail*: the QR code, the key, how to set the phone up, and -
  if ticked - the recovery codes, in Czech or English, as a tidy HTML mail
  with a plain-text copy. Every mail sent is in the events.
- The owner's full name is read from the directory as soon as the token is
  made - no need to press *Names from the directory* afterwards.

**Tokens out as .totp files.**
- *Settings → Export and import*: every token, or the ones a search picks
  (`realm:example.cz`, `name:novak*`, a state), as totpcgi .totp files in
  one ZIP - for totpcgi or another otp. A single token from its window:
  *For another server → Export .totp*. Full administrators only, with
  showing keys allowed, and each export is in the events as a warning.

**The pages made over.**
- One height for every box and button, one grid for the tiles, the token's
  window rebuilt as cards of actions, the settings laid on one grid so every
  name, box and explanation on a row starts at the same height.
- The list of suggestions floats above windows instead of being cut off
  inside them with its own scroll bars.
- Czech for everything new and for the titles still left in English.

## 1.0.19 — 23 October 2026

**Every search box offers its fields and values as one types (as isemon).**
- Tokens, the Log, Enrolment and Events read `field:value` besides plain
  words: `result:reject client:ASA`, `name:novak*`, `-state:active`,
  `realm:dpmo.cz,corpnet.cz`, `ms:>500`, `reason~ldap`, `from:10.1.0.0/16`,
  `(client:ASA OR client:localhost)`, `NOT …`. A name the list does not have
  is a word, so `10.1.2.3:1812` is searched as before.
- Under the box, as one types: the list's fields with what each means and an
  example; after `field:` what that field holds, busiest first, narrowed by
  what is typed. ↑ ↓ choose, Tab or Enter take, Esc closes. A search that
  cannot be read says why under the box. `GET /api/suggest` behind it.

**People and realms offered as one types.**
- *Make a token*, the token's *Move to*, *Look a name up* and the Test tab:
  type part of a name and the people of the realm's directory are offered,
  with their full name, mail, whether they are switched off and whether
  they have a token already; after an @ the realms are offered.

**A token can be given to another person, not only moved to another realm.**
- *Move to* takes any name; given to somebody else, the owner's name is read
  again from the directory. Key, recovery codes and history go with it.

**The person card, as isemon's.**
- The directory card (Accounts, a token's *In the directory*) and *Your
  account*: initials, name, principal name, tags (active / switched off /
  locked out / expires, role, realm, token), where the account lives as
  steps (domain › OU › person) with the DN, and the groups - the ones that
  make an administrator or let into a realm first, as cards saying so, the
  rest as chips (and N more).

**Fixes**
- The administration sign-in page said "the database will not open" to
  anyone not on the server itself, though it opened and signing in worked.
- Tiles never break a value in the middle of a word; a value too long ends
  in an ellipsis with the whole under the pointer.

## 1.0.18 — 22 October 2026

- Settings → Accounts: every row has the same buttons in the same places -
  the role first, then the directory lookup, the password, switching off,
  removing, the columns. A button that does not apply to an account (the
  directory for a local one, the password for a directory one) is there,
  dimmed, and says why; the invisible gaps that stood in for them made the
  rows look broken.

## 1.0.17 — 22 October 2026

**Long lists keep their search and their pager in place (as isemon).**

- Tokens, the Log, Enrolment and Events: the card is a column of heading,
  note, filters, the rows and the pager; only the rows scroll, the table's
  heading stays stuck to the top of them, and the search box and the pager
  never leave the window. A note longer than two lines is cut, and opens
  with a press on it. The daemon's own log under the events stays reachable.
  On a window too short or too narrow to frame, the page scrolls as one.

## 1.0.16 — 22 October 2026

**A tab for the enrolment pages: who came and what they did.**

- *Enrolment*, between Test and Events: every step a person took on the
  enrolment pages, newest first - signed in, made a token, confirmed it with
  a code, replaced an old one, could not sign in (and why), may not enrol
  (not in the groups). Six tiles count them for the chosen window (24 hours,
  a week, a month, all time); the list is searched by name or address and
  narrowed by step. A click on a row opens the person's token.
- `GET /api/enrolment` behind it (`q`, `step`, `since`, `limit`, `offset`).

## 1.0.15 — 22 October 2026

**A review of the whole program: security, bugs, the pages.**

Security - the daemon:
- A token an administrator switched off could be switched back on by its
  owner on the enrolment pages: confirming a code did not look at the state.
  Only a token that waits (new, or with a replacement staged) is confirmed
  now, and confirming never moves `last_step` back, so a code already used
  stays used.
- A test of a code in the Test tab ("dry") counted nothing and logged
  nothing: a token administrator could try codes without limit. Dry checks
  are logged (`test-dry`) and wrong ones count towards the pause.
- Recovery codes were kept as a plain SHA-256 of the code: a copy of the
  database without its key could be brute-forced offline in a minute. They
  are now keyed with the sealing key (HMAC); old rows are read and rewritten
  on their next use.
- The admin sign-in no longer says whether the name exists in the
  directory, or that the account there is locked or expired (that stays in
  the events).
- An account marked "must change the password" could call every endpoint;
  it may now only change the password, ask who it is, or sign out.
- A Reply-Message with non-ASCII characters longer than 253 bytes made the
  RADIUS server throw instead of answering and the request was never logged.
- `--trusted-proxy` wrote the real_ip block into the port-80 server, not the
  HTTPS one: behind a load balancer the sign-in pause was keyed on the
  balancer's address.
- HA: database passwords no longer pass on psql's command line nor reach
  PostgreSQL's log; an error text with a connection string is scrubbed
  before it is stored. The peer has to be one address (not a range); IPv6
  peers get /128. The `pg_hba.conf` line is prepended, so no earlier reject
  line wins.
- The per-name lock table and the "unknown client" table could grow without
  bound under a flood of made-up names and addresses.
- `--radtest` no longer prints the password.

Security - the pages:
- A restore upload (up to 4 GB) was read into a temp file before anyone was
  identified; now a full administrator's sign-in is checked first.
- The sign-in rate limit in nginx could be bypassed with a doubled or
  percent-encoded `api` parameter.
- `/healthz` is rate-limited; the pre-sign-in page tells its operator
  details (php-fpm user, token path, "no account yet") only from localhost;
  PHP errors are never displayed into a response.

The pages:
- Fields side by side in a popup started on different lines (the labels
  of a row were staggered); the tuning popup's memory field as well.
- Switching tabs with unsaved settings threw them away.
- The name of a switch setting did not flip it when clicked.
- Names with an apostrophe or an ampersand showed `&#39;` / `&amp;` in
  popup titles.
- Settings search: results are styled and say when nothing is found.
- Export and the Test tab are hidden from roles that may not use them.
- "Add it" under the certificate authority came back on a timer, so a slow
  import could be sent twice.
- The job progress is asked every five seconds when its pane is left (was
  every second, for ever).
- Escape over the column menu closed the popup under it too.
- Column layouts from a file are checked (no absurd widths, no junk).
- Shared secrets, bind passwords, first passwords and the HA passphrase
  are typed unseen; every popup label is linked to its box.
- Edit/person/lock buttons no longer turn red on hover; only the destructive
  ones do. Empty tables say "Nothing here". Several Czech texts that were
  still in English (the DB tooltips, HA buttons, token verdicts in the log,
  disk words in the tuning popup, the isemon rule note); `<this>` in the
  isemon hint was shown as `&lt;this&gt;`.
- The realm list no longer wraps its name, suffix and directory; the
  replication table's numbers have room; the import pane's checkbox is dark.
- The sign-in page of the administration shows the version and the language
  switch, as the enrolment pages do.
- The HA pane describes building and looking after the cluster with the
  exact commands, step by step, and has a table of every `--ha-*` command
  and when to use it. The intro follows the mode (replicated or shared).
- Sign-ins that sat untouched longer than allowed were still listed under
  "Signed in now"; they are tidied.
- About a third of the stylesheet was rules carried over from isemon for
  things these pages never draw; they are gone, as is a block that was in
  the file twice.

## 1.0.14 — 22 October 2026

**High availability, replicated: each node its own PostgreSQL, both answering**
- see docs/high-availability.md.

- `otp --ha-setup --ha-peer ADDRESS` now builds the replicated layout by
  default: logical replication both ways (publication `otp_pub`, subscriptions
  with `origin = none`, so nothing goes round in circles), odd ids on the first
  node and even on the second, `max_slot_wal_keep_size = 16GB`. The shared
  layout of 1.0.13 is `--ha-setup --ha-shared`.
- `otp --ha-join FILE` on the second node installs PostgreSQL if it is missing,
  copies every row from the first node and sets both directions up. The same
  command rejoins a reinstalled node.
- A node that was down catches up by itself. A node that was away longer than
  what is kept for it is rebuilt from the live one: `otp --ha-resync`, or
  *Rebuild this node from the other…* (a safety copy is made first).
- Watching and stepping in, on the pages (*Settings → High availability →
  Replication*) and on the command line: status of each direction (running,
  last heard from, waiting to go over, errors), `--ha-pause [both|in|out]`,
  `--ha-resume`, `--ha-stop`, `--ha-resync`, *Read the tables again*.
- Per-node things stay per node: the tuning record, the disk sizes, a job's
  progress, the nightly dump. The settings serial is a time and node mark, so
  both nodes' changes are seen.
- A new PostgreSQL database is created as UTF8 and every connection speaks
  UTF8 (an SQL_ASCII database failed on names with diacritics).

**Names from the directory after an import**
- Tokens brought in from another system get their owner's name from the
  directory, the same way as tokens enrolled here: right after the import, then
  every hour for any still without a name (100 at a time; a directory that does
  not answer is skipped for that round).
- A *Names from the directory* button on the Tokens tab does it at once for every
  token without a name; `otp --fill-names` on the command line.

**Settings → Active Directory → The certificate authority**
- The SHA-256 fingerprint is shown whole (two lines of 16 bytes) instead of
  cut short; a click selects it.

## 1.0.13 — 22 October 2026

**High availability: two servers, both answering (active/active), over one
PostgreSQL** - see docs/high-availability.md.

- Anything may go to either node, round robin and without stickiness: the
  "Edit the columns" switch is now kept with the sign-in in the database (it
  was in one daemon's memory), a job's progress is in the database too, and
  every setting changed on one node is read by the other within five seconds.
- A code - or a recovery code - is used up with one conditional UPDATE: two
  nodes asked for the same code at the same moment cannot both accept it.
- The nightly dump is claimed by one node.
- Each node writes a heartbeat; *Settings → High availability* lists the nodes
  (address, version, RADIUS, when last heard from), and the header says which
  node answered the page when there are two.
- The wizard: `otp --ha-setup --ha-peer ADDRESS` on the first node (opens a
  local PostgreSQL to the second node - listen_addresses, pg_hba.conf,
  firewalld - and writes the bundle), `otp --ha-join FILE` on the second; or
  *Make the bundle…* and *Join a cluster…* on the pages. The bundle carries
  the database's address and password and the key that opens the tokens,
  locked with a passphrase (scrypt + HMAC-SHA256) shown once.
  `otp --ha-status` lists the nodes.
- `GET /healthz` for the load balancer: 200 "ok NODE" while the node and its
  database answer, 503 when not.
- `otp --trusted-proxy CIDR`: nginx takes the client's address from
  X-Forwarded-For when it comes from the load balancer.
- `node_name` in config.json: this node's name (Settings → High availability).
- `install.sh --upgrade` now brings an existing nginx configuration up to the
  version (the 4 GB body for putting a database back, which 1.0.10 needed, and
  /healthz), keeping its allow lists and a copy of what it was.
- A token window's history, cleaner popups: a grid of two fields no longer has
  the second one pushed down.

## 1.0.12 — 22 October 2026

- **Several certificate authorities per directory.** A directory whose
  domain controllers come from several domains or authorities keeps a chain
  for each: *Add it* adds what is pasted or read from a file (a whole chain at
  once, and a certificate already kept is not added twice) instead of
  replacing it; every certificate is listed - who it is, who signed it, valid
  from and until (coloured as it nears its end), its SHA-256 fingerprint - and
  each has its own bin. *Take them all away* empties it.
- **A token's window is wide and needs no scrolling**: four cards side by
  side - the phone (with *Try a code* under it), the recovery codes, signing
  in (with *Take it away* under it) and the person (directory, realm, note) -
  and the history behind its button below them.

## 1.0.11 — 22 October 2026

**The whole interface gone over.**

- A token's window: the buttons of each card are one under another, all the
  same size; *Try a code* and *Note* take the whole width; the history (the
  checks of a code and the requests) is no longer drawn under everything but
  behind **The history** - a popup of its own with the way back - and
  **Everything in the Log** opens the Log searched for that name.
- **A token can be moved to another realm** (*The person → Realm → Move it*):
  its name changes to name@realm (or the bare name), with the same key, the
  same history and its recovery codes made again under the new name.
- Settings whose choices are long (*Who may enrol a token*, *Token names are
  kept*) are two columns wide, so the choice is not cut off.
- Fields in popups have room between them; the group searches are wide enough
  for their hint; the certificate authority's *Load a file…* has the upload
  icon and *Import* the save one; the phone on the enrolment page shows its
  code inside the screen.
- Realms: "default - also without @" and how a name is looked up are in the
  page's language; "/var/log/remote/<host>/" reads "HOST"; About says the
  engine by its name.
- Czech: the database pane, the reasons of the token engine (*Not a valid
  token*, *Scratch-token used*…), "From"/"Since" as *Odkud*/*Od kdy*, the new
  events.
- The database's restart: the tuning popup has **Restart the server…** itself
  when something waits for PostgreSQL's next start, and where it may not, says
  why (another machine, no single postgresql service, or install.sh's rule
  missing).
- The installer installs the database client only for the engine in the
  config file: `--with-db both` no longer puts the MariaDB client on a machine
  that runs on PostgreSQL.
- Events of copies and dumps read better ("made a PostgreSQL dump (every
  night): …").

## 1.0.10 — 22 October 2026

**Settings → The database, rebuilt to be isemon's.**

- **The dumps it keeps** (new): every night the database in use is dumped by
  its engine's own program - `pg_dump` (custom format, `.pgc`),
  `mariadb-dump` (`.sql.gz`), SQLite's own backup (`.db`) - into
  `/var/lib/otp/dumps`, with the key that opens the tokens beside each one.
  Where the program is missing, a portable copy is made instead and the card
  says what to install. *Make one now*, *Download one*, and per dump
  *Download*, *Restore* and *Delete*; *Put a dump back* takes one from
  elsewhere. A dump goes back only into the engine it came off.
- **Copies**: the same list for the portable copies (any engine), with
  *Download*, *Restore* and *Delete*, plus *Download it* (a copy made now,
  with the key inside it) and *Put a copy back* (drop a file). Everything put
  back is read and shown first - what it is, how many tokens, accounts and
  full administrators - and refused if it is not otp's, is a dump of another
  engine or has no full administrator. A copy of what is replaced is always
  made first. The file goes up as the request body itself (never multipart,
  php2shell), a lump at a time, up to 4 GB.
- **Which one it is**: the facts as isemon shows them, whether each driver is
  installed; *Try it*, *Set it up…*, *Carry everything across…*, *Empty it…*,
  *Start using it…* each in its own popup with what will happen.
- **The disk it is on** (new): free space, how fast the database grows (noted
  daily, the slope of the last fortnight), days left, the files it is made of
  (`otp.db`, `-wal`, `-shm`, the copies, the dumps); a warning when the
  server's own cache is smaller than the database.
- **The database server's own settings**: the popup shows the server, the
  machine (memory, free memory, processors), how the disk was judged - a
  virtual machine's disk always says it spins, so the time a small write takes
  decides, as on isemon - and per setting *Now / For this machine / Takes /
  Why*. Memory settings within a tenth are the same, so it no longer asks to
  change shared_buffers back and forth. What was tuned and when, and what is
  waiting for the server's next start, is said on the card.
- **Restart the server…**: PostgreSQL on this machine restarted from the page
  for the settings waiting for its start, refused when the memory free would
  not hold the new shared_buffers or huge pages are on, then waited for. The
  installer puts in a polkit rule that lets the `otp` account restart
  `postgresql*.service` and nothing else (`--no-db-restart` takes it away).
- **Erase the collected data** (new): the RADIUS requests, the checks of a
  code and the event log, each with its count, ticked and erased as a job
  with a copy made first and the disk given back afterwards. Tokens, accounts
  and settings are not in the list at all.
- The installer installs the database clients (`postgresql`, `mariadb`) with
  `--with-db`, for the dumps.

## 1.0.9 — 22 October 2026

**The columns of every table, laid out by whoever is looking - exactly as on isemon.**

- Every table in the administration (tokens, the log, events, realms,
  clients, accounts, sign-ins, groups, the database…) can be laid out per
  account: drag the edge of a heading to size a column (its width is shown
  in a pill at the foot of the window, twice on the edge puts that table's
  widths back), drag the heading itself to move the column, and the right
  button on a heading or a row opens the menu: hide this column, bring a
  hidden one back (a tick by each column), add an empty column to the left
  or right for room, take an empty one away, put this table back as it comes.
- Only while **Edit the columns** is switched on - under your name at the
  top right, or on Settings → Accounts. The switch is held by the daemon for
  that one sign-in: signing out, the sign-in running out or a restart of the
  service turn it off. Off, the layout is drawn just the same and nothing can
  move it; a change sent with it off is refused (409) and the page says so.
- The layout is kept with the account in the database (`accounts.cols`),
  not in the browser, so it follows you to any machine; widths are kept as
  shares of the table so it always fits its card. Laid out before the
  browser paints, so a table is never seen in its old order first.
- **Put my columns back as they come** (under your name and on Accounts).
  A full admin can put anybody's back: the new *Columns* column on Accounts
  says how many tables each person has laid out, and the button beside it
  resets them (logged as an event).
- **Your settings in a file**: *Export my settings* saves your column layout
  and language as `otp-settings-<you>-<date>.json` (kind
  `otp-user-settings`); *Import settings…* shows whose file it is, where and
  when it was saved and what it holds before replacing yours. isemon's own
  settings file is read too. Never a password, a role or anything else about
  the account.
- New API: `POST /api/auth/columns` (`{edit}`, `{cols}`, `{reset}`),
  `GET|POST /api/auth/settings`; `/api/users` action `reset_cols`;
  `whoami` carries `cols` and `cols_edit`.

**Who may enrol a token: the groups found and picked.**

- Settings → The enrolment pages → *Groups that may enrol* has a
  **Find and pick the groups** button: the same directory group search as
  for realms and administrators, with *May enrol* beside each group to put
  it in or take it out, the chosen ones shown as chips. It looks in the
  directory of the enrolment pages' realm (or the default realm) first.

## 1.0.8 — 22 October 2026

**Security: the groups of a realm are now always checked.**

- A realm whose *By* was "not looked up anywhere" skipped the directory
  entirely - its groups, a switched-off account - and let anybody with a right
  code in. A realm with a directory now always asks it: the way is chosen by
  the form of the name (with an @ by userPrincipalName, without it by
  sAMAccountName) when none is set. A realm that names groups and has no
  directory refuses everybody, saying so.
- **Enrolment** checks the realm's groups always: nobody enrols a token the VPN
  would refuse. *Who may enrol* can only narrow that further.
- Every refusal says why, with names: `account does not pass LDAP group
  filter(s): novak@example.cz is in none of VPN_USERS, VPN_ADMINS`, and on the
  enrolment pages the same goes into the log and the events.
- Groups inside groups (nested) count everywhere a group is asked about - the
  realms, enrolment, the administrators' roles - with Active Directory's
  in-chain rule; a realm can switch it off.
- A request that could not be decided because of an error inside gets a
  refusal with the reason, never silence.

**The default realm** (Settings → Realms): names written without a realm
belong to it - `novak` is `novak@example.cz` - on the enrolment pages and in
RADIUS requests from a client that adds no realm of its own; `novak@example.cz`
works as well, and every other realm still needs its @domain. The realm list
marks it.

**One log**: *Requests* and *Codes* are one tab, *Log* - every RADIUS request
with what the token said about its code, and every code checked anywhere else
(the enrolment pages, a test, the command line), filtered by kind, time,
result and client. A log is not edited from the pages any more: old lines go
by themselves after the days set under Settings → The database, which is also
where they can be cleared (*Forget records older than…*, or every line).

**Tokens**

- The token window is large and in sections: *The phone* (show the QR code and
  key, a new QR code with a new key, the waiting one), *Recovery codes* (show
  them - which are free and which were used, and when - or make new ones),
  *Signing in* (switch off, forget the wrong codes, clock drift), *Try a code*,
  *The person* (what the directory says, the note), *Take it away*.
- Recovery codes are kept sealed beside their hashes, so a full administrator
  can show them again; a used one stays, struck through, with when it was
  used. Tokens made before 1.0.8 have only the hashes: make new ones to have
  them shown. Every look is an event; *Administrators may show a token's QR
  code and key* switches it off.

**The pages**

- A pencil for every Edit, everywhere.
- *In the directory* beside every token and every account signed in from the
  directory: who it is, whether it is switched off or has run out, the DN, its
  groups (nested ones too).
- Active Directory: each directory a card - its servers as chips, how it is
  reached, its certificate, the base, the reading account - and its editor in
  two sections. The certificate authority as tiles, *Good until* coloured as
  it nears its end, the paste box behind *Import another…* once one is there.
- The realm editor in sections: what it takes, looking the person up, the
  groups that let in, the answer.
- The overview's lists keep their words whole - the name or the reason on its
  own line, the bar, the count and when under it - and the chart counts in
  whole numbers.
- The save bar shows only on a page with settings to save.

Upgrading: unpack 1.0.8 and run `./install.sh --upgrade`. Check *By* of every
realm afterwards: what was "not looked up anywhere" now looks the name up.

## 1.0.7 — 22 October 2026

- **Aligned.** A row with buttons at its end is centred top to bottom, so the
  name, its tags and its buttons stand on one line. In Accounts every row's
  buttons stand in the same columns - an account signed in from the directory,
  which has no password here to set, keeps an empty place where the lock is -
  and the role choice has one width in every row. A setting as wide as the
  page (the groups of the roles, the help text) has its (i) at its right edge
  like every other.

Upgrading: unpack 1.0.7 and run `./install.sh --upgrade`.

## 1.0.6 — 22 October 2026

- **No browser dialogs anywhere.** *Look a name up* (Active Directory) and
  *Set a new password* (Accounts) asked through the browser's own prompt box;
  both are now the pages' own popup, like everything else - the password asked
  twice and checked for length before it is sent. Nothing on the pages uses
  prompt, alert or confirm any more.

Upgrading: unpack 1.0.6 and run `./install.sh --upgrade`.

## 1.0.5 — 22 October 2026

The administration pages, gone through as a whole.

- **The tables no longer draw their buttons over the columns before them.**
  The cell holding a row's buttons was made a flex box, which takes it out of
  the table: in Active Directory the Base and the account were covered, in
  Accounts the role. Long names (servers, DNs) wrap in their own column.
- **Every row has its Edit and its Delete**: tokens (open it, take it away),
  clients, realms, directories (a gear to change it, a bin to take it away),
  the checks of a code and the RADIUS requests (see below).
- **Codes**: a line opens what it was (when, right or not, what was said, how,
  from where, which request) with *Its token*, *Its requests* and *Forget this
  line*; a bin on every line; *Forget these…* takes out every line the filters
  match. The same on **Requests**. Full administrators only, and every
  forgetting is written down as an event; what went to isemon stays there.
- **A name without a token** opens with *Make a token* and its history,
  instead of a window saying only that there is none.
- **A token's QR code and key can be shown again** by a full administrator
  (*Show the QR code and key*, and *Show the waiting one* for a replacement
  not yet confirmed) - after a warning, and every look written down. The
  setting *Administrators may show a token's QR code and key* (Settings → The
  tokens) switches it off.
- **A wrong code when confirming a new token says why**: the phone's clock is
  off by so many seconds, or the code is not from this token at all - usually
  an older entry of the same name in the application.
- **Signing administrators in against Active Directory, as isemon does it**
  (Settings → Accounts): *The groups, and what each one may do* - *Find the
  groups* (all, or those whose name holds what is typed), the list searchable
  and paged, and *Full admin* / *Token admin* / *Read only* beside every
  group, lit where it holds the role; *Try a sign-in…* asks the directory as a
  real sign-in would and shows the role and the groups, signing nobody in.
  Names may be typed as `novak`, `novak@example.cz` or `EXAMPLE\novak`. With
  no group given a role at all, anybody in the directory may read (isemon's
  rule); naming one closes that.
- **The same group list in the realm editor**: *Find the groups*, search, and
  *Lets in* beside every group, in place of a prompt that added every match.
- **The certificate authority of a directory, as isemon's**: its own card
  under Active Directory - what is imported (who it is, who signed it, from
  and until when), paste it or *Read a file…* (.pem, .crt, and a .cer in DER
  as Windows exports it), *Import it*, *Take it away*. It is checked for being
  a certificate before it is stored.
- **The database page, as isemon's**:
  - *Which one it is*: *Try it* (the address in the editor, unsaved), *Set it
    up…* (makes the database and the account on MariaDB or PostgreSQL with an
    administrator of that server used once and kept nowhere; a password made
    and shown once), *Carry everything across…* (a copy first, then every
    row, with a progress bar), *Empty it…* (only ever the other one), *Start
    using it…* (writes the address and starts the daemon again on it).
  - *What is in it*: rows and size of every table, the room free inside,
    *Make a copy now*, *Check it* (integrity check / CHECK TABLE / every table
    read), *Optimise it* (fresh statistics), *Apply what is kept, now*,
    *Forget records older than…*, *Give the disk back* (VACUUM / OPTIMIZE
    TABLE / VACUUM FULL).
  - *The database server's own settings* (MariaDB, PostgreSQL): what the
    machine has, the settings worked out for it beside what is there now, put
    in with ALTER SYSTEM or SET GLOBAL (the ones that need a restart said so,
    and for MariaDB the lines for `/etc/my.cnf.d/`), and *Put back as it was*.
- Copying into another database is batched: a transaction per thousand rows
  rather than one per row.
- A link to `#settings/dir` (or Back in the browser) opens that page.

Upgrading: unpack 1.0.5 and run `./install.sh --upgrade`.

## 1.0.4 — 22 October 2026

The command line, and the enrolment page.

- **`otp` (or `otp`) with nothing after it, typed at a terminal, says what it
  is doing** - the same as `--status` - instead of starting a second daemon
  that failed on the port the running one holds. The daemon itself is now
  `otp --daemon`; `otp.service` starts it so (under systemd, or anything else
  that is not a terminal, a bare `otp` is still the daemon).
- **Only one daemon at a time**: a second one stops at once and says which one
  is running (`/var/lib/otp/otp.lock`). And the RADIUS sockets no longer set
  SO_REUSEADDR, which on UDP let a second process bind the very same port
  and take half the packets.
- A daemon started by hand as root becomes the account `otp`, as the rest of
  the command line already did.
- **Colour as in isemon**: colorama when it is installed (the installer puts
  `python3-colorama` in place, or takes it from pip), the same escape
  sequences written by hand when it is not. `--help` is isemon's: two
  columns, the options green, their values yellow, the headings cyan, and
  THINGS PEOPLE ACTUALLY TYPE at the end. `NO_COLOR=1` and `--no-color` turn
  it off; a pipe gets none.
- **`--check` checks more than `--status` shows**: the key of the tokens, the
  age of the latest copy, PHP and php2shell, every client, every realm and
  whether its directory exists, every domain controller step by step, and
  where isemon's lines go.
- **The enrolment page** is headed *One-time passwords* (*Jednorázová hesla*)
  unless `portal_title` says otherwise - it said *Google Authenticator*. It
  links to the administration pages at the bottom, and while no realm with a
  directory is set up it says that nobody can enrol yet and that
  administrators sign in at `/admin/` - instead of "the name or the password
  is not right" to the administrator who has just installed it.

- The daemon's answers on the pages ("the directory cannot be reached just now" and
  the rest) are in Czech as well, not half-translated.

Upgrading: unpack 1.0.4 and run `./install.sh --upgrade` - it puts the new
`otp.service` in place, with `--daemon`.

## 1.0.3 — 22 October 2026

- **`otp` works as well as `otp`.** The installer links the command under both
  names, `/usr/local/bin/otp` and `/usr/local/bin/otp` — `otp --status`,
  `otp --log`, `otp --radtest falco 135830`. A different `otp` already on the
  machine is left alone, with a warning. `--uninstall` takes the link away.

Upgrading: unpack 1.0.3 and run `./install.sh --upgrade`.

## 1.0.2 — 22 October 2026

The installer.

- With firewalld not running, the firewall step was skipped without a word.
  It now says so, and what has to be let through by whatever filters the
  machine instead: TCP 443 (and 80), UDP 1812 and 1813 from the VPN
  concentrators.
- `--radius-from 127.0.0.1` (or `::1`) no longer becomes a firewalld rule:
  the machine's own packets never meet the firewall.

Upgrading from 1.0.0 or 1.0.1: unpack 1.0.2 and run `./install.sh --upgrade`.
The daemon, the pages and the database are unchanged; the version number on
them moves to 1.0.2.

## 1.0.1 — 22 October 2026

The installer.

- **It ended without a word at "PHP, and php2shell" on a machine that never
  had PHP.** `dnf module list --enabled php` exits 1 when no PHP stream is
  enabled, and under `set -euo pipefail` that ended the script. Its output is
  now taken first and read afterwards; PHP goes onto `php:8.3` as intended.
- The same kind of trap in two more places that had not been reached yet:
  the check for FreeRADIUS holding UDP 1812, and the list of PHP packages on
  Debian / Ubuntu.
- Nothing ends silently any more: whatever stops the installer prints
  `ERROR: line N: "command" ended with X`.

Upgrading from 1.0.0: unpack 1.0.1 and run `./install.sh` again (or
`./install.sh --upgrade` where 1.0.0 finished installing). The daemon, the
pages and the database are the same as in 1.0.0.

## 1.0.0 — 22 October 2026

The first version: the RADIUS server, TOTP, the QR codes, Active Directory,
realms and groups, the enrolment and administration pages, isemon's syslog
lines, SQLite / MariaDB / PostgreSQL, the import of a totpcgi + FreeRADIUS
server, the installer with PHP fixed against php2shell, Czech.
