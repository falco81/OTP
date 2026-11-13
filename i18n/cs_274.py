# 1.0.274: signing in to the administration pages with Windows (Kerberos), and with Windows only.
S274 = {
    'Passwords are switched off here - only Windows': 'Hesla jsou tu vypnutá – jen Windows',
    'Signing in here is with Windows only - no password. People of the directory get their account at their first sign-in with Windows, with the role of their groups; an account of this server, with a password, could not sign in.':
        'Přihlášení je tu jen přes Windows – bez hesla. Lidé z adresáře dostanou účet při prvním přihlášení přes Windows, s rolí podle svých skupin; účet tohoto serveru s heslem by se nepřihlásil.',
    # the sign-in page
    'Sign in with Windows': 'Přihlásit přes Windows',
    'Signing in with Windows…': 'Přihlašuji přes Windows…',
    'or': 'nebo',
    'Signing in here is with Windows only - no password.': 'Přihlášení je tu jen přes Windows – bez hesla.',
    "the browser sent no Kerberos ticket - is this computer in the domain, and is this name among the browser's intranet sites?":
        'prohlížeč neposlal žádný tiket Kerbera – je tento počítač v doméně a je tento název mezi intranetovými weby prohlížeče?',
    'signing in with Kerberos is off': 'přihlášení přes Kerberos je vypnuté',
    'signing in with a password is switched off here - sign in with Windows':
        'přihlášení heslem je tu vypnuté – přihlaste se přes Windows',
    'signing in with Kerberos needs the directory of the administrators':
        'přihlášení přes Kerberos potřebuje adresář administrátorů',
    'the browser sent no ticket': 'prohlížeč neposlal žádný tiket',
    'the ticket is larger than any Kerberos ticket': 'tiket je větší než jakýkoli tiket Kerbera',
    'the ticket is not base64': 'tiket není v base64',
    'this node has no keytab yet': 'tento uzel ještě nemá keytab',
    'the browser wants more than one round - that is not Kerberos (NTLM?)':
        'prohlížeč chce víc než jedno kolo – to není Kerberos (NTLM?)',
    'the browser used a mechanism that is not Kerberos 5': 'prohlížeč použil mechanismus, který není Kerberos 5',
    'the ticket has no name that can be read': 'tiket nemá čitelné jméno',
    'the browser offered NTLM, which is never taken here - only Kerberos (is the name it opened in the keytab, and is the computer in the domain?)':
        'prohlížeč nabídl NTLM, které se tu nikdy nepřijímá – jen Kerberos (je otevřený název v keytabu a je počítač v doméně?)',
    'this ticket was used already (a replay?)': 'tento tiket už byl použit (přehrání?)',
    'the realm whose people may sign in is not known - set Kerberos realm':
        'není známá realm, jejíž lidé se smí přihlásit – nastavte Realm Kerbera',
    'sign in with Windows first, then switch the password off - so it is known to work for you (nothing saved)':
        'nejdřív se přihlaste přes Windows a pak heslo vypněte – tak je jisté, že vám to funguje (nic neuloženo)',
    'no keytab is put in - nobody could sign in (nothing saved)': 'není vložený žádný keytab – nikdo by se nepřihlásil (nic neuloženo)',
    # settings
    'Sign administrators in with Windows (Kerberos)': 'Přihlašovat administrátory přes Windows (Kerberos)',
    '...by itself when the sign-in page opens': '...samo při otevření přihlašovací stránky',
    'Kerberos realm': 'Realm Kerbera',
    '...and no password at all - only Windows': '...a vůbec bez hesla – jen Windows',
    'A browser on a computer in the domain signs its person in without a password: it sends a Kerberos ticket for the name it opened, checked against the keytab put in below. Only accounts of the directory above, with the role of their groups; the second step, when it is on, is still asked. NTLM is never taken. Off: as until now.':
        'Prohlížeč na počítači v doméně přihlásí svého člověka bez hesla: pošle tiket Kerbera pro otevřený název a ten se ověří proti keytabu vloženému níže. Jen účty z adresáře výše, s rolí podle jejich skupin; druhý krok se, když je zapnutý, žádá i tak. NTLM se nikdy nepřijímá. Vypnuto: jako dosud.',
    'On: the sign-in page tries Kerberos at once, and shows the form only when it did not work. Off: a button "Sign in with Windows" beside the form. After signing out it is never tried by itself in that tab.':
        'Zapnuto: přihlašovací stránka hned zkusí Kerberos a formulář ukáže, jen když to nevyšlo. Vypnuto: tlačítko „Přihlásit přes Windows“ u formuláře. Po odhlášení se v té záložce samo nezkouší.',
    'The realm whose people may sign in, in capitals (CORP.EXAMPLE). Empty: taken from the base DN of the directory above (DC=corp,DC=example).':
        'Realm, jejíž lidé se smí přihlásit, velkými písmeny (CORP.EXAMPLE). Prázdné: vezme se z base DN adresáře výše (DC=corp,DC=example).',
    'On: the sign-in page offers no name and password - nobody signs in with a password, local accounts neither; only Windows (Kerberos), then the second step when it is on. Switched on only from a sign-in made with Windows (so it is known to work). Kerberos off: passwords are taken again. Locked out: as root, otp --set admin_password_off=0.':
        'Zapnuto: přihlašovací stránka nenabízí jméno a heslo – nikdo se nepřihlásí heslem, ani místní účty; jen přes Windows (Kerberos), pak druhý krok, je-li zapnutý. Zapnout jde jen z přihlášení přes Windows (tak je jisté, že funguje). Kerberos vypnutý: hesla se zase přijímají. Zamčeno: jako root otp --set admin_password_off=0.',
    # the card
    'Signing in with Windows (Kerberos)': 'Přihlášení přes Windows (Kerberos)',
    'Realm': 'Realm',
    'Directory': 'Adresář',
    'Second step after it': 'Druhý krok po něm',
    'By itself on the sign-in page': 'Samo na přihlašovací stránce',
    'A password on the sign-in page': 'Heslo na přihlašovací stránce',
    'not offered - only Windows': 'nenabízí se – jen Windows',
    'offered beside it': 'nabízí se vedle',
    'as set': 'jak je nastaveno',
    "from the directory's base DN": 'z base DN adresáře',
    'none - set Sign administrators in against the directory': 'žádný – nastavte Přihlašovat administrátory proti adresáři',
    'asked': 'žádá se',
    'off (A second step when signing in to these pages)': 'vypnuto (Druhý krok při přihlášení do těchto stránek)',
    'no - a button beside the form': 'ne – tlačítko u formuláře',
    'never taken': 'nikdy se nepřijímá',
    'Not ready yet: ': 'Ještě není připraveno: ',
    'The keytab': 'Keytab',
    'Put in ': 'Vložen ',
    ' by ': ' – ',
    ' - kept sealed in the database; its keys are never shown.': ' – uložen zapečetěný v databázi; jeho klíče se nikdy neukazují.',
    'Principal': 'Principal',
    'Key version': 'Verze klíče',
    'Kind of key': 'Druh klíče',
    'weak': 'slabý',
    'None yet. Make it in the domain (below) and put it in here - once: every node of a cluster gets it.':
        'Zatím žádný. Vytvořte ho v doméně (níže) a vložte sem – jednou: dostane ho každý uzel clusteru.',
    'Put in a keytab…': 'Vložit keytab…',
    'Put in another keytab…': 'Vložit jiný keytab…',
    'Take the keytab away': 'Odebrat keytab',
    'Take the keytab away?': 'Odebrat keytab?',
    'Nobody signs in with Windows any more until another one is put in. Signing in with a password is not touched.':
        'Přes Windows se už nikdo nepřihlásí, dokud se nevloží jiný. Přihlášení heslem se to netýká.',
    'Take it away': 'Odebrat',
    "Try my browser's ticket": 'Zkusit tiket mého prohlížeče',
    'Asks this browser for its Kerberos ticket and says who it would sign in, and as what. Nothing is signed in or changed.':
        'Požádá tento prohlížeč o jeho tiket Kerbera a řekne, koho by přihlásil a s jakou rolí. Nic se nepřihlásí ani nezmění.',
    'would sign in': 'přihlásil by',
    'would not sign in': 'nepřihlásil by',
    'no ticket': 'bez tiketu',
    'then the second step, as after a password': 'pak druhý krok, jako po hesle',
    'The names the pages are opened by': 'Názvy, pod kterými se stránky otevírají',
    'The browser asks for a ticket of HTTP/<the name in its address bar>. Each name needs its SPN on the service account in AD; one key of that account in the keytab serves them all.':
        'Prohlížeč žádá tiket pro HTTP/<název v adresním řádku>. Každý název potřebuje své SPN na servisním účtu v AD; jeden klíč toho účtu v keytabu poslouží všem.',
    'Name': 'Název',
    'Of': 'Čí',
    'SPN': 'SPN',
    'In the keytab': 'V keytabu',
    'by name': 'jménem',
    "by the account's key": 'klíčem účtu',
    'Each node': 'Každý uzel',
    'Node': 'Uzel',
    'Heard from': 'Ozývá se',
    'Kerberos library': 'Knihovna Kerbera',
    'Trouble': 'Potíž',
    'written': 'zapsán',
    'not yet': 'zatím ne',
    'missing': 'chybí',
    'there': 'je',
    'Making the keytab in AD': 'Vytvoření keytabu v AD',
    'On a domain controller, as a domain administrator: a service account of its own (a normal user, password never expires, AES allowed), the SPN of each name, and the keytab of the first one - the others are served by the same key.':
        'Na řadiči domény jako administrátor domény: vlastní servisní účet (běžný uživatel, heslo nevyprší, AES povolen), SPN každého názvu a keytab prvního z nich – ostatní obslouží stejný klíč.',
    'Telling the browsers': 'Nastavení prohlížečů',
    'Edge and Chrome (Windows, by group policy): ': 'Edge a Chrome (Windows, skupinovou politikou): ',
    '…or Internet Options → Security → Local intranet → Sites: ': '…nebo Možnosti Internetu → Zabezpečení → Místní intranet → Weby: ',
    'Firefox (policy or about:config): ': 'Firefox (politikou nebo about:config): ',
    'NTLM: ': 'NTLM: ',
    'nothing to set here - it is refused whatever the browser offers': 'tady se nic nenastavuje – odmítne se, ať prohlížeč nabídne cokoli',
    'A browser on a computer in the domain signs its person in to these pages without a password: it sends a Kerberos ticket for the name it opened, checked here against the keytab of that name. Only accounts of the directory set above get in, with the role of their groups - and the second step, when it is on, is asked after it just the same. NTLM is never taken. Switched on above (Sign administrators in with Windows (Kerberos)); off, nothing of it is offered.':
        'Prohlížeč na počítači v doméně přihlásí svého člověka do těchto stránek bez hesla: pošle tiket Kerbera pro otevřený název a ten se tu ověří proti keytabu toho názvu. Dostanou se jen účty z adresáře nastaveného výše, s rolí podle jejich skupin – a druhý krok, je-li zapnutý, se po něm žádá stejně. NTLM se nikdy nepřijímá. Zapíná se výše (Přihlašovat administrátory přes Windows (Kerberos)); vypnuté nic z toho nenabízí.',
    'that is larger than any keytab of a web service': 'to je větší než jakýkoli keytab webové služby',
    'the keytab is taken away': 'keytab je odebrán',
    'the keytab of Kerberos is taken away': 'keytab Kerbera je odebrán',
    'the file is empty': 'soubor je prázdný',
    'that is larger than any keytab of a web service (64 kB)': 'to je větší než jakýkoli keytab webové služby (64 kB)',
    'that is not a keytab (it starts 0x05 0x02)': 'to není keytab (začíná 0x05 0x02)',
    'the keytab ends in the middle of an entry': 'keytab končí uprostřed záznamu',
    'the keytab holds no key': 'keytab neobsahuje žádný klíč',
    'every key in it is of a weak kind (DES, RC4) - make it with -crypto AES256-SHA1 (ktpass) and allow AES for the account':
        'každý klíč v něm je slabého druhu (DES, RC4) – vytvořte ho s -crypto AES256-SHA1 (ktpass) a povolte účtu AES',
    'it holds no key of a web service (HTTP/name@REALM) - the browser asks for HTTP/<the name it opened>':
        'neobsahuje klíč webové služby (HTTP/název@REALM) – prohlížeč žádá HTTP/<otevřený název>',
    'no directory is set for administrators (Sign administrators in against the directory)':
        'pro administrátory není nastaven adresář (Přihlašovat administrátory proti adresáři)',
    'no keytab is put in': 'není vložený keytab',
    'the realm is not known - set it (Kerberos realm)': 'realm není známá – nastavte ji (Realm Kerbera)',
    "the keytab in the database does not open with this node's key (secrets.key)":
        'keytab v databázi nejde otevřít klíčem tohoto uzlu (secrets.key)',
}
P274 = {
    'the keytab is put in: {0}': 'keytab je vložen: {0}',
    'the ticket was not taken: {0}': 'tiket nebyl přijat: {0}',
    '{0} is not the name of a person': '{0} není jméno člověka',
    '{0} is known, and none of the groups given a role here holds it': '{0} je známý, ale žádná skupina s rolí tady ho neobsahuje',
    'the directory does not let {0} in: {1}': 'adresář {0} nepustí: {1}',
    'the account {0} is switched off here': 'účet {0} je tu vypnutý',
}
