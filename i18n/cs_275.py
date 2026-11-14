# 1.0.275: signing in to the administration with a client certificate (a smart card, a YubiKey).
S275 = {
    # the sign-in page
    'Sign in with a certificate': 'Přihlásit certifikátem',
    'Asking for your certificate…': 'Žádám o váš certifikát…',
    'Signing in here is with a certificate only - no password.': 'Přihlášení je tu jen certifikátem – bez hesla.',
    'Signing in here is with Windows or a certificate only - no password.':
        'Přihlášení je tu jen přes Windows nebo certifikátem – bez hesla.',
    'signing in with a certificate is off': 'přihlášení certifikátem je vypnuté',
    'open the pages by their name': 'otevřete stránky jejich názvem',
    'the sign-in with a certificate was not started from this browser\'s sign-in page - try again':
        'přihlášení certifikátem nezačalo na přihlašovací stránce tohoto prohlížeče – zkuste to znovu',
    'no certificate was sent - none chosen, or the browser has none from the authorities put in here':
        'nebyl poslán žádný certifikát – žádný nebyl vybrán, nebo prohlížeč nemá žádný od zde vložených autorit',
    'no certificate was sent (none chosen, or the browser has none from the authorities put in here)':
        'nebyl poslán žádný certifikát (žádný nebyl vybrán, nebo prohlížeč nemá žádný od zde vložených autorit)',
    'signing in with a certificate needs the directory of the administrators':
        'přihlášení certifikátem potřebuje adresář administrátorů',
    'that is the certificate of an authority, not of a person': 'to je certifikát autority, ne člověka',
    'larger than any certificate of a person': 'větší než jakýkoli certifikát člověka',
    'the certificate is not for signing in (no Client Authentication or Smart Card Logon among its key usages)':
        'certifikát není pro přihlášení (mezi jeho použitími klíče chybí Client Authentication i Smart Card Logon)',
    'no authority is put in on this node yet': 'na tomto uzlu ještě není vložená žádná autorita',
    'the certificate names no CRL over http (CRL Distribution Points) - it cannot be checked for revocation':
        'certifikát neuvádí CRL přes http (CRL Distribution Points) – nejde ověřit, zda není odvolaný',
    'the certificate names no user (no UPN in its Subject Alternative Name)':
        'certifikát neuvádí uživatele (v Subject Alternative Name chybí UPN)',
    'the certificate names no SID of its account (strong mapping, KB5014754) - issued by an AD CS before May 2022, or from an offline template':
        'certifikát neuvádí SID svého účtu (silné mapování, KB5014754) – vydaný AD CS před květnem 2022, nebo z offline šablony',
    'no directory is set for administrators': 'pro administrátory není nastaven adresář',
    'no authority is put in': 'není vložená žádná autorita',
    'no authority is put in - nobody could sign in (nothing saved)': 'není vložená žádná autorita – nikdo by se nepřihlásil (nic neuloženo)',
    'sign in with Windows or a certificate first, then switch the password off - so it is known to work for you (nothing saved)':
        'nejdřív se přihlaste přes Windows nebo certifikátem a pak heslo vypněte – tak je jisté, že vám to funguje (nic neuloženo)',
    'no certificate in it (PEM, DER or PKCS#7 .p7b)': 'není v něm žádný certifikát (PEM, DER nebo PKCS#7 .p7b)',
    'that is more than certificates of authorities are': 'to je víc, než mají certifikáty autorit',
    'there is no such authority': 'taková autorita neexistuje',
    'the authority is taken away': 'autorita je odebrána',
    'every one of them was in already': 'všechny už tu byly',
    'Your certificate': 'Váš certifikát',
    'Back to the pages': 'Zpět na stránky',
    # settings
    'No password at all - only Windows or a certificate': 'Vůbec bez hesla – jen Windows nebo certifikát',
    'Sign administrators in with a certificate (a smart card, a YubiKey)': 'Přihlašovat administrátory certifikátem (čipová karta, YubiKey)',
    'The certificate’s own port': 'Vlastní port certifikátu',
    'Which account a certificate is': 'Kterému účtu certifikát patří',
    'Check that a certificate is not revoked (CRL)': 'Ověřovat, že certifikát není odvolaný (CRL)',
    'On: no field for a password anywhere on these pages - nobody signs in with a password, local accounts neither; only Windows (Kerberos) or a certificate, then the second step when it is on. Switched on only from a sign-in made that way (so it is known to work). Kerberos and certificates both off: passwords are taken again. Locked out: as root, otp --set admin_password_off=0.':
        'Zapnuto: na těchto stránkách není nikde pole pro heslo – nikdo se nepřihlásí heslem, ani místní účty; jen přes Windows (Kerberos) nebo certifikátem, pak druhý krok, je-li zapnutý. Zapnout jde jen z přihlášení takovým způsobem (tak je jisté, že funguje). Kerberos i certifikáty vypnuté: hesla se zase přijímají. Zamčeno: jako root otp --set admin_password_off=0.',
    'A certificate of the domain’s authority - on a smart card, a YubiKey or in the computer - signs its person in without a password: nginx asks for it on a port of its own (below), never on 443. Checked here: the chain to an authority put in below, its dates, a key usage for signing in, not revoked, the UPN in it looked up in the directory above (the role of the groups). The second step, when it is on, is still asked. Off: as until now.':
        'Certifikát autority domény – na čipové kartě, YubiKey nebo v počítači – přihlásí svého člověka bez hesla: nginx o něj žádá na vlastním portu (níže), nikdy na 443. Tady se ověřuje: řetěz k autoritě vložené níže, platnost, použití klíče pro přihlášení, že není odvolaný, a UPN v něm se vyhledá v adresáři výše (role podle skupin). Druhý krok se, je-li zapnutý, žádá i tak. Vypnuto: jako dosud.',
    'Where nginx asks the browser for a certificate (8443: SELinux lets nginx have it already). Opened in the firewall for the administrators’ networks.':
        'Kde nginx žádá prohlížeč o certifikát (8443: SELinux ho nginx už dovoluje). Ve firewallu se otevře pro sítě administrátorů.',
    'compat: the SID an AD CS writes into a certificate since KB5014754 must be the account’s when it is there; strong: it must be there (Microsoft’s full enforcement); upn: the UPN alone.':
        'compat: SID, který AD CS od KB5014754 zapisuje do certifikátu, musí patřit účtu, když tam je; strong: musí tam být (plné vynucení Microsoftu); upn: jen UPN.',
    'The CRL at the certificate’s CRL Distribution Point (http), kept until its next update: no CRL to be had, no sign-in. Off: revocation is not checked - a lost card signs in until its account is switched off in AD.':
        'CRL z CRL Distribution Point certifikátu (http), drží se do další aktualizace: bez CRL žádné přihlášení. Vypnuto: odvolání se neověřuje – ztracená karta přihlašuje, dokud se účet nevypne v AD.',
    # the card
    'Signing in with a certificate': 'Přihlášení certifikátem',
    "A certificate of the domain's authority - on a smart card, a YubiKey or in the computer - signs its person in to these pages without a password. nginx asks for it on a port of its own, never on 443: nobody else is ever asked for a certificate. Checked here: the chain to an authority put in below, its dates, a key usage for signing in, not revoked (CRL), and the UPN in it looked up in the directory set above - the role of its groups. The second step, when it is on, is asked after it just the same. Switched on above (Sign administrators in with a certificate); off, nothing of it is offered.":
        'Certifikát autority domény – na čipové kartě, YubiKey nebo v počítači – přihlásí svého člověka do těchto stránek bez hesla. nginx o něj žádá na vlastním portu, nikdy na 443: nikdo jiný se o certifikát nežádá. Tady se ověřuje: řetěz k autoritě vložené níže, platnost, použití klíče pro přihlášení, že není odvolaný (CRL), a UPN v něm se vyhledá v adresáři nastaveném výše – role podle jeho skupin. Druhý krok se, je-li zapnutý, žádá po něm stejně. Zapíná se výše (Přihlašovat administrátory certifikátem); vypnuté nic z toho nenabízí.',
    'The port': 'Port',
    'nginx asks for a certificate there, and nowhere else': 'tam nginx žádá o certifikát, a nikde jinde',
    'Which account': 'Který účet',
    "the UPN; the SID in it must be the account's when it is there": 'UPN; SID v něm musí patřit účtu, když tam je',
    'the UPN and the SID in it, which must be there': 'UPN a SID v něm, který tam musí být',
    'the UPN alone': 'jen UPN',
    'Revocation': 'Odvolání',
    'checked - the CRL of each certificate, no CRL no sign-in': 'ověřuje se – CRL každého certifikátu, bez CRL žádné přihlášení',
    'not checked': 'neověřuje se',
    'offered beside it': 'nabízí se vedle',
    'not offered': 'nenabízí se',
    'The authorities': 'Autority',
    'Authority': 'Autorita',
    'Issued by': 'Vydal',
    'Valid to': 'Platí do',
    'SHA-256': 'SHA-256',
    'Take this authority away': 'Odebrat tuto autoritu',
    'Take this authority away?': 'Odebrat tuto autoritu?',
    'Certificates issued by it no longer sign anybody in.': 'Certifikáty od ní už nikoho nepřihlásí.',
    "None yet. Put in the certificate of the authority that issues the people's certificates and of the one above it (the root) - PEM, DER or a .p7b. Once: every node of a cluster gets them.":
        'Zatím žádná. Vložte certifikát autority, která vydává certifikáty lidem, a té nad ní (kořenové) – PEM, DER nebo .p7b. Jednou: dostane je každý uzel clusteru.',
    'Put in an authority…': 'Vložit autoritu…',
    'Try my certificate': 'Zkusit můj certifikát',
    "Opens the certificate's port in a new tab: the browser asks which certificate, and the page says who it would sign in, and as what. Nothing is signed in or changed.":
        'Otevře port certifikátu v nové záložce: prohlížeč se zeptá, který certifikát, a stránka řekne, koho by přihlásil a s jakou rolí. Nic se nepřihlásí ani nezmění.',
    'Revocation lists fetched': 'Stažené seznamy odvolaných certifikátů',
    'Address': 'Adresa',
    'State': 'Stav',
    'Fetched': 'Staženo',
    'Next update': 'Další aktualizace',
    'good': 'v pořádku',
    'not had': 'nestaženo',
    'The authorities ': 'Autority ',
    'listening': 'naslouchá',
    "The people's certificates (AD CS)": 'Certifikáty lidí (AD CS)',
    'A template from "Smartcard Logon" (or "User"): Subject Alternative Name built from Active Directory with the User principal name (UPN); key usages Client Authentication and Smart Card Logon.':
        'Šablona z „Smartcard Logon“ (nebo „User“): Subject Alternative Name sestavený z Active Directory s User principal name (UPN); použití klíče Client Authentication a Smart Card Logon.',
    'Since KB5014754 the authority writes the account\'s SID into each certificate it issues from AD: "Which account" compat (the default) checks it, strong requires it.':
        'Od KB5014754 autorita zapisuje SID účtu do každého certifikátu, který vydá z AD: „Který účet“ compat (výchozí) ho ověřuje, strong ho vyžaduje.',
    "A CRL Distribution Point over http in the certificates (the authority's Extensions tab), reachable from the nodes.":
        'CRL Distribution Point přes http v certifikátech (karta Extensions autority), dostupný z uzlů.',
    "A YubiKey (PIV): enrolled from Windows with certreq or the template's smart card enrolment, or with YubiKey Manager (a CSR from slot 9a, signed by the authority). Windows asks for its PIN when the browser offers it.":
        'YubiKey (PIV): zapsaný z Windows přes certreq nebo zápis čipové karty dané šablony, nebo přes YubiKey Manager (CSR ze slotu 9a, podepsaný autoritou). Windows se zeptá na jeho PIN, když ho prohlížeč nabídne.',
    'The browsers and the network': 'Prohlížeče a síť',
    'The button "Sign in with a certificate" opens ': 'Tlačítko „Přihlásit certifikátem“ otevře ',
    "The firewall of each node lets the port in for the administrators' networks - nothing else is served there: ":
        'Firewall každého uzlu port pouští pro sítě administrátorů – nic jiného se tam neobsluhuje: ',
    'Behind a load balancer the port is passed through as TCP - TLS ends on the nodes: ':
        'Za load balancerem se port předává jako TCP – TLS končí na uzlech: ',
    'Edge, Chrome: no setting - a policy can pick the certificate by itself: ':
        'Edge, Chrome: nic se nenastavuje – politika může certifikát vybrat sama: ',
}
P275 = {
    '{0} authority(ies) put in': 'vloženo autorit: {0}',
    'nginx on port {0}': 'nginx na portu {0}',
    'the certificate is not taken: {0}': 'certifikát není přijat: {0}',
    '{0} is not the name of a person': '{0} není jméno člověka',
    'the certificate is of another account: its SID is {0}, {1}\'s is {2}': 'certifikát patří jinému účtu: jeho SID je {0}, SID účtu {1} je {2}',
    'would sign in {0} as {1}': 'přihlásil by {0} jako {1}',
}
