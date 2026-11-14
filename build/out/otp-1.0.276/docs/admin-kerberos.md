# Signing in to the administration with Windows (Kerberos)

Since 1.0.274. **Off by default.** A browser on a computer in the domain signs its person in to
the administration pages without typing a password: it sends a Kerberos ticket for the name it
opened (SPNEGO, `Authorization: Negotiate`), otp checks it against the keytab of that name, and
looks the person up in the directory the administrators sign in against. The role comes from
the directory's groups, exactly as after a password.

- **The second step stays.** With *A second step when signing in to these pages* on, Kerberos
  takes the place of the password only: the code (app, mail, SMS or passkey) is asked after it,
  every time.
- **NTLM is never taken.** A token of NTLM - bare, or carried inside SPNEGO - is refused, and so
  is any mechanism of SPNEGO that is not Kerberos 5. There is no switch for it.
- **Only accounts of the directory.** A local account of otp signs in with its password; a ticket
  of the same name is refused.
- **Nothing to install.** otp calls the system's own GSS-API library (`libgssapi_krb5`, part of
  `krb5-libs` on RHEL/Rocky/AlmaLinux and `libgssapi-krb5-2` on Debian/Ubuntu) through Python's
  standard library. No KDC is contacted: the ticket is checked with the key in the keytab.
- **A cluster:** the keytab is put in once, kept sealed in the database and written out by every
  node itself. A ticket used on one node is refused on the other (the replay cache of the
  library is a node's own; the cluster's is in the database), also after the VIP address moved.

## Setting it up

1. **Settings → Accounts → Sign administrators in against the directory**: the directory, and the
   groups of each role (as for signing in with the directory's password).
2. **In AD**, as a domain administrator, a service account of its own - a normal user, *Password
   never expires*, *This account supports Kerberos AES 256 bit encryption*:

   ```
   setspn -S HTTP/otp.corp.example CORP\svc-otp-http
   setspn -S HTTP/otp1.corp.example CORP\svc-otp-http
   setspn -S HTTP/otp2.corp.example CORP\svc-otp-http
   ktpass -princ HTTP/otp.corp.example@CORP.EXAMPLE -mapuser CORP\svc-otp-http ^
          -crypto AES256-SHA1 -ptype KRB5_NT_PRINCIPAL -pass * -out otp-http.keytab
   ```

   One SPN for every name the pages are opened by (the VIP address's name and each node's). The
   keytab of the first one is enough: a ticket for any of the names is encrypted with the same
   key of the account, and otp takes a ticket for any principal whose key is in the keytab. The
   card shows the names otp knows and fills them into these commands.
3. **Settings → Accounts → Signing in with Windows (Kerberos) → Put in a keytab…** (a full
   administrator). Refused: a file that is not a keytab, one with no `HTTP/` principal, one with
   only weak keys (DES, RC4). The card lists its principals, key versions and kinds of key - never
   a key.
4. Switch on **Sign administrators in with Windows (Kerberos)**. The realm is taken from the
   directory's base DN (`DC=corp,DC=example` → `CORP.EXAMPLE`) unless set in **Kerberos realm**;
   a ticket of another realm is refused.
5. **The browsers** send a ticket only to names they trust:
   - Edge and Chrome on Windows: group policy `AuthServerAllowlist` = `otp.corp.example,otp1.corp.example,...`
     (or Internet Options → Security → Local intranet → Sites).
   - Firefox: `network.negotiate-auth.trusted-uris` = the same names (policy or about:config).
6. **Try my browser's ticket** on the card says who your browser would sign in, and as what -
   nothing is signed in or changed.

## On the sign-in page

- **Sign in with Windows** below the form.
- *...by itself when the sign-in page opens*: the page tries Kerberos at once and shows the
  form only when it did not work. After **Sign out** it is not tried by itself again in that tab.
- *...and no password at all - only Windows*: the page offers no name and password, and the
  pages refuse every password - local accounts too. Switched on only from a sign-in made with
  Windows (so it is known to work for the one switching it on) and only with a keytab in. Off
  again by itself in effect when Kerberos is switched off. Locked out: as root,
  `otp --set admin_password_off=0` (or `otp --kerberos off`).
  In this mode no field for a password is shown anywhere on the pages - not *A new password* in
  Your account, not *Set a new password* of an account, not the first password of *Make an
  account* - and a change of a password is refused by the daemon too.

## On the command line

```
otp --kerberos status            # on or off, realm, keytab, each node, problems
otp --kerberos on|off
otp --kerberos-keytab FILE       # put a keytab in (every node gets it)
otp --kerberos-keytab-drop
otp --set admin_kerberos_auto=1  # by itself on the sign-in page
otp --set admin_password_off=1   # only Windows (the way back: =0)
```

## How it works

```
browser ──GET /admin/──────────────► the sign-in page: "Sign in with Windows"
browser ──POST ?api=kerberos-login─► PHP: no Authorization → 401, WWW-Authenticate: Negotiate
browser ──POST, Authorization: Negotiate <SPNEGO token>──► PHP → daemon /api/auth/kerberos
daemon: NTLM? refuse · gss_accept_sec_context (keytab) · mechanism Kerberos 5? · principal
        user@REALM, the realm wanted? · once in the cluster? · the directory: the account, its
        state, its groups → role · the session (the second step first, when on)
PHP: the session's cookie (HttpOnly, SameSite=Strict); a refusal is 403, never another 401
```

nginx takes a header of up to 32 kB (`large_client_header_buffers 4 32k`): a ticket of a person
in many groups is larger than nginx's 8 kB. The upgrade puts it in.

## When it does not work

| What the page says | Why |
|---|---|
| *the browser sent no Kerberos ticket* | The name is not among the browser's intranet sites; the computer is not in the domain; the person signed in locally; the name has no SPN. |
| *the browser offered NTLM, which is never taken here* | No ticket could be had for `HTTP/<name>` - usually a missing SPN, or the name opened is an IP address. |
| *the ticket was not taken: ...* | The keytab is of another key version (the account's password changed - make it again), or another account; the clocks are more than 5 minutes apart. |
| *... is of the realm X, and only Y signs in here* | Set **Kerberos realm**. |
| *... is known, and none of the groups given a role here holds it* | Add the person to a group of a role. |
| *... is an account of this server* | A local account of otp of that name: it signs in with its password. |
| *this ticket was used already* | A replay - the same token sent twice. |
