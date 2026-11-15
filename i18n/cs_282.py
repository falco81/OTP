# 1.0.282: the values of a certificate request.
S282 = {
    'Values for a certificate request…': 'Hodnoty pro žádost o certifikát…',
    'Values for a certificate request': 'Hodnoty pro žádost o certifikát',
    "An account of the directory looked up: the subject, the UPN and the SID of the SAN its certificate needs - each to copy, and certreq's and openssl's words for them.":
        'Vyhledá účet v adresáři: subjekt, UPN a SID do SAN, které jeho certifikát potřebuje – každé ke zkopírování, a podklady pro certreq a openssl.',
    'An account of the directory set for administrators: its subject, the UPN and the SID the certificate must name to sign in here - as AD CS writes them since KB5014754 (strong mapping). Nothing is changed or kept.':
        'Účet z adresáře nastaveného pro administrátory: subjekt, UPN a SID, které musí certifikát uvádět, aby se tu přihlásil – tak, jak je AD CS zapisuje od KB5014754 (strong mapping). Nic se nemění ani neukládá.',
    'Find': 'Najít',
    'Asking the directory…': 'Ptám se adresáře…',
    'no role here': 'tady bez role',
    'switched off': 'vypnutý',
    'locked out': 'zamčený',
    'Certificate subject': 'Subjekt certifikátu',
    "the certificate's name": 'jméno certifikátu',
    'Common Name': 'Common Name',
    'Other Name - Principal Name (1.3.6.1.4.1.311.20.2.3)': 'Other Name – Principal Name (1.3.6.1.4.1.311.20.2.3)',
    'the SID - strong mapping (KB5014754)': 'SID – strong mapping (KB5014754)',
    'SAN: e-mail': 'SAN: e-mail',
    'RFC 822 Name - not needed to sign in': 'RFC 822 Name – k přihlášení není potřeba',
    'objectSid of the account': 'objectSid účtu',
    'Account': 'Účet',
    'its place in the directory': 'jeho místo v adresáři',
    'Copy it': 'Zkopírovat',
    'Copy the SAN': 'Zkopírovat SAN',
    'the SAN copied': 'SAN zkopírován',
    'Windows: certreq': 'Windows: certreq',
    'certreq -new request.inf request.req, then certreq -submit -attrib "CertificateTemplate:SmartcardLogon" request.req - on the computer with the card (or the YubiKey); a template whose subject is "Supply in the request".':
        'certreq -new request.inf request.req, pak certreq -submit -attrib "CertificateTemplate:SmartcardLogon" request.req – na počítači s kartou (nebo YubiKey); šablona, jejíž subjekt je „Supply in the request“.',
    'openssl req -new -key the.key -config request.cnf -out request.csr - for a key made outside Windows (a YubiKey with ykman, a CSR of slot 9a).':
        'openssl req -new -key the.key -config request.cnf -out request.csr – pro klíč vytvořený mimo Windows (YubiKey přes ykman, CSR slotu 9a).',
    'which account? its sAMAccountName, DOMAIN\\name or its UPN': 'který účet? jeho sAMAccountName, DOMÉNA\\jméno nebo UPN',
    'no directory is set for administrators (Settings - Accounts)': 'pro administrátory není nastavený žádný adresář (Nastavení – Účty)',
    "the account has no userPrincipalName - a certificate names its account by it; nobody signs in with one of this account":
        'účet nemá userPrincipalName – certifikát svůj účet uvádí právě jím; s certifikátem tohoto účtu se nikdo nepřihlásí',
    "the directory did not say the account's SID (objectSid) - strong mapping needs it":
        'adresář neřekl SID účtu (objectSid) – strong mapping ho potřebuje',
    'none of the groups given a role here holds the account - a certificate of it is taken, and nobody is signed in':
        'účet není v žádné skupině, která tu má roli – jeho certifikát se přijme, ale nikdo se nepřihlásí',
}
P282 = {
    '{0} copied': '{0} zkopírováno',
    'Download {0}': 'Stáhnout {0}',
    'the directory {0} has nobody called {1}': 'adresář {0} nemá nikoho jménem {1}',
    'more than one account answers to {0}': 'jménu {0} odpovídá víc účtů',
    'the account may not sign in now: {0}': 'účet se teď přihlásit nesmí: {0}',
}

S282.update({
    'from AD': 'z AD',
    'guessed': 'odhadnuto',
    'asking AD…': 'ptám se AD…',
    'Ask AD again': 'Zeptat se AD znovu',
})
P282.update({
    'the domain {0} (NetBIOS), {1} (DNS) - as {2} says them': 'doména {0} (NetBIOS), {1} (DNS) – jak je říká {2}',
    "the directory did not say the domain's names ({0}) - the NetBIOS name below is the first part of the realm: check it (set /a USERDOMAIN on a computer of the domain)":
        'adresář neřekl jména domény ({0}) – NetBIOS jméno níže je první část realmu: ověřte ho (echo %USERDOMAIN% na počítači v doméně)',
    'The realm used here is {0}, and AD says its domain is {1} - set the realm (admin_kerberos_realm) to it.':
        'Tady se používá realm {0}, ale AD říká, že jeho doména je {1} – nastavte realm (admin_kerberos_realm) na ni.',
    'The SPNs are on more than one account ({0}) - one key serves them all only when one account holds them: setspn -D them from the others.':
        'SPN jsou na víc účtech ({0}) – jeden klíč obslouží všechny jen tehdy, když je drží jeden účet: odeberte je z ostatních (setspn -D).',
    'AD has the SPN {0} on {1} already - that account is the one below.': 'AD už má SPN {0} na účtu {1} – níže je použit tento účet.',
    'AD has the SPNs {0} on {1} already - that account is the one below.': 'AD už má SPN {0} na účtu {1} – níže je použit tento účet.',
})
