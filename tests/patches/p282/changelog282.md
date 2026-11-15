## 1.0.282 — 15 November 2026

Added
- **Values for a certificate request** - *Settings → Accounts → Signing in with a certificate*: an account of the directory (its sAMAccountName, `DOMAIN\name` or UPN) looked up, and what its certificate must name to sign in here, each with a button to copy it - the subject (`CN=...`), the UPN of the SAN, the SID as the URL of the SAN (`tag:microsoft.com,2022-09-14:sid:S-1-5-21-...`, the strong mapping of KB5014754), the mail; the whole SAN at once; certreq's `request.inf` and openssl's config to copy or download. It says too whether a certificate of the account would sign anybody in (no UPN, no SID with strong mapping, switched off, locked, no role here). A full administrator only; nothing is changed or kept.
- **Signing in with Windows: the keytab guide's values from AD** - the domain's NetBIOS name and DNS name are read from its crossRef in the forest's configuration (`nETBIOSName`, `dnsRoot`), no longer guessed from the realm: where the NetBIOS name is not the first part of the DNS one (`MERIT_NT` for `merit.cz`) the commands said `MERIT\...` and did not work. The account that already holds the pages' SPNs is named in them; SPNs on more than one account, and a realm that is not AD's, are said. The guide says where its values come from (*from AD*, or *guessed* when the directory did not say), with *Ask AD again*.

Fixed
- **The SID in the SAN's URL** (`tag:microsoft.com,2022-09-14:sid:...`, as Microsoft writes the strong mapping in the SAN) is read too: a certificate naming its SID only there was refused with *strong* mapping ("names no SID").

