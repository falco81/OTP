# Testing on the real devices: Cisco FTD and Omnissa Horizon UAG

A checklist for the day otp is put in front of a **Cisco Firepower Threat Defense** (remote
access VPN, managed by FMC, people on **Cisco Secure Client**) and an **Omnissa (VMware)
Horizon Unified Access Gateway** (RADIUS as the second factor before Horizon). Go through it
once on each device, with both nodes of a cluster up, and again with one of them down.

What otp sends back for each product, attribute by attribute, is in
[reply-attributes.md](reply-attributes.md); the second window (codes by e-mail and SMS, the app
in a second window) in [codes-by-mail-and-sms.md](codes-by-mail-and-sms.md); names with several
suffixes in [realms-and-suffixes.md](realms-and-suffixes.md); the two nodes and the VIP address
in [high-availability.md](high-availability.md).

## Where to look in otp

Every scenario below is checked in the same three places:

- **Log** (the tab): one row a request. The columns: *When*, *Name* (with the realm under it),
  *Result* - `let in`, `refused`, `asked for the code` (an Access-Challenge), `not answered`,
  `accounting` - *Why - what the token said*, *Where* (the RADIUS client), *From* (the
  Calling-Station-Id: the person's public address on FTD), *Device*, *ms*, and *Node* in a
  cluster. Click a row for *How it was decided* (every step: the realm, the account found, the
  directory password, the group, the code), *What was asked* (every attribute that came -
  passwords, CHAP and MS-CHAP values shown as `<suppressed>`) and *What was answered* (the
  attributes that went back). Filter *every client* → the FTD or the UAG.
- **Events**: a token locked out (*the token of NAME is locked out for N min after M wrong codes
  in a row*), a request from an address that is no client (*a request from A, which is not a
  client, was not answered*), a code that could not be sent by mail or SMS.
- **The token's card** (Tokens → the name): its history - *A code was sent by SMS to
  +420\*\*\*\*\*\*222*, *Code sent by SMS accepted*, *Scratch-token used*, wrong codes - and
  *Unlock it* for a locked token.

The reasons, word for word, as the Log shows them:

| What happened | Result | The reason (row detail) / *Why* |
|---|---|---|
| password and code right | let in | *Why*: `Valid token used` (or `... within window size used`) |
| code wrong | refused | `Denied by the token server: Not a valid token` |
| AD password wrong | refused | `the directory refused the password: ...` |
| a code used before (a second sign-in with the same code) | refused | `Denied by the token server: Token has already been used once` |
| three wrong codes in *Wrong codes before a pause* | refused | `Denied by the token server: Rate-limit reached, please try again later` |
| the token locked | refused | `Denied by the token server: Locked out after too many wrong codes, please try again later` |
| the password alone, a code is asked for | asked for the code | `the code is asked for in a second window`; *Why*: `Code asked for` / `Code sent by SMS` / `Code sent by mail` |
| a wrong code in the second window | asked for the code | `the code was not right: asked again (1 of 3)` |
| the second window answered too late, or its State already used | refused | `the code was asked for too long ago: sign in again` |
| the second window answered through another client | refused | `the answer does not belong to the question it names` |
| account disabled / locked in AD | refused | `the account is disabled in the directory` / `the account may not sign in: it is locked out in the directory` |
| not in the realm's group | refused | `account does not pass LDAP group filter(s): ...` |
| CHAP, MS-CHAPv1, MS-CHAPv2 | refused | `the request carries no User-Password (PAP)` |
| a name with no realm | refused | `no realm takes the name NAME` |
| from an address that is no client | not answered | `the address A is not one of the clients` |
| a client that signed its requests before sends one unsigned | not answered | `there is no Message-Authenticator, and this client must send one ...` |

A refusal goes back with **no Reply-Message** unless *Settings → The RADIUS server → Say why in
a refusal* is on - the device shows its own "authentication failed"; the reason is in otp's Log.

From the command line of a node: `otp --radtest NAME -` asks for the password (and the code)
at a prompt and then for the code of a second window, as the VPN does (the Test tab does the
same from the pages). Do not put a password on a command line.

## Set up in otp first

1. *Settings → Clients*: one client for each FTD (the address it sends RADIUS from - the
   interface facing otp, not the outside address) and one for each UAG. The shared secret the
   same as on the device. *Must send a Message-Authenticator*: on for the FTD; for the UAG only
   once you see it sends one (Log → a row → *What was asked* lists `Message-Authenticator`).
   *Realm added to names without one*: for a UAG that sends the bare user name (see *Name ID
   suffix* below).
2. *Settings → Realms*: the realm for the VPN people - *The password is*:
   - FTD: *the directory password followed by the code* (one field) or *the directory password;
     the code in a second window* (Secure Client shows a second window);
   - UAG: *the code alone* (Horizon asks the AD password itself, after RADIUS) or *the directory
     password; the code in a second window* (UAG's RADIUS page takes the AD password, then
     shows the challenge).
   Groups and their answer (FTD): `ASA-Group-Policy = GP_NAME` and/or `Class = OU=GP_NAME;`.
   The UAG reads no attribute - only Accept or Reject.
3. Test people: one with the app, one with codes by SMS, one with codes by e-mail, each with
   recovery codes; one account disabled in AD; one in no allowed group.
4. A test with the Test tab (or `otp --radtest`) for each before the device is involved.

## Cisco FTD (FMC)

### What to set

- **Objects → Object Management → AAA Server → RADIUS Server Group → Add**
  - *RADIUS Servers*: **both nodes** (or the VIP address - see *A node down*), authentication
    port 1812, accounting port 1813, the key. *Timeout* **10-15 s** per server is right for otp:
    the Access-Challenge goes back at once - a code is mailed or sent by SMS after the answer,
    not before - and only a slow directory makes otp take longer. A long timeout (60 s) delays
    the move to the other node by as long when one is down.
  - *Retry Interval*: 10 s (the default) - the FTD sends the same packet again; otp answers a
    repeat from its memory (*Settings → The RADIUS server → A repeated request is the same one
    for (s)*, 30 s), the code is not used twice.
  - *Message-Authenticator*: where the release offers it (the BlastRADIUS fixes, FTD 7.4.2 / 7.6
    and later), switch it on. otp signs every Access-Accept, Access-Reject and Access-Challenge
    with one, and checks the one the FTD sends.
  - *Enable dynamic authorization* (CoA): leave off - otp sends no CoA.
- **Devices → Remote Access → (the policy) → Connection Profile → (the profile) → AAA**
  - *Authentication Method*: **AAA Only**; *Authentication Server*: the group.
  - *Authorization Server*: none needed - the group policy comes back in the Access-Accept.
  - *Accounting Server*: the same group (optional; otp writes Start and Stop rows).
  - *Strip Realm from username*: **off** when the realm in otp is found by the suffix
    (`novak@corpnet.cz`); with it on, set *Realm added to names without one* on the client.
  - Password management (*Enable Password Management*): **off** - with it the FTD asks with
    MS-CHAPv2, and a code travels only as PAP.
- **Remote Access → (the policy) → Advanced → Group Policies**: every group policy otp may
  name (`GP_NAME`) must be **added here**, or the FTD falls back to the profile's default group
  policy without a word.
- Deploy. The Secure Client profile's *Authentication Timeout* (Preferences part 2) must be
  longer than the FTD's timeout for one server, so the person still waits when the first
  server does not answer.

### What to run, and what to check

| # | Scenario | On the FTD | In otp |
|---|---|---|---|
| F1 | **Right code** - password followed by the code in one field | Session up; `show vpn-sessiondb anyconnect filter name novak@corpnet.cz` lists it with the right *Group Policy* and *Tunnel Group* | Log: `let in`, *Where* the FTD, *From* the person's public address; row → *What was answered*: `ASA-Group-Policy` / `Class` |
| F2 | **Wrong code** | Secure Client: login failed | `refused`, `Not a valid token`; the token's card counts one wrong code |
| F3 | **Wrong AD password**, right code | login failed | `refused`, `the directory refused the password`; the code is **not** used - the same code with the right password lets in |
| F4 | **The same code again** (a second sign-in within 30 s) | login failed | `refused`, `Token has already been used once` |
| F5 | **Second window, the app** (realm: the code in a second window) | Secure Client shows a second window with *Type the code from the app on your phone* | `asked for the code`, then `let in`; the second row's steps start with *checked with the first request* |
| F6 | **Second window, SMS** | the second window: *Type the code sent by SMS to +420\*\*\*\*\*\*222* (in the token's language) | `asked for the code` *Code sent by SMS*, then `let in` *Code sent by SMS accepted*; the token's history: *A code was sent by SMS to ...* |
| F7 | **Second window, e-mail** | *Type the code mailed to n\*\*\*\*@example.cz* | as F6, by mail; *Settings → Outgoing mail* shows it sent |
| F8 | **Wrong code in the second window**, three times | the second window again with *That code was not right - type it again*, then login failed | `asked for the code` *asked again (1 of 3)*, *(2 of 3)*, then `refused`; three wrong codes on the token |
| F9 | **Recovery code** in the second window (or after the password, in one field) | session up | `let in`, *Why* `Scratch-token used`; the token has one recovery code fewer |
| F10 | **Wrong AD password** with an SMS/mail token | login failed, **no SMS** arrives | `refused`, `the directory refused the password`; no *A code was sent* in the history |
| F11 | **Locked token** - wrong codes up to *Wrong codes in a row before a lockout* | login failed, also with a right code | `refused` *Locked out after too many wrong codes*; Events: *the token of ... is locked out*; *Unlock it* on the card, then F1 works |
| F12 | **Locked or disabled AD account** | login failed | `refused`, *the account may not sign in: it is locked out in the directory* / *the account is disabled in the directory* |
| F13 | **Group policy applied** - people of two AD groups with different `ASA-Group-Policy` | `show vpn-sessiondb detail anyconnect filter name NAME`: *Group Policy* as otp sent it (and its ACL, banner, split tunnel) | row → *What was answered* lists the attribute; *How it was decided*: *a member of GROUP* |
| F14 | **Accounting** | disconnect the session | two rows `accounting`, reasons `Start` and `Stop`, with the session's Class echoed in *What was asked* |
| F15 | **A node down** - `otp --maintenance on` on node 1 (or stop it) | `show aaa-server OTP` - node 1 *FAILED* after the timeout, node 2 *ACTIVE*; the sign-in goes through (it took about one timeout longer) | Log of node 2 (*Node* column): `let in` |
| F16 | **Back** - `otp --maintenance off` | after the reactivation (dead time / depletion) node 1 *ACTIVE* again | rows on node 1 again |
| F17 | **The VIP address** (a group of one server: the VIP) - node holding it to maintenance | the next try reaches the other node within seconds | rows on the other node |
| F18 | **Second window across nodes** - code typed after node 1 went down between the two windows | the second request goes to node 2 | node 2 lets in (the challenge is in the shared database) |

### On the FTD itself

- `show vpn-sessiondb anyconnect` / `show vpn-sessiondb detail anyconnect filter name NAME`:
  the session, its *Group Policy*, *Tunnel Group*, *Duration*.
- `show aaa-server OTP`: each server's state (ACTIVE / FAILED), how many requests, accepts,
  rejects, challenges, timeouts. Timeouts going up with otp's Log empty: a wrong address, a
  firewall, or the FTD sending from another interface than the client set up in otp - otp's Log
  then shows `not answered`, *the address A is not one of the clients* (and an Event).
- `debug radius all` (from `system support diagnostic-cli`; `undebug all` afterwards): every
  packet decoded - User-Name, NAS-IP-Address, State, Reply-Message, the vendor attributes.
  "Invalid authenticator" or a wrong Message-Authenticator: the shared secret differs.
- `test aaa-server authentication OTP host 10.0.0.50` - give user name and password at its
  prompts (not on the command line). Use it with a realm of *the password followed by the
  code*: the test cannot type a code into a second window. A right code is used up by it.

## Omnissa Horizon UAG

### What to set

In the UAG admin console: **Advanced Settings → Authentication Settings → RADIUS** (the gear),
then the Horizon edge service's *Auth Methods* set to RADIUS (chained with the AD password
where Horizon asks it after). The field names move a little between UAG releases.

- *Authentication type*: **PAP**. CHAP, MSCHAP V1 and MSCHAP V2 cannot carry a one-time code;
  otp refuses them (`the request carries no User-Password (PAP)`).
- *Shared secret*: as on the otp client.
- *NAS IP address*: any; otp finds the client by the address the packet comes from, and shows
  this value in the Log's NAS column. A UAG behind NAT: set up the client in otp with the
  address after NAT.
- *Server timeout*: 5-10 s; *Number of attempts to RADIUS server*: 3 - repeats of one request
  from the same UAG are answered from otp's memory.
- *Number of authentication attempts allowed* (wrong passcodes before UAG gives up): keep it at
  3 or below. otp pauses a token after *Wrong codes before a pause* (3) within *... (seconds)*
  (30): the 4th try in that time is refused **even with a right code**
  (`Rate-limit reached`) - and every wrong passcode counts towards the token's lockout.
- *Name ID suffix* (or *Realm suffix*): `@corpnet.cz` makes `novak` → `novak@corpnet.cz`, which
  is what otp's realm is found by. Without it, set *Realm added to names without one* on the
  otp client. A person who types the whole `novak@corpnet.cz` with the suffix set arrives as
  `novak@corpnet.cz@corpnet.cz` and is refused (Log: `the name has more than one @ (a suffix added to a name that had one already?)`) - tell
  people to type the name alone. `DOMAIN\novak` works (the domain is dropped).
- *Realm prefix*: leave empty unless otp's realm needs it.
- *Login page passphrase hint*: the label of the passcode field - *"Code from the app"* for a
  realm of the code alone, *"Windows password"* for a realm of the AD password with the code in
  a second window.
- *RADIUS challenge*: on (where the release has the switch) for a realm with the second window:
  UAG then shows otp's Reply-Message (*Type the code from the app on your phone*) above a field.
- *Enable secondary server*: the second otp node (or use the VIP address as the only server).
  The second window's State is known to both nodes of a cluster (one database) - **not** to two
  standalone servers.
- *Message-Authenticator*: newer releases send one; otp then requires it from that UAG for
  good (*Must send a Message-Authenticator* or not) - a UAG downgraded later must have the
  client's remembered state cleared (take the client away and add it again).
- Horizon (Connection Server, *Authentication*): with RADIUS at the UAG, the Connection Server's
  own 2-factor stays off. *Use the same user name for RADIUS and Windows* if the AD name and the
  RADIUS name differ only by the suffix.

### What to run, and what to check

| # | Scenario | On the UAG / Horizon client | In otp |
|---|---|---|---|
| U1 | **The RADIUS test** (the *Test* button of the RADIUS settings) with a real code | "successful" | `let in`, *Where* the UAG client; a code used up |
| U2 | **Right code** (realm: the code alone), then the AD password in Horizon | desktops listed | `let in`, *Why* `Valid token used` |
| U3 | **Wrong code** | "authentication failed", UAG offers another try | `refused`, `Not a valid token` |
| U4 | **AD password typed into the passcode field** | failed | `refused`, `Not a valid token`; the password is never in the Log |
| U5 | **Second window** (realm: AD password, then the code) | UAG shows the challenge text; the code → desktops | `asked for the code`, then `let in` |
| U6 | **Codes by SMS / e-mail** with the second window | the challenge says where the code went | as F6/F7 |
| U7 | **Recovery code** as the passcode | in | `let in`, `Scratch-token used` |
| U8 | **Attempts**: wrong passcode until UAG stops | UAG's own limit | each a `refused` row; the 4th within 30 s `Rate-limit reached`; at the lockout an Event, *Unlock it* |
| U9 | **Name forms**: `novak`, `novak@corpnet.cz`, `CORP\novak`, another suffix of the realm | in, except the doubled suffix | the row's *Name* as otp read it; steps: *the name is read as ...* |
| U10 | **CHAP / MSCHAP** set by mistake | failed | `refused`, `the request carries no User-Password (PAP)` (written once a minute for a client that does not sign its requests) |
| U11 | **NAS IP** set to an address otp does not know | in - the client is found by the source address | the Log's NAS column shows the configured value |
| U12 | **Primary otp down** (`otp --maintenance on`) | in, after one *Server timeout* | the row on the other node |
| U13 | **Locked / disabled AD account** | failed | `refused` before any code is looked at |

### On the UAG itself

- *Support Settings → Log Archive* (the log bundle, `UAG-log-archive*.zip`): `esmanager.log`
  (the edge service's RADIUS sign-ins: the user, the result, the timeout) and `authbroker.log`
  (the RADIUS conversation). "Timeout" with otp's Log empty: the address or the firewall;
  "invalid response authenticator": the shared secret.
- The *Test* button of the RADIUS settings sends one PAP request - it uses up the code typed.

## After the tests

- Log → filter the device's client → *refused*: nothing left that is not explained.
- Events: no *was not answered* for the device's address, no *could not be sent*.
- Unlock the test tokens that were locked; take away the test tokens that are not needed.
