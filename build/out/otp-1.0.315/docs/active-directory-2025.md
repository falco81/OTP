# Domain controllers on Windows Server 2025 (1.0.267)

What changes for otp when the domain controllers are replaced by Windows Server 2025 ones - and
what to check in *Settings → Directories* before and after each controller is replaced.

## How otp speaks to Active Directory

- Its own LDAP client (no `ldap3`, no `python-ldap`), a **simple bind** only: the reading account
  to find the person, then the person's own name and password. No NTLM, no Kerberos, no SASL -
  so channel binding (CBT), the end of RC4 in Kerberos and the removal of NTLMv1 do not touch it.
- It writes nothing to the directory (no password changes, no accounts, no groups).
- Encrypted by **LDAPS** (port 636, the default for a new directory) or **STARTTLS** (389);
  plain LDAP can be chosen, and the security check says so.
- TLS 1.2 or 1.3 (Python's default context); "Take old, weak certificates" allows TLS 1.0 and
  weak keys for old servers only - keep it off for Windows Server 2025.
- The certificate is checked against the authority given with the directory, or against the
  system's trusted roots (*Settings → Certificates and TLS → Trusted roots of the system*), **and
  against the server's name** as given in the list of servers.
- Several servers per directory, in order: one that does not answer, is busy or unavailable is
  marked down for a while and the next is asked - also in the middle of a sign-in. No DNS SRV
  lookup: list every controller.
- Searches are paged (the 1000-objects limit of AD), with time limits on every operation.

## What a Windows Server 2025 controller changes

| Change | Effect on otp | What to do |
|---|---|---|
| LDAP signing required | A simple bind over **plain LDAP** is refused (result code 8, *strongerAuthRequired*). otp says it plainly (1.0.267): "the domain controller wants a signed or encrypted connection ... reach the directory by LDAPS or STARTTLS". | *Reached by*: LDAPS or STARTTLS. |
| TLS 1.0/1.1 off | None - otp uses TLS 1.2/1.3. | Keep "Take old, weak certificates" off. |
| A new certificate on every new controller | None, as long as otp trusts the **authority** (the company's root, an intermediate), not one controller's own certificate. | In *Certificate authority*: the company's root CA - or leave it empty and add the root to the system's trusted roots. |
| The name in the certificate | A server given by its **IP address** fails the name check unless the new certificate carries that address too (it usually does not). The directory's card and the security check say so (1.0.267). | Give the servers by name (FQDN), e.g. `dc1.example.local`. |
| One controller away while it is replaced | The next one in the list answers. | List all three controllers. |
| Channel binding, RC4, NTLMv1, SMB1 | None (otp uses none of them). Backups to SMB use SMB2 or newer (`client min protocol=SMB2`), signing as the server asks, SMB3 encryption on by default. | - |

## Checklist

Before the first controller is replaced:

1. *Settings → Directories*: every directory **LDAPS** (or STARTTLS), the certificate **checked**,
   "Take old, weak certificates" **off**.
2. Its servers: **all** controllers, **by name**. The card warns of a server given by address
   (1.0.267), the security check too.
3. *Certificate authority*: the company's root (or intermediate) - not a controller's own
   certificate. Or empty, with the root in the system's trusted roots.
4. *Check it* on the card: it tries each server.

After each controller is replaced:

1. *Check it* on the directory's card - every server, the new one too, must answer over TLS with
   its certificate accepted.
2. *Look a name up* for a person.
3. A test sign-in through the VPN (RADIUS).
4. Events / the log: no "LDAP signing", "certificate", "TLS ... did not start" for the new
   controller. Only then the next one.

On the server: `otp --directory-test NAME` does the same as *Check it*, `otp --directories` lists them with the same warnings.
