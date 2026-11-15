# Signing in to the administration with a certificate (a smart card, a YubiKey)

Since 1.0.275. **Off by default.** A certificate of the domain's authority (AD CS) - on a smart
card, a YubiKey (PIV) or in the computer's store - signs its person in to the administration pages
without a password. Never NTLM, never a password on that way.

How this way sits beside a password and the other way on one sign-in page (since 1.0.277): [admin-sign-in.md](admin-sign-in.md).

- **A port of its own.** nginx asks the browser for a certificate only on `admin_cert_port` (8443),
  never on 443: nobody opening the enrolment pages or the administration's own sign-in is ever
  asked for a certificate. Only the sign-in is served there; everything else on that port is 404.
- **Checked by otp itself**, not trusted from nginx:
  - the chain to an authority put in on the pages (`openssl verify`), its dates;
  - a key usage for signing in: *Client Authentication* or *Smart Card Logon*;
  - not revoked - the CRL at the certificate's *CRL Distribution Point* (http), kept until its next
    update; no CRL to be had, no sign-in (`admin_cert_crl`, on by default);
  - the person: the **UPN** in its *Subject Alternative Name*, looked up in the directory the
    administrators sign in against - on, not locked, not expired; the role of its groups;
  - `admin_cert_map`: **compat** (default) - the SID the AD CS writes into a certificate since
    KB5014754 must be the account's when it is there; **strong** - it must be there; **upn** - the
    UPN alone.
- **The second step stays.** With *A second step when signing in to these pages* on, it is asked
  after the certificate, every time.
- **One person, one account**: the account is named by the sAMAccountName, as with a password or
  Kerberos - whichever way they signed in first.
- **A cluster**: the authorities are put in once, kept in the database (signed with the guard on)
  and written by every node; root's helper of each node makes nginx's server on the port from that
  node's HTTPS server - and from the VIP address's (its address, name and certificate) beside it.
  The firewall lets the port in for the administrators' networks; SELinux lets nginx have it (8443
  is `http_port_t` already).
- **Login CSRF** is refused: the sign-in starts from the sign-in page with a nonce in a cookie of
  that browser (5 minutes, used once).

## Setting it up

1. **Settings → Accounts → Sign administrators in against the directory**, and the groups of each
   role.
2. **AD CS**: a template from *Smartcard Logon* (or *User*) - the *Subject Alternative Name* built
   from Active Directory with the *User principal name (UPN)*; key usages *Client Authentication*
   and *Smart Card Logon*; a *CRL Distribution Point* over http in the authority's Extensions,
   reachable from the nodes. Since KB5014754 (May 2022) the authority writes the account's SID into
   each certificate it issues from AD.
3. **A YubiKey**: enrolled from Windows with the template's smart card enrolment or `certreq`, or
   with YubiKey Manager (a CSR from PIV slot 9a, signed by the authority). Windows asks for its PIN
   when the browser offers the certificate.
4. **Settings → Accounts → Signing in with a certificate → Put in an authority…**: the issuing
   authority and the root (PEM, DER or `.p7b`). A person's certificate is refused.
5. Switch on **Sign administrators in with a certificate**; the port (8443) if another is wanted.
6. **Try my certificate** opens the port in a new tab: the browser offers a certificate and the
   page says who it would sign in, and as what - nothing is signed in.

## Revocation (CRL)

Since 1.0.278, as the crl-revocation-kit says it (acme 1.0.104). With *Check that a certificate is not
revoked* on (`admin_cert_crl`, the default):

- **No CRL, no sign-in.** When a CRL cannot be had and no good copy is kept, nobody signs in with a
  certificate it covers.
- **Which CRLs**: the one at the certificate's *CRL Distribution Point* (up to three of its `http://`
  addresses, the first that answers), its **delta CRL** when the certificate or its CRL names one
  (*Freshest CRL*; a delta named and not to be had means no sign-in), and the same for **every
  authority above it among those put in, except the root** (an issuing authority revoked by its root
  signs nobody in). Then one `openssl verify -crl_check_all [-use_deltas]` against the authorities put
  in alone - never the system's store. An authority above the person's certificate that names **no**
  CRL at all is not checked (it signed people in before 1.0.278 and still does), and then only the
  person's certificate is checked against its CRLs (`-crl_check`); give every issuing authority a CDP
  over http to have them all checked.
- **Only for a certificate whose chain is already good**: a CRL address written into just anybody's
  certificate is never fetched.
- **When**: at a sign-in, or *Fetch now*. A CRL is used for ten minutes at most, or until its next
  update if sooner; a failed fetch less than a minute ago is not tried again. When its address does
  not answer, the last good one is kept until its next update - then nothing. A CRL already past its
  next update when fetched counts as none.
- **From where**: **http only** (no https, ldap, or a name and password in the address), by **this
  node's own resolver** (`/etc/hosts`, the DNS of Settings → Network) and **never through the proxy**
  - AD CS publishes its CDPs inside. Every address the name has is checked, and none may be loopback,
  link-local, multicast, unspecified, reserved or a cloud's metadata service (169.254.169.254 and the
  others, in any spelling of the number); private addresses (RFC 1918, fc00::/7) are fine. The
  connection is made to the address checked - the name is not looked up again; no redirect is
  followed, 8 MB and 15 s at most.
- **Each node fetches and keeps its own** - a node that cannot reach a CDP refuses on its own. It
  publishes only facts and dates of them (never a CRL), at most 24.

**The lag**: a card revoked at the authority stops signing in once the authority has **published** a
CRL listing it, plus up to ten minutes. With AD CS's defaults (base weekly, delta daily) that can be
a day. After revoking a lost card, publish by hand on the authority - `certutil -CRL` - then press
**Fetch now**.

**The network**: every node must reach every CDP over http - the person's issuing authority's, and
the issuing authority's own (the root's CRL). Allow them through the firewall from the nodes; they
are fetched straight, never through the proxy.

### On the card

*Settings → Accounts → Signing in with a certificate → Revocation lists (CRL)*: one row for each CRL
a node keeps, and one for each CRL the authorities name that has not been fetched yet. The pill of
its next update says, in this order: **not fetched yet** (grey), **run out** or **not had** (red -
nobody signs in with a certificate it covers), **within a day** (amber; AD CS's delta CRLs always
are), **last fetch failed** (amber - the last good one is kept until its next update), **good**. A row
opens to this update, next update, number, size, how many are revoked, the signature (checked by
openssl against the authorities put in), the issuer, the error, the address and **each node's**
fetch. **Fetch now** and **Clear all** (and each row's own two buttons) are asked of every node -
each does it itself - and a box shows each node's answer as it comes. A full administrator only;
each is written to the events.

### On the command line

```
otp --cert-crl [--json]        the table, as text
otp --cert-crl-fetch [URL]     Fetch now - every CRL, or one - on every node; waits a minute; exit 1 if any failed
otp --cert-crl-clear [URL]     Clear - one, or all (asks; --yes) - on every node
```

## Values for a certificate request (1.0.282)

*Settings → Accounts → Signing in with a certificate → Values for a certificate request…* (a full
administrator): an account of the directory set for administrators - `jnovak`, `CORP\jnovak` or
`jnovak@corp.example` - looked up, and what its certificate must name to sign in here, each with a
button to copy it:

| | | |
|---|---|---|
| **Subject** | `CN=<the account's CN>` | the certificate's name |
| **SAN: UPN** | `jnovak@corp.example` | *Other Name - Principal Name* (1.3.6.1.4.1.311.20.2.3): the account it signs in |
| **SAN: URL** | `tag:microsoft.com,2022-09-14:sid:S-1-5-21-...` | the account's SID - the **strong mapping** of KB5014754 |
| **SAN: e-mail** | the account's mail | not needed to sign in |

And the whole request as **certreq**'s `request.inf` (Windows: `certreq -new request.inf request.req`,
then `certreq -submit -attrib "CertificateTemplate:..." request.req`) and **openssl**'s config (a key
made outside Windows, a YubiKey's slot 9a) - to copy or download. The window also says whether a
certificate of the account would sign anybody in: no UPN, no SID with *strong* mapping, the account
switched off or locked, none of the groups given a role here. Nothing is changed or kept.

**Make a CSR…** (1.0.283) makes the request itself, in the browser: a second window chooses the key (RSA
2048/3072/4096, ECDSA P-256/P-384), the subject (CN, O, OU, L, ST, C), which of the UPN, the SID's URL and
the e-mail go into the SAN (each to be edited), the extended key usages (Client Authentication, Smart Card
Logon, Secure Email) and the template of AD CS. The key pair is made by the browser (WebCrypto) and never
leaves it - nothing of it reaches the server; the request (`.csr`, PEM) and the private key (`.key`,
PKCS#8, by default locked by a passphrase: PBES2 with PBKDF2-SHA-256 and AES-256-CBC) are downloaded.
For a smart card or a YubiKey's PIV slot the key is made on the card instead (certreq's `request.inf` with
the Smart Card Key Storage Provider, or `ykman piv keys generate` and `ykman piv certificates request`).

The SID is read from the certificate's SID extension (1.3.6.1.4.1.311.25.2), the SAN's *Other Name* of
it, **or the SAN's URL** `tag:microsoft.com,2022-09-14:sid:...` (1.0.282) - any of them satisfies
*strong*.

## OCSP and CRLs from the directory

Two settings on the card, both **off by default** - with them off, revocation is checked by the CRLs
alone, exactly as before (1.0.279).

### Ask an OCSP responder (`admin_cert_ocsp`)

| Mode | The responder says good | revoked / unknown | no answer | names no responder |
|---|---|---|---|---|
| `off` | - | - | - | the CRLs, as before |
| `first` | taken | refused | its **CRL** (refused when CRLs are off) | its CRL |
| `only` | taken | refused | **refused** | the person's certificate: **refused**; an authority above: its CRL |
| `both` | then its **CRL** too | refused | refused | its CRL |

- **The certificate and every authority above it but the root**, each asked of its own issuer's
  responder: the OCSP address in its *Authority Information Access* (up to two http addresses, tried
  in turn) - or **one responder for all** (`admin_cert_ocsp_url`), for certificates issued before the
  responder was there. That setting is refused unless it is an http address a CRL could be fetched
  from.
- **An authority above that names no responder** (an issuing authority under an offline root seldom
  does) is held to its CRL in every mode, even with CRLs off; one that names no CRL either is not
  checked, as in 1.0.278.
- **An authority renewed with a new key under the same name** (as AD CS does): the one whose key
  signed the certificate (its *Authority Key Identifier*) is the one asked, and the one above it in
  the chain.
- **Asked only for a certificate whose chain is already good** - over http with the guards of a CRL:
  every address of the name checked (no loopback, link-local, metadata, multicast or reserved
  address), the connection made to the address checked, never through the proxy, no redirect,
  1 MB and 15 s at most. The request has no nonce (as Windows asks).
- **Checked by openssl against the authorities put in alone** (never the system's store): signed by
  the authority, or by a responder certificate it issued with *OCSP Signing*. Only openssl's own
  words are read - nothing the answer carries (a responder's name, a certificate's comment) is taken
  for them. A forged, unsigned or out-of-date answer is no answer.
- **Ten minutes at most**: an answer is used for 600 s, or until its next update when that is sooner.
  A responder that gave no answer is not asked again for a minute, whoever's certificate; while it
  does not answer, its last **good** answer is used until its next update.
- **The person is told little** (*the certificate cannot be checked for revocation just now*,
  *revoked*); which responder did not answer, and why, is in **Events**.

### CRLs from the directory (`admin_cert_crl_ldap`)

The `ldap:///CN=<CA>,CN=<server>,CN=CDP,CN=Public Key Services,CN=Services,CN=Configuration,DC=...`
address AD CS writes into its certificates is read too, after up to three http ones - **with the
connection of the directory set for administrators**, never the host written in the address. Only a
`cRLDistributionPoint` object under the configuration's Public Key Services, base scope, and only its
`certificateRevocationList` / `deltaRevocationList`. The same rules as over http: ten minutes, the
last good one until its next update, openssl's check, no CRL no sign-in. With the setting off, a
certificate whose only CRL is in the directory is refused (*names no CRL over http*).

### On the card

- **Revocation** in the facts shows the order as steps: *OCSP → no answer → CRL → none to be had →
  no sign-in* (blue OCSP, green CRL, red the end).
- **Online status (OCSP)**: a row for each answer kept on every node - the certificate, its issuer,
  the status (*good*, *last answer kept*, *run out*, *unknown*, *revoked*, *no answer*), the next
  update, the serial and when it was asked. A row opens (click, Enter, Space) to its details - signed
  by, this and next update, size, the last error, the responder's address and each node's answer.
- **Ask again** and **Clear all** (and each row's buttons) are asked of every node, by a full
  administrator only, and written to the events.
- A CRL read from the directory has an **LDAP** tag and its authority's name in the CRL table; its
  details say *Read from: the directory (LDAP)* and show the whole address.

```
otp --cert-ocsp [--json]          the answers kept: certificate, status, responder, dates, errors
otp --cert-ocsp-fetch [KEY]       ask every responder again (or the one of KEY); exit 1 if one did not answer
otp --cert-ocsp-clear [KEY]       forget them (asks first; --yes)
```

### AD CS

- **OCSP**: add the *Online Responder* role; issue it an *OCSP Response Signing* certificate; add a
  *Revocation Configuration* for the issuing authority (and one for the root, or use `first`); in the
  authority's *Extensions* - *Authority Information Access*, add `http://<responder>/ocsp` with
  *Include in the online certificate status protocol (OCSP) extension*. Certificates issued before
  that name no responder: set *OCSP responder of its own*, or use `first`.
- **LDAP CDPs** are AD CS's default; any domain account may read the configuration partition.
- **After revoking a lost card**: the Online Responder picks it up at its next CRL refresh - then
  *Ask again*; for CRLs, `certutil -CRL`, then *Fetch now*.

## When the card is taken out (1.0.285)

On the card *Signing in with a certificate*:

| Key | Values | Default | Shown as |
|---|---|---|---|
| `admin_cert_card` | `off`, `signout`, `grace` | `off` | *When the card is taken out* |
| `admin_cert_card_s` | 5-300 | 15 | *Checked every (seconds)* |
| `admin_cert_card_grace_s` | 5-600 | 30 | *...put back within (seconds)* |

- **`off`** (the default): nothing is checked, the page loads nothing more, and nginx's server on the
  certificate's port is written exactly as before.
- **`signout`**: the first check without the card ends the session; the sign-in page says *Signed out:
  the card you signed in with was taken out.*
- **`grace`**: a notice covers the page (*Put the card back*, the seconds left in a ring that empties, *Sign out*; nothing behind it
  can be used, and the server answers no question of the session meanwhile - HTTP 423). The card back in
  time: the notice goes. Not back in time: *Signed out: the card you signed in with was not put back in
  time.*
- **Another card** than the one signed in with ends the session at once, in either mode.
- Only a sign-in made with a certificate (by 1.0.285 or later) is watched - a password, Windows
  (Kerberos) and RADIUS never are.

### How

A browser has no event for "the smart card was taken out"; the only sure sign is that the card can no
longer sign. Every `admin_cert_card_s` seconds the page loads a picture from the certificate's port
(`/admin/?api=cert-alive`): a new TCP and TLS connection - while watching is on, nginx keeps no TLS
session (`ssl_session_cache off`, `ssl_session_tickets off`) and no connection (`keepalive_timeout 0`)
there - whose handshake only the card's key can sign. PHP hands the certificate that came (none: the card
is out) and the session's cookie to the daemon, which compares its SHA-256 with the one kept with the
sign-in. The answer is a picture 1 pixel wide (the card is there), 2 wide (out, the session waits) or a
403 (the session is over). A picture needs no CORS and gives another site nothing to read; the page's
Content-Security-Policy lets in that one address (`img-src ... https://<name>:<port>`), only for a
watched session. A handshake that fails reaches nothing: the page asks once more, then tells the pages on
443 (`?api=card-gone`), which hold or end only that same session.

The state is kept with the session in the database: either node of a cluster answers a check, and a
restart of the daemon forgets nothing. The server ends a watched session on its own too when the card
has been out longer than the grace plus *late* (*late*: three checks or 150 s, the longer - a browser
checks a tab in the background about once a minute). A session whose page has not checked for *late* +
grace + max(interval, 30 s) is **held, not ended**: a page asleep (an iPad's screen locked, Safari in the
background - iPadOS stops its pages entirely) is not a card taken out. Nothing of it is answered (HTTP
423) until a check finds the card again - the page checks the moment it wakes (shown again, focused, the
network back); no card then, and it goes as a card taken out. Every end is in the events: `... was signed
out: the card they signed in with was taken out` (`...was not put back in time`, `another certificate
than the one signed in with was offered (the card was changed)`).

### Kind to the card

- One check at a time; the tabs of one browser share one check (the others take its answer).
- No PIN at each check, normally: while the card stays in, Windows (the smart-card minidriver) and the
  browser keep the PIN; a YubiKey's PIV slot 9a has PIN policy `once` by default. A key with touch or PIN
  policy `always` would ask at every check - leave watching off for one.
- Windows may show *Insert a smart card* when the browser tries the missing key. Answering it fails the
  check; a check that waited on such a window is followed by a longer pause, so it does not come back
  again and again; after the end, the sign-in page tries nothing by itself, so the browser's certificate
  chooser does not open on its own either.
- A one-off lost connection is asked again before it counts as the card out.

For the whole computer, Windows does it itself - the group policy *Interactive logon: Smart card removal
behavior* = **Lock Workstation** (or **Force Logoff**), with the service **Smart Card Removal Policy**
(`SCPolicySvc`) started. Both together are best. A load balancer in front of the certificate's port must
pass it through as TCP.

## On the sign-in page

**Sign in with a certificate** below the form: the browser goes to `https://<name>:8443/admin/`,
asks which certificate (the system asks for the card's PIN), and comes back to the pages on 443
signed in - or with why not.

*No password at all - only Windows or a certificate*: no field for a password anywhere on the pages,
every password refused - local accounts too. Switched on only from a sign-in made with Windows or a
certificate, and only while one of them is on. Locked out: as root,
`otp --set admin_password_off=0` (or `otp --cert off`).

## On the command line

```
otp --cert status              # on or off, the port, the authorities, each node, problems
otp --cert on|off
otp --cert-ca FILE             # put an authority in (every node gets it)
otp --cert-ca-drop SHA256
otp --set admin_cert_port=8443 --set admin_cert_map=compat --set admin_cert_crl=1
```

## The port

`admin_cert_port` (8443) is the certificate sign-in's alone: not 80 or 443, not the balancer's own
port (`web_proxy_port` - give that 9443, say, when both are used), not the API's, RADIUS's or the SSH
gate's, on either node. Saving one over the other is refused, whichever is set first, and so is a
port something else listens on already.

## Behind a load balancer

The port must reach the nodes as TCP (TLS passthrough): a balancer that ends TLS itself cannot hand
the client's certificate on. Open the port, or sign in to the nodes' own names.

## When it does not work

| What the page says | Why |
|---|---|
| *no certificate was sent* | The browser has no certificate of the authorities put in (the card not inserted, the PIN prompt cancelled, another authority). |
| *the certificate is not taken: certificate revoked* | In the CRL. |
| *the certificate is not taken: certificate has expired* | Run out. |
| *the certificate is not taken: unable to get local issuer certificate* | Its authority is not put in - put in the issuing authority and the root. |
| *... unsuitable certificate purpose* / *not for signing in* | No Client Authentication or Smart Card Logon. |
| *the CRL at ... could not be had* | The CDP does not answer from the nodes (the firewall; it is fetched straight, never through the proxy - http only, the node's own DNS); with revocation checked nobody signs in until it does. Settings → Accounts → the certificate's card → Revocation lists says which, on which node. |
| *names no user* | No UPN in the Subject Alternative Name - fix the template. |
| *of another account: its SID is ...* | The SID in it is not the account's (the UPN was moved to somebody else). |
| *names no SID of its account* | `strong`, and a certificate from before KB5014754 or an offline template. |
| *... none of the groups given a role here holds it* | Add the person to a group of a role. |
| *not started from this browser's sign-in page* | A link of somebody else's, or the 5 minutes passed - press the button again. |
