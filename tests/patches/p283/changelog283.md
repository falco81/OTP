## 1.0.283 — 15 November 2026

Added
- **A certificate request made in the browser** - *Values for a certificate request → Make a CSR…*: a second window where what goes in is chosen and added to first - the key (RSA 2048/3072/4096, ECDSA P-256/P-384), the subject (CN of the account, O, OU, L, ST, C), the Subject Alternative Name each ticked and edited (the UPN, the SID as its URL for the strong mapping, the e-mail), what the certificate is for (Client Authentication, Smart Card Logon, Secure Email), the template of AD CS - then the key pair and the PKCS#10 request are made **in this browser** (WebCrypto): the private key never leaves it, nothing of it is sent to the server. The request is copied or downloaded (`.csr`), the key downloaded (`.key`) - by default locked by a passphrase (PKCS#8 encrypted with PBES2: PBKDF2-SHA-256, AES-256-CBC; openssl and Windows read it).

