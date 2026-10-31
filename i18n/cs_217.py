# 1.0.196: ACME - the keys Let's Encrypt takes, both RSA and ECDSA, the profiles.
S217 = {
 "ECDSA P-384": "ECDSA P-384",
 "RSA 3072": "RSA 3072",
 "RSA 4096": "RSA 4096",
 "The profile of the certificate": "Profil certifikátu",
 "the CA’s own (classic at Let’s Encrypt)": "vlastní CA (u Let’s Encrypt classic)",
 "classic - 90 days": "classic – 90 dní",
 "tlsserver - 90 days, for TLS servers only": "tlsserver – 90 dní, jen pro TLS servery",
 "shortlived - 6 days": "shortlived – 6 dní",
 "What the CA makes the certificate as, where it offers profiles (Let’s Encrypt does): shortlived lasts 6 days and is renewed every two or three - no revoking needed if its key is lost. Another CA without profiles: its own.":
  "Jako co CA certifikát vydá, pokud profily nabízí (Let’s Encrypt ano): shortlived platí 6 dní a obnovuje se každé dva až tři – při ztrátě klíče není potřeba ho odvolávat. Jiná CA bez profilů: její vlastní.",
 "the output": "výstup",
}
S217.update({
 "Both: RSA 2048 + ECDSA P-256 (advised)": "Oba: RSA 2048 + ECDSA P-256 (doporučeno)",
 "Both: RSA 4096 + ECDSA P-384": "Oba: RSA 4096 + ECDSA P-384",
 "ECDSA P-256 (ES256)": "ECDSA P-256 (ES256)",
 "ECDSA P-384 (ES384)": "ECDSA P-384 (ES384)",
 "RSA 2048 (RS256)": "RSA 2048 (RS256)",
 "RSA 3072 (RS256)": "RSA 3072 (RS256)",
 "RSA 4096 (RS256)": "RSA 4096 (RS256)",
 "The key of the ACME account": "Klíč účtu ACME",
 "Keys": "Klíče",
 "(a second certificate beside it)": "(druhý certifikát vedle něj)",
 "Let’s Encrypt takes RSA keys of 2048, 3072 or 4096 bits and ECDSA keys on P-256 or P-384. Both - what Let’s Encrypt advises - orders two certificates for the name: RSA served by default, the much smaller ECDSA one to the clients that say they take it.":
  "Let’s Encrypt přijímá klíče RSA o 2048, 3072 nebo 4096 bitech a klíče ECDSA na křivkách P-256 nebo P-384. Oba - jak Let’s Encrypt doporučuje - objedná pro jméno dva certifikáty: RSA se podává standardně, mnohem menší ECDSA klientům, kteří řeknou, že ho umí.",
 "The key the account with the CA signs with - never one of a certificate. RSA 2048, 3072, 4096 or ECDSA P-256, P-384. A change makes a new account at the next order.":
  "Klíč, kterým se podepisuje účet u CA - nikdy ne klíč certifikátu. RSA 2048, 3072, 4096 nebo ECDSA P-256, P-384. Změna při příští objednávce založí nový účet.",
})
P217 = {
 "a second certificate, with a {0} key": "druhý certifikát, s klíčem {0}",
 "{0} + {1} (a second certificate beside it)": "{0} + {1} (druhý certifikát vedle něj)",}
