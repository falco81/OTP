import sys
F = sys.argv[1].rstrip('/') + '/docs/admin-certificate.md'
s = open(F).read()
a = 'The SID is read from the certificate\'s SID extension'
assert s.count(a) == 1 and 'Make a CSR' not in s
s = s.replace(a, '''**Make a CSR…** (1.0.283) makes the request itself, in the browser: a second window chooses the key (RSA
2048/3072/4096, ECDSA P-256/P-384), the subject (CN, O, OU, L, ST, C), which of the UPN, the SID's URL and
the e-mail go into the SAN (each to be edited), the extended key usages (Client Authentication, Smart Card
Logon, Secure Email) and the template of AD CS. The key pair is made by the browser (WebCrypto) and never
leaves it - nothing of it reaches the server; the request (`.csr`, PEM) and the private key (`.key`,
PKCS#8, by default locked by a passphrase: PBES2 with PBKDF2-SHA-256 and AES-256-CBC) are downloaded.
For a smart card or a YubiKey's PIV slot the key is made on the card instead (certreq's `request.inf` with
the Smart Card Key Storage Provider, or `ykman piv keys generate` and `ykman piv certificates request`).

''' + a, 1)
open(F, 'w').write(s)
print('docs patched')
