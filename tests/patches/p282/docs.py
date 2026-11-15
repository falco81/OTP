# 1.0.282 docs/admin-certificate.md: the values of a certificate request - python3 docs.py OUTDIR
import sys
F = sys.argv[1].rstrip('/') + '/docs/admin-certificate.md'
s = open(F).read()
a = '## OCSP and CRLs from the directory'
assert s.count(a) == 1 and 'Values for a certificate request' not in s
s = s.replace(a, '''## Values for a certificate request (1.0.282)

*Settings → Accounts → Signing in with a certificate → Values for a certificate request…* (a full
administrator): an account of the directory set for administrators - `jnovak`, `CORP\\jnovak` or
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

The SID is read from the certificate's SID extension (1.3.6.1.4.1.311.25.2), the SAN's *Other Name* of
it, **or the SAN's URL** `tag:microsoft.com,2022-09-14:sid:...` (1.0.282) - any of them satisfies
*strong*.

''' + a, 1)
open(F, 'w').write(s)
print('docs patched')
