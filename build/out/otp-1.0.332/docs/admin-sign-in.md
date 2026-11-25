# The sign-in page of the administration: a password, Windows and a certificate together

Since 1.0.277. How the three ways of signing in to the administration pages fit on one page - what
the page offers in each combination, what is tried by itself, in which order, and what a refusal
looks like. How each way works inside: [admin-kerberos.md](admin-kerberos.md) (Windows) and
[admin-certificate.md](admin-certificate.md) (a smart card, a YubiKey).

## The rules

1. **Everything is off by default.** An installation that sets nothing has the name and password form.
2. **The password stays** until it is switched off on purpose (*No password at all*); Windows and the
   certificate are added beside the form.
3. **One person, one account**: a password (`falco`, `falco@corp.example`, `CORP\falco`), a Windows
   ticket and a certificate (its UPN) land in the same account - the directory's sAMAccountName, with
   the role of its groups. A local account of the same name keeps its password and is never signed in
   by Windows or a certificate.
4. **The second step is asked after every way**, every time (*A second step when signing in to these
   pages* - an app, a code by mail or SMS, a passkey).
5. **Nothing is tried by itself twice**: after *Sign out*, after a refusal, or once in a browser tab,
   nothing starts on its own again.
6. **A browser with no Windows ticket is remembered for 30 days.** Outside the domain a browser asked
   for a ticket may show a window of its own for a name and password; cancelled (or NTLM offered, which
   is refused), that browser is marked, and Windows is not tried by itself there for 30 days - the form
   and the button *Sign in with Windows* are there, and the button works. A sign-in with Windows
   forgets the mark. Computers in the domain sign in silently as before and are never marked.
7. **Refusals say why** on the page, and as an event for an administrator.
8. **Never locked out**: *No password at all* is in effect only while Windows or a certificate is on;
   the keytab, or the last authority, cannot be taken away on the pages while it alone signs people in;
   root's way back is `otp --set admin_password_off=0`.
9. **A cluster**: the same on every node and on the VIP address - the settings are the cluster's, the
   keytab and the authorities are put in once, each node's nginx serves the certificate's port for its
   own name and the VIP address's.

## The settings (Settings → Accounts, three cards)

| Setting | Default | Card |
|---|---|---|
| Sign administrators in with Windows (Kerberos) | off | Signing in with Windows |
| ...by itself when the sign-in page opens | off | Signing in with Windows |
| Kerberos realm | from the base DN | Signing in with Windows |
| Sign administrators in with a certificate | off | Signing in with a certificate |
| ...by itself when the sign-in page opens | off | Signing in with a certificate |
| The certificate's own port | 8443 | Signing in with a certificate |
| Which account a certificate is | compat | Signing in with a certificate |
| Check that a certificate is not revoked (CRL) | on | Signing in with a certificate |
| No password at all - only Windows or a certificate | off | The sign-in page |

The card **The sign-in page** says in words what a person meets with the settings as saved: the name
and password offered or not, each way a button or tried by itself, the order, and what happens after a
refusal and after *Sign out*.

## When the page opens

| Windows | Certificate | What happens |
|---|---|---|
| button | button | nothing - the person chooses |
| by itself | button | Windows, silently; outside the domain the form and the certificate's button stay |
| button | by itself | the certificate at once (the browser's chooser, the card's PIN); back to the form with why, if it does not work |
| by itself | by itself | **Windows first, silently**; the certificate **only when this computer has no Windows ticket** (a computer outside the domain with a smart card); then the form |

A refusal of either is not a reason to try the other: a person Windows refuses (no group, switched off)
is told so and nothing else starts. Only "this computer has no ticket at all" moves on to the
certificate. When people often sign in with a password (the local `admin`, external staff), keep the
certificate a button: by itself, the page leaves for the chooser before anybody can type.

**No password at all**: no name and password on the page, a password refused on the server too (local
accounts as well), no password set or changed on the pages. With one way alone on, it is tried by itself
whatever its own switch says - the page has nothing else to offer.

## For implementing it elsewhere

The page knows, before anybody is signed in, only: `kerberos`, `kerberos_auto`, `cert`, `cert_port`,
`cert_auto`, `password` (from the daemon's health). Then:

```
if a second step is owed                      -> show it, nothing else
elif Windows by itself, not tried in this tab, not signed out in this tab:
     (and not marked "no ticket" in this browser in the last 30 days)
     try Windows silently
       signed in                              -> reload (or the second step)
       refused with a reason                  -> say why, stop
       no ticket at all (or NTLM offered)     -> mark the browser for 30 days;
                                                 the certificate by itself? go there : stay quiet
elif the certificate by itself, not tried, not signed out, not just refused:
     go to the certificate's port (a nonce first, top-level navigation)
else focus the name field
```

The flags are in `sessionStorage` (`otp.krb.tried`, `otp.cert.tried`, `otp.krb.out` - signed out): per
tab, gone with it. A refusal from the certificate's port comes back as `?certsaid=<why>`. One mark is in
`localStorage`: `otp.krb.none` - the time this browser had no Windows ticket; Windows is not tried by
itself while it is under 30 days old, and a sign-in with Windows takes it away.
