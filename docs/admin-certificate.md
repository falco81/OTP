# Signing in to the administration with a certificate (a smart card, a YubiKey)

Since 1.0.275. **Off by default.** A certificate of the domain's authority (AD CS) - on a smart
card, a YubiKey (PIV) or in the computer's store - signs its person in to the administration pages
without a password. Never NTLM, never a password on that way.

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
| *the CRL at ... could not be had* | The CDP does not answer from the nodes (the firewall, the proxy); with revocation checked nobody signs in until it does. |
| *names no user* | No UPN in the Subject Alternative Name - fix the template. |
| *of another account: its SID is ...* | The SID in it is not the account's (the UPN was moved to somebody else). |
| *names no SID of its account* | `strong`, and a certificate from before KB5014754 or an offline template. |
| *... none of the groups given a role here holds it* | Add the person to a group of a role. |
| *not started from this browser's sign-in page* | A link of somebody else's, or the 5 minutes passed - press the button again. |
