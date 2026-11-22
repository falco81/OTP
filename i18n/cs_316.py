# 1.0.316: what was left in English - the certificate sign-in's CDP in the directory and OCSP, the directory's
# reasons for a refusal, and what a database agent puts in.
S316 = {
    'A CRL Distribution Point in the directory (ldap:///CN=...,CN=CDP,CN=Public Key Services,...) is read too - after the http ones - with the connection of the directory set for administrators, never the host written in the address; only a CDP object of the configuration’s Public Key Services, only its CRL. Off: only http.':
        'Čte se i distribuční bod CRL v adresáři (ldap:///CN=...,CN=CDP,CN=Public Key Services,...) – až po těch http – spojením adresáře nastaveného pro administrátory, nikdy ne na hostitele uvedeného v adrese; jen objekt CDP v Public Key Services konfigurace a jen jeho CRL. Vypnuto: jen http.',
    'off: the CRLs alone (as before). first: the OCSP responder (AD CS Online Responder) of each certificate - and of each authority above it but the root - and its CRL when it does not answer. only: OCSP alone - no answer, no sign-in. both: OCSP and the CRL, both must say good. An answer is checked by openssl against the authorities put in and used ten minutes at most.':
        'vypnuto: jen CRL (jako dřív). nejdřív: OCSP respondér (AD CS Online Responder) každého certifikátu – i každé autority nad ním kromě kořenové – a jeho CRL, když neodpoví. jen: samotné OCSP – bez odpovědi žádné přihlášení. obojí: OCSP i CRL, obě musí říct, že je certifikát v pořádku. Odpověď ověří openssl proti vloženým autoritám a platí nejvýš deset minut.',
    'An http address asked for every certificate instead of the one each names (Authority Information Access) - for certificates issued before the responder was there. Empty: each certificate’s own.':
        'Adresa http, na kterou se ptát u každého certifikátu místo té, kterou uvádí on sám (Authority Information Access) – pro certifikáty vydané dřív, než respondér existoval. Prázdné: vlastní adresa každého certifikátu.',
    'the directory had an operations error': 'adresář ohlásil chybu operace',
    'there is no such object under that base': 'pod touto základnou žádný takový objekt není',
    'the distinguished name is not well formed': 'rozlišující jméno (DN) není správně zapsané',
    'that server will not take this kind of authentication': 'tento server takový způsob ověření nepřijímá',
    'the name or the password was not accepted': 'jméno nebo heslo nebylo přijato',
    'that account may not read what was asked for': 'tento účet nesmí číst to, na co se ptal',
    'the server is unwilling to do that (a blank password, or an account that must change it)':
        'server to odmítá udělat (prázdné heslo, nebo účet, který si ho musí změnit)',
    'that account may not sign in at this time of day': 'tento účet se v tuto denní dobu přihlásit nesmí',
    'that account may not sign in from this machine': 'tento účet se z tohoto počítače přihlásit nesmí',
    'the password has expired': 'heslo vypršelo',
    'the directory ran out of room for the groups this account is in': 'adresáři došlo místo pro skupiny, ve kterých tento účet je',
    'the account has expired': 'platnost účtu vypršela',
    'the password must be changed before this account can be used': 'heslo je nutné změnit, než bude možné účet použít',
    'the account is locked out': 'účet je zablokovaný',
    "the database's certificate from otp's authority, ssl on, its renewal": 'certifikát databáze od autority otp, zapnuté ssl, jeho obnova',
    'the link between the databases: certificate, verify-full, pg_hba hostssl': 'spojení mezi databázemi: certifikát, verify-full, pg_hba hostssl',
    'wal_level, listen_addresses, the account, the publication': 'wal_level, listen_addresses, účet, publikace',
    "the database's port opened to the otp nodes and the other server": 'port databáze otevřený uzlům otp a druhému serveru',
    "the database server's own settings and their restart": 'vlastní nastavení databázového serveru a jeho restart',
    "PostgreSQL's log of the replication": 'log replikace PostgreSQL',
    'how busy the database server is': 'jak vytížený je databázový server',
}
P316 = {}
