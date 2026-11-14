# 1.0.277: the Kerberos card laid out as in acme (its switches in it, chips, headings, Copy); the certificate card alike.
S277 = {
    'On - not ready': 'Zapnuto – není připraveno',
    'A keytab is in': 'Keytab je vložený',
    'No keytab yet': 'Zatím bez keytabu',
    'no keytab': 'bez keytabu',
    'none to write': 'není co zapsat',
    'Authorities put in': 'Autority vloženy',
    'No authority yet': 'Zatím bez autority',
    'no - a button under the form': 'ne – tlačítko pod formulářem',
    'not offered - only Windows or a certificate': 'nenabízí se – jen Windows nebo certifikát',
    'cmd.exe on a domain controller': 'cmd.exe na řadiči domény',
    'Signing in with Windows (Kerberos)': 'Přihlášení přes Windows (Kerberos)',
    'None yet. Make it in AD (below) and put it in here - once, for every node.':
        'Zatím žádný. Vytvořte ho v AD (níže) a vložte ho sem – jednou, pro všechny nody.',
    'A browser on a computer in the domain signs its person in to these pages without a password: it sends a Kerberos ticket for the name it opened, checked here against the keytab of that name. Only accounts of the directory chosen above get in, with the role of their groups - and the second step, when it is on, is asked after it just the same. NTLM is never taken. Off, nothing of it is offered.':
        'Prohlížeč na počítači v doméně přihlásí svého člověka do těchto stránek bez hesla: pošle tiket Kerbera pro otevřený název a ten se tu ověří proti keytabu toho názvu. Dostanou se jen účty z adresáře zvoleného výše, s rolí podle jejich skupin – a druhý krok, je-li zapnutý, se po něm žádá stejně. NTLM se nikdy nepřijímá. Vypnuté nic z toho nenabízí.',
    "A certificate of the domain's authority - on a smart card, a YubiKey or in the computer - signs its person in to these pages without a password. nginx asks for it on a port of its own, never on 443: nobody else is ever asked for a certificate. Checked here: the chain to an authority put in below, its dates, a key usage for signing in, not revoked (CRL), and the UPN in it looked up in the directory set above - the role of its groups. The second step, when it is on, is asked after it just the same. Off, nothing of it is offered.":
        'Certifikát autority domény – na čipové kartě, YubiKey nebo v počítači – přihlásí svého člověka do těchto stránek bez hesla. nginx o něj žádá na vlastním portu, nikdy na 443: nikdo jiný se o certifikát nežádá. Tady se ověřuje: řetěz k autoritě vložené níže, platnost, použití klíče pro přihlášení, že není odvolaný (CRL), a UPN v něm se vyhledá v adresáři nastaveném výše – role podle jeho skupin. Druhý krok se, je-li zapnutý, žádá po něm stejně. Vypnuté nic z toho nenabízí.',
    'The browser asks for a ticket of HTTP/<the name in its address bar>. Each name needs its SPN on the service account in AD; one key of that account in the keytab serves them all. Never an address: there is no SPN for one, and Windows then offers NTLM - which is refused.':
        'Prohlížeč žádá tiket pro HTTP/<název v adresním řádku>. Každý název potřebuje své SPN na servisním účtu v AD; jeden klíč toho účtu v keytabu poslouží všem. Nikdy adresa: pro tu SPN není a Windows pak nabídnou NTLM – které se odmítá.',
    "On a domain controller, as a domain administrator: a service account of its own (a normal user, password never expires, AES allowed), the SPN of each name, and the keytab of the first one - the others are served by the same key. Changing the account's password later makes a new key version: make the keytab again.":
        'Na řadiči domény jako administrátor domény: vlastní servisní účet (běžný uživatel, heslo nevyprší, AES povolen), SPN každého názvu a keytab prvního z nich – ostatní obslouží stejný klíč. Pozdější změna hesla účtu vytvoří novou verzi klíče: keytab pak vytvořte znovu.',
    'The way back from "only Windows", as root: otp --set admin_password_off=0 (or Kerberos switched off). More: docs/admin-kerberos.md in the package.':
        'Cesta zpět z „jen Windows“, jako root: otp --set admin_password_off=0 (nebo vypnutý Kerberos). Víc: docs/admin-kerberos.md v balíčku.',
    # the sign-in variants (signin-variants-kit, for otp)
    'The sign-in page': 'Přihlašovací stránka',
    'What the sign-in page offers, with Windows and a certificate side by side: each is a button under the name and password, or is tried by itself when the page opens. Both tried by itself: Windows first - silently - and the certificate only when this computer has no Windows ticket (a computer outside the domain with a smart card). A refusal of either stops there and says why; the form stays unless there is no password at all. After Sign out nothing is tried by itself again in that tab. The same on every node of a cluster and on the VIP address.':
        'Co přihlašovací stránka nabízí, s Windows a certifikátem vedle sebe: každý je tlačítko pod jménem a heslem, nebo se zkusí sám při otevření stránky. Oba zkoušené samy: nejdřív Windows – potichu – a certifikát jen tehdy, když tento počítač nemá tiket Windows (počítač mimo doménu s čipovou kartou). Odmítnutí kteréhokoli tím končí a řekne proč; formulář zůstává, pokud není vypnuté heslo úplně. Po odhlášení se v té záložce už nic samo nezkouší. Stejně na každém nodu clusteru i na adrese VIP.',
    "On: the sign-in page goes to the certificate’s port at once - the browser offers its certificate, the card asks for its PIN - and shows the form only when that did not work. With Windows tried by itself as well, Windows goes first and the certificate only when this computer has no Windows ticket (not in the domain). Off: a button \"Sign in with a certificate\" under the form. Never tried by itself again in a tab after Sign out or after a refusal.":
        'Zapnuto: přihlašovací stránka hned přejde na port certifikátu – prohlížeč nabídne svůj certifikát, karta si řekne o PIN – a formulář ukáže jen tehdy, když to nevyšlo. Když se sám zkouší i Windows, jde Windows první a certifikát jen tehdy, když tento počítač nemá tiket Windows (není v doméně). Vypnuto: tlačítko „Přihlásit certifikátem“ pod formulářem. Po odhlášení nebo po odmítnutí se v té záložce už samo nezkouší.',
    'nginx: listening': 'nginx: naslouchá',
    'nginx: not yet - root puts it in within a minute': 'nginx: zatím ne – root ho nastaví do minuty',
    'yes - tried at once, the form if it did not work': 'ano – zkusí se hned, formulář, když to nevyjde',
    'yes - at once, the form if it did not work': 'ano – hned, formulář, když to nevyjde',
    'tried by itself when the page opens': 'zkusí se sám při otevření stránky',
    'a button': 'tlačítko',
    'a button under the form': 'tlačítko pod formulářem',
    'Windows silently; the certificate when this computer has no Windows ticket': 'Windows potichu; certifikát, když tento počítač nemá tiket Windows',
    'Windows silently': 'Windows potichu',
    "the certificate at once - the browser's chooser, the card's PIN": 'certifikát hned – výběr v prohlížeči, PIN karty',
    'nothing - the person chooses': 'nic – člověk si vybere',
    'Name and password': 'Jméno a heslo',
    'offered': 'nabízí se',
    'Tried by itself when the page opens': 'Samo se zkusí při otevření stránky',
    'After a refusal': 'Po odmítnutí',
    'said why on the page; nothing else tried by itself': 'na stránce řekne proč; nic dalšího se samo nezkouší',
    'After Sign out': 'Po odhlášení',
    'nothing tried by itself in that tab': 'v té záložce se nic samo nezkouší',
    'The second step': 'Druhý krok',
    'asked after every way - a password, Windows, a certificate': 'žádá se po každém způsobu – heslo, Windows, certifikát',
    'The way back from no password at all, as root: otp --set admin_password_off=0.': 'Cesta zpět z režimu bez hesla, jako root: otp --set admin_password_off=0.',
    'the keytab signs everybody in - with no password at all, nobody could sign in without it: switch No password at all off first (or a certificate on)':
        'keytab přihlašuje všechny – bez hesla by se bez něj nikdo nepřihlásil: nejdřív vypněte Vůbec bez hesla (nebo zapněte certifikát)',
    'the last authority signs everybody in - with no password at all, nobody could sign in without it: switch No password at all off first (or Windows on)':
        'poslední autorita přihlašuje všechny – bez hesla by se bez ní nikdo nepřihlásil: nejdřív vypněte Vůbec bez hesla (nebo zapněte Windows)',
    'On: the sign-in page tries Windows at once, silently, and shows the form only when it did not work. A browser that had no ticket (outside the domain, its window of name and password cancelled) is not tried by itself again for 30 days - its button stays, and a sign-in with Windows forgets it; computers in the domain sign in silently as before. Off: a button "Sign in with Windows" under the form. After signing out it is never tried by itself in that tab.':
        'Zapnuto: přihlašovací stránka hned a potichu zkusí Windows a formulář ukáže jen tehdy, když to nevyšlo. Prohlížeč, který tiket neměl (mimo doménu, okno se jménem a heslem zrušené), se 30 dní sám znovu nezkouší – tlačítko zůstává a přihlášení přes Windows to zapomene; počítače v doméně se přihlásí potichu jako dřív. Vypnuto: tlačítko „Přihlásit přes Windows“ pod formulářem. Po odhlášení se v té záložce už nikdy samo nezkouší.',
    'A computer without a Windows ticket': 'Počítač bez tiketu Windows',
    'Windows not tried by itself in that browser for 30 days - its button stays; a sign-in with Windows forgets it':
        'Windows se v tom prohlížeči 30 dní samo nezkouší – tlačítko zůstává; přihlášení přes Windows to zapomene',
}
P277 = {}
