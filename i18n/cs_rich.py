R = {
"A copy of the database once a day, into <code>/var/lib/otp/backups</code>, with the key that opens the tokens beside it.":
"Jednou denně kopie databáze do <code>/var/lib/otp/backups</code>, s klíčem, který otevírá tokeny, hned vedle.",
"A message longer than this is cut, with <code>...TRUNCATED</code> at the end. rsyslog cuts at 2048 bytes over UDP unless <code>$MaxMessageSize</code> says more on both machines.":
"Delší zpráva se zkrátí a na konec se připíše <code>...TRUNCATED</code>. rsyslog přes UDP ořezává na 2048 bajtech, pokud <code>$MaxMessageSize</code> na obou strojích neříká víc.",
"A name typed without an @ gets this added before it is looked up: <code>novak</code> becomes <code>novak@example.cz</code>. Empty: the name has to be typed whole.":
"Ke jménu napsanému bez @ se před vyhledáním připojí toto: z <code>novak</code> se stane <code>novak@example.cz</code>. Prázdné: jméno se musí napsat celé.",
"One line under the sign-in boxes saying what to type, such as <code>login@example.cz</code>.":
"Jeden řádek pod přihlašovacími poli, co se má psát, například <code>login@example.cz</code>.",
"Send every check of a code and every RADIUS packet to isemon, as syslog, in the very shape a totpcgi token server and its FreeRADIUS write - so isemon reads it with what it already has (<i>Settings → The OTP logs</i>, with <i>RADIUS detail</i> switched on).":
"Posílat každou kontrolu kódu a každý RADIUS paket do isemonu jako syslog, přesně v podobě, v jaké je píše tokenový server totpcgi a jeho FreeRADIUS – takže isemon je čte tím, co už má (<i>Nastavení → OTP logy</i>, se zapnutým <i>RADIUS detail</i>).",
"The RADIUS packet behind every check - the person’s own address, the device, the tunnel group - as <code>radius-detail</code> lines. isemon puts them beside the check of the code.":
"RADIUS paket za každou kontrolou – adresa člověka, zařízení, tunnel group – jako řádky <code>radius-detail</code>. isemon je zobrazí vedle kontroly kódu.",
"The account name under it. <code>{user}</code> is the whole name as it was enrolled (<code>novak@example.cz</code>), <code>{name}</code> the part before the @.":
"Název účtu pod ním. <code>{user}</code> je celé jméno, jak bylo registrováno (<code>novak@example.cz</code>), <code>{name}</code> část před @.",
"The address the RADIUS server listens on. <code>0.0.0.0</code> is every IPv4 address this machine has; <code>::</code> every IPv6 one as well. Changed, the server starts listening on the new one at once.":
"Adresa, na které RADIUS server naslouchá. <code>0.0.0.0</code> jsou všechny IPv4 adresy tohoto stroje; <code>::</code> navíc i všechny IPv6. Po změně začne server ihned naslouchat na nové.",
"The directory (by its name under <i>Active Directory</i>) the administration pages sign people in against. Empty: only the accounts made here. Whoever signs in from it gets the role of the first group below they are in, and nobody in none of them gets in.":
"Adresář (podle názvu v sekci <i>Active Directory</i>), vůči kterému se přihlašuje do administrace. Prázdné: jen účty založené zde. Kdo se z něj přihlásí, dostane roli první skupiny níže, ve které je; kdo není v žádné, nepřihlásí se.",
"The host name on every line, which is the folder isemon’s rsyslog files them under: <code>/var/log/remote/&lt;this&gt;/totp.cgi.log</code>. isemon looks in <code>/var/log/remote/otp</code> unless told otherwise, so <code>otp</code> needs nothing changed there. Empty: this machine’s own short name.":
"Název hostitele na každém řádku – podle něj je rsyslog isemonu ukládá do složky <code>/var/log/remote/&lt;this&gt;/totp.cgi.log</code>. isemon hledá v <code>/var/log/remote/otp</code>, pokud mu není řečeno jinak, takže <code>otp</code> tam nepotřebuje žádnou změnu. Prázdné: vlastní krátké jméno tohoto stroje.",
"The port on 127.0.0.1 the web pages ask this daemon on. It has to be the same in <code>otp-api.php</code>.":
"Port na 127.0.0.1, na kterém se webové stránky ptají tohoto démona. Musí být stejný i v <code>otp-api.php</code>.",
"The very same lines go into <code>/var/log/otp/totp.cgi.log</code> and <code>/var/log/otp/radius-detail.log</code> as well, whether or not they are sent. Something on this machine can then forward them, and they are there to read when the network is not.":
"Úplně stejné řádky jdou i do <code>/var/log/otp/totp.cgi.log</code> a <code>/var/log/otp/radius-detail.log</code>, ať se odesílají, nebo ne. Něco na tomto stroji je pak může přeposlat a jsou k přečtení, i když síť není.",
"This account may not change the settings. A full administrator can change that under <i>Accounts</i>.":
"Tento účet nesmí měnit nastavení. Plný administrátor to může změnit v sekci <i>Účty</i>.",
"This daemon’s own events as well (a token made, a setting changed), as <code>otp</code> lines. isemon does not read those; they are for whatever else collects the syslog.":
"I vlastní události démona (vytvořený token, změněné nastavení), jako řádky <code>otp</code>. isemon je nečte; jsou pro cokoli jiného, co sbírá syslog.",
"What follows the @, such as example.cz. <code>*</code> takes every name no other realm does; empty takes names written without a realm.":
"Co následuje za @, například example.cz. <code>*</code> bere každé jméno, které nebere žádný jiný realm; prázdné bere jména napsaná bez realmu.",
"What goes back to the VPN with every Access-Accept: <code>Class = VPN</code>, <code>ASA-Group-Policy = GP_FULL</code>, <code>Session-Timeout = 43200</code>. Known: Reply-Message, Class, Filter-Id, Session-Timeout, Idle-Timeout, Service-Type, Framed-IP-Address, Framed-IP-Netmask, Framed-Pool, Acct-Interim-Interval, Tunnel-Type, Tunnel-Medium-Type, Tunnel-Private-Group-Id, Cisco-AVPair, ASA-Group-Policy, ASA-Tunnel-Group-Lock.":
"Co se vrací do VPN s každým Access-Accept: <code>Class = VPN</code>, <code>ASA-Group-Policy = GP_FULL</code>, <code>Session-Timeout = 43200</code>. Známé: Reply-Message, Class, Filter-Id, Session-Timeout, Idle-Timeout, Service-Type, Framed-IP-Address, Framed-IP-Netmask, Framed-Pool, Acct-Interim-Interval, Tunnel-Type, Tunnel-Medium-Type, Tunnel-Private-Group-Id, Cisco-AVPair, ASA-Group-Policy, ASA-Tunnel-Group-Lock.",
"When, as <code>HH:MM</code> on this machine’s clock.":
"Kdy, jako <code>HH:MM</code> podle hodin tohoto stroje.",
"Where to send them: <code>host</code>, <code>host:port</code>, and <code>/udp</code> or <code>/tcp</code> after it - <code>10.1.2.3:514/tcp</code>. Several, separated by commas. UDP is the default; TCP does not lose a line when the network does.":
"Kam je posílat: <code>host</code>, <code>host:port</code> a za tím <code>/udp</code> nebo <code>/tcp</code> – <code>10.1.2.3:514/tcp</code>. Více cílů oddělte čárkami. Výchozí je UDP; TCP neztratí řádek, ani když vypadne síť.",
"Whether <code>Novak@example.cz</code> and <code>novak@example.cz</code> are one token. Active Directory does not care, and neither should this, unless something else forces it to.":
"Zda jsou <code>Novak@example.cz</code> a <code>novak@example.cz</code> jeden token. Active Directory to nerozlišuje a nemělo by ani tohle, pokud to nevynucuje něco jiného.",
"Who may enrol a token. <b>The realm’s group filter</b> is the same test the VPN applies, so nobody can enrol a token they could never use.":
"Kdo se smí registrovat. <b>Skupinový filtr realmu</b> je tentýž test, jaký použije VPN, takže nikdo si nezaregistruje token, který by nikdy nemohl použít.",
"Who may open these pages. <b>full admin</b> may change everything; <b>token admin</b> may look at everything and look after people's tokens; <b>read only</b> may look and change nothing.":
"Kdo smí otevřít tyto stránky. <b>plný admin</b> smí měnit vše; <b>správce tokenů</b> smí vidět vše a starat se o tokeny lidí; <b>jen pro čtení</b> smí se dívat a nic neměnit.",
"With <i>members of the groups named below</i>: the groups, by name (<code>VPN_USERS</code>) or by whole DN, separated by semicolons or new lines.":
"Při volbě <i>členové níže uvedených skupin</i>: skupiny jménem (<code>VPN_USERS</code>) nebo celým DN, oddělené středníky nebo novými řádky.",
"Write everything into <code>/var/log/otp/otp.log</code>. Loud: for finding something out, not for leaving on.":
"Zapisovat vše do <code>/var/log/otp/otp.log</code>. Upovídané: na hledání problému, ne na trvalý provoz.",
"<b>Install an authenticator application on your phone</b> - Google Authenticator, Microsoft Authenticator, or any other that reads a QR code.":
"<b>Nainstalujte si do telefonu ověřovací aplikaci</b> – Google Authenticator, Microsoft Authenticator nebo jinou, která umí číst QR kód.",
"<b>Press Make my token below</b> - a QR code appears.":
"<b>Stiskněte níže Vytvořit můj token</b> – objeví se QR kód.",
"<b>In the application, add an account and scan the QR code</b> - it starts showing codes at once.":
"<b>V aplikaci přidejte účet a naskenujte QR kód</b> – hned začne ukazovat kódy.",
"<b>Type the code it shows here</b> - and the token is ready for the VPN.":
"<b>Zadejte sem kód, který ukazuje</b> – a token je připraven pro VPN.",
}
S_EXTRA = {
"isemon reads a token server from two files under /var/log/remote/<host>/: totp.cgi.log and radius-detail.log. Its rsyslog needs a rule for both program names - deploy/isemon/11-otp.conf in this package, copied to /etc/rsyslog.d/ there - and in isemon: Settings → The OTP logs switched on, the folder of this host in it, and RADIUS detail switched on.":
"isemon čte tokenový server ze dvou souborů v /var/log/remote/<host>/: totp.cgi.log a radius-detail.log. Jeho rsyslog potřebuje pravidlo pro oba názvy programů – deploy/isemon/11-otp.conf z tohoto balíčku, zkopírovaný tam do /etc/rsyslog.d/ – a v isemonu: zapnuté Nastavení → OTP logy, v nich složka tohoto hostitele, a zapnutý RADIUS detail.",
}
S_EXTRA.update({
"replace a token that is here already": "nahradit token, který tu už je",
"takes every name no other realm does; empty takes names written without a realm.": "bere každé jméno, které nebere žádný jiný realm; prázdné bere jména napsaná bez realmu.",
"plain LDAP (389) - a test only": "prosté LDAP (389) – jen pro test",
"sign-ins": "přihlášení", "sign-ins only": "jen přihlášení",
"the enrolment pages": "stránky registrace", "these pages": "tyto stránky",
"the built-in default is": "vestavěná výchozí hodnota je", "the built-in default": "vestavěná výchozí hodnota",
"small letters - Novak and novak are one person": "malá písmena – Novak a novak jsou jeden člověk",
"tokens": "tokeny", "packets": "pakety",
"unless told otherwise, so": ", pokud mu není řečeno jinak, takže",
"the part before the @, as sAMAccountName": "část před @, jako sAMAccountName",
"otp answers RADIUS itself - no FreeRADIUS - on the ports below. A request from an address that is not one of the clients is never answered.": "otp odpovídá na RADIUS sám – žádný FreeRADIUS – na portech níže. Na požadavek z adresy, která není klientem, se nikdy neodpoví.",
"waiting for a code": "čeká na kód",
"plain LDAP, 389": "prosté LDAP, 389",
"the directory password alone": "samotné heslo z adresáře",
"this account may not have a token here - ask the administrator": "tento účet tu nesmí mít token – obraťte se na administrátora",
"with a password kept here": "s heslem uloženým zde",
"says more on both machines.": "na obou strojích neříká víc.",
"the directory password, then the code": "heslo z adresáře, za ním kód",
"the code alone": "samotný kód",
"right": "správně", "wrong": "chybně", "there": "tam",
"the password is the code from the phone": "heslem je kód z telefonu",
"the whole name, as userPrincipalName": "celé jméno, jako userPrincipalName",
"the name or the password is not right": "jméno nebo heslo není správné",
"straight into the decision, as from a client": "rovnou do rozhodování, jako od klienta",
"the part before the @.": "část před @.",
"switched on).": "zapnutý).",
"otp stopped": "otp zastaven",
"SHA-256": "SHA-256",
"command line": "příkazová řádka",
})
P_EXTRA = {
"· running: {0}": "· běží: {0}",
"{0} could not be reached: {1}": "{0} není dostupný: {1}",
"the client adds {0} to a name without a realm": "klient přidá {0} ke jménu bez realmu",
"the account {0} was made on the command line, as {1}": "účet {0} byl založen na příkazové řádce jako {1}",
"the password of {0} was set on the command line": "heslo uživatele {0} bylo nastaveno na příkazové řádce",
"{0} may not enrol a token: in none of the groups": "{0} se nesmí registrovat: není v žádné ze skupin",
"saved on these pages (by {0}, {1})": "uloženo na těchto stránkách ({0}, {1})",
"by {0}": "kdo: {0}",
"the whole name: {0}": "celé jméno: {0}",
"the part before the @: {0}": "část před @: {0}",
"{0} min ago": "před {0} min",
"{0} s ago": "před {0} s",
"the built-in default is {0}": "vestavěná výchozí hodnota je {0}",
}
P_EXTRA.update({
"last {0} ago": "naposledy před {0}",
"{0} (a test by {1})": "{0} (test – {1})",
"{0} in 6 hours": "{0} za 6 hodin", "{0} in 24 hours": "{0} za 24 hodin", "{0} in 3 days": "{0} za 3 dny",
"{0} in a week": "{0} za týden", "{0} in a month": "{0} za měsíc",
})
S_EXTRA.update({
"One-time passwords": "Jednorázová hesla",
"Administration": "Administrace",
"nobody can enrol here yet: no realm with a directory is set up. Administrators sign in at /admin/":
"tady se zatím nikdo nemůže registrovat: není nastaven žádný realm s adresářem. Administrátoři se přihlašují na /admin/",
"The heading on every enrolment page and the title of the browser tab. Empty: One-time passwords, in the language of the page.":
"Nadpis každé stránky registrace a titulek karty prohlížeče. Prázdné: Jednorázová hesla, v jazyce stránky.",
})
S_EXTRA.update({
"a token can only be replaced by an administrator here": "token tu může nahradit jen administrátor",
"enrolling a token here is switched off": "registrace tokenu je tu vypnutá",
"not signed in, or the sign-in has run out": "nejste přihlášeni, nebo přihlášení vypršelo",
"that account is switched off": "ten účet je vypnutý",
"that account may no longer sign in": "ten účet se už nesmí přihlásit",
"that is the last full administrator who can sign in": "to je poslední plný administrátor, který se může přihlásit",
"the directory cannot be reached": "adresář není dostupný",
"the directory cannot be reached just now": "adresář teď není dostupný",
"the directory of this realm is not set up": "adresář tohoto realmu není nastaven",
"the password is not right": "heslo není správné",
"the password you have now is not right": "současné heslo není správné",
"the window is -1 (the setting) or 0 to 20 steps": "okno je -1 (podle nastavení) nebo 0 až 20 kroků",
"there is a token already; it can be replaced with a code from it": "token už existuje; lze ho nahradit kódem z něj",
"there is no such request": "takový požadavek neexistuje",
"which token?": "který token?",
"this account signs in with its directory password, which is changed in the directory": "tento účet se přihlašuje heslem z adresáře, které se mění v adresáři",
"there is no client for 127.0.0.1 to send the test from: add one (the installer makes \"localhost\"), or give the secret": "není klient pro 127.0.0.1, ze kterého poslat test: přidejte ho (installer vytváří „localhost“), nebo zadejte heslo",
"no such client": "takový klient neexistuje",
})
P_EXTRA.update({
"the code from the old token was not taken: {0}": "kód ze starého tokenu nebyl přijat: {0}",
"the directory knows {0}, and none of the groups given a role here holds them": "adresář zná {0}, ale není v žádné ze skupin, které tu mají roli",
"there is no account called {0}": "účet {0} neexistuje",
"there is no directory called {0} (switched on)": "adresář {0} neexistuje (zapnutý)",
"there is no token for {0}": "pro {0} neexistuje token",
"too many wrong passwords from {0}: try again in {1}": "příliš mnoho chybných hesel z {0}: zkuste to znovu za {1}",
})
S_EXTRA.update({
# accounts / AD groups
"The groups, and what each one may do": "Skupiny a co která smí",
"Choose the directory in Sign administrators in against the directory above, then press Find the groups and pick them out of the directory rather than typing a distinguished name by hand — that is how a role ends up pointing at a group that does not exist, and nobody finds out until the first person cannot sign in.":
"Nahoře v „Přihlašovat administrátory vůči adresáři“ zvolte adresář, pak stiskněte Najít skupiny a vyberte je z adresáře, místo abyste DN psali ručně — tak totiž role skončí u skupiny, která neexistuje, a nikdo to nezjistí, dokud se první člověk nepřihlásí.",
"part of a group's name (empty: all)": "část názvu skupiny (prázdné: všechny)",
"part of a group’s name (empty: all)": "část názvu skupiny (prázdné: všechny)",
"Find the groups": "Najít skupiny",
"Ask the directory what groups there are. Nothing is changed; it only reads.": "Zeptat se adresáře, jaké skupiny má. Nic se nemění; jen se čte.",
"Try a sign-in…": "Zkusit přihlášení…", "Try a sign-in": "Zkusit přihlášení",
"Try one person's sign-in from here, so you find out it works before you sign out.": "Vyzkoušet přihlášení jednoho člověka odsud, abyste věděli, že funguje, dřív než se odhlásíte.",
"Full admin": "Plný admin", "Token admin": "Správce tokenů", "Read only": "Jen pro čtení",
"Group": "Skupina", "What it is for": "K čemu je", "narrow this list…": "zúžit seznam…",
"The name they would type": "Jméno, které by zadal", "Their password": "Jeho heslo",
"novak, novak@example.cz or EXAMPLE\\novak": "novak, novak@example.cz nebo EXAMPLE\\novak",
"Try it": "Vyzkoušet", "They are": "Je to", "Role here": "Role zde", "In the directory": "V adresáři", "Asked": "Dotázán",
"Groups the directory gave back:": "Skupiny, které adresář vrátil:",
"none - they cannot sign in": "žádná – nepřihlásí se",
"Nothing is signed in and no session is made. This asks the directory the same question a real sign-in asks, and shows the whole answer - including which groups came back and what role they earn. It uses the settings as they are saved.":
"Nikdo se nepřihlásí a nevznikne žádná relace. Adresáři se položí stejná otázka jako při skutečném přihlášení a ukáže se celá odpověď – i které skupiny se vrátily a jakou roli dávají. Použije se nastavení, jak je uložené.",
"That is not a fault: a name the directory has never heard of is looked for in the local accounts instead.": "To není chyba: jméno, které adresář nezná, se hledá místo toho v místních účtech.",
"taken out — save to keep it": "vyjmuto — uložte, aby to platilo", "put in — save to keep it": "přidáno — uložte, aby to platilo",
"the settings are not drawn yet": "nastavení ještě není vykreslené",
"choose the directory first - \"Sign administrators in against the directory\" above": "nejdřív zvolte adresář – „Přihlašovat administrátory vůči adresáři“ nahoře",
"Lets in": "Pouští",
"The directory has no groups under that base matching that.": "Adresář pod touto bází nemá žádné odpovídající skupiny.",
"The directory has no groups under that base matching that - or the base is not where they live.": "Adresář pod touto bází nemá žádné odpovídající skupiny – nebo nejsou v této bázi.",
"Back": "Zpět", "Next": "Další",
"no directory signs administrators in yet: choose one in \"Sign administrators in against the directory\" and save": "zatím žádný adresář nepřihlašuje administrátory: zvolte ho v „Přihlašovat administrátory vůči adresáři“ a uložte",
# certificate
"The certificate authority": "Certifikační autorita",
"Needed only when the directory is reached over TLS (LDAPS or StartTLS) and the domain controllers' certificates were signed by your own authority. Paste it, or read it from the .crt / .pem file, and press Import it.":
"Potřeba jen tehdy, když se k adresáři přistupuje přes TLS (LDAPS nebo StartTLS) a certifikáty řadičů domény podepsala vaše vlastní autorita. Vložte ho, nebo ho načtěte ze souboru .crt / .pem, a stiskněte Importovat.",
"Import it": "Importovat", "Read a file…": "Načíst soubor…",
"Read the certificate and keep it. It is checked for being a certificate at all before it is stored, and what it is gets shown above.": "Načíst certifikát a uložit ho. Před uložením se ověří, že je to vůbec certifikát, a co je zač, se ukáže nahoře.",
"Pick a .crt or .pem file instead of pasting it.": "Vybrat soubor .crt nebo .pem místo vkládání.",
"Take the stored authority away. The domain controllers' certificates then have to be signed by one this machine already trusts.": "Odebrat uloženou autoritu. Certifikáty řadičů domény pak musí být podepsané autoritou, které tento stroj už věří.",
"For the directory": "Pro adresář", "none imported": "nic není importováno", "imported": "importováno",
"It is": "Je to", "Signed by": "Podepsal", "Good from": "Platí od", "Good until": "Platí do", "Certificates in it": "Certifikátů v něm",
"itself (a root)": "sám sebe (kořenový)", "unnamed": "bez názvu", "stored, but could not be read": "uložen, ale nelze ho přečíst",
"paste the certificate first, or read it from a file": "nejdřív vložte certifikát, nebo ho načtěte ze souboru",
"Change it": "Změnit",
"Open it: switch it off, new recovery codes, try a code, the note": "Otevřít: vypnout, nové záložní kódy, vyzkoušet kód, poznámka",
# tokens / codes / requests
"Show the QR code and key": "Zobrazit QR kód a klíč", "Show the waiting one": "Zobrazit čekající", "Show it": "Zobrazit",
"Whoever has this QR code or key can make the codes of this token, as its owner can. Show it only to its owner; that you looked is written down as an event.":
"Kdo má tento QR kód nebo klíč, umí vytvářet kódy tohoto tokenu stejně jako jeho majitel. Ukažte ho jen majiteli; že jste se podívali, se zapíše jako událost.",
"Administrators may show a token's QR code and key": "Administrátoři smí zobrazit QR kód a klíč tokenu",
"A full administrator may open a token and show its QR code and key - for somebody whose phone cannot scan the page, or to set the same token up again. Whoever has the key can make the codes, so every look is written down as an event. Off: nobody sees a key after it is made.":
"Plný administrátor smí otevřít token a zobrazit jeho QR kód a klíč – pro někoho, jehož telefon stránku nenaskenuje, nebo pro opětovné nastavení stejného tokenu. Kdo má klíč, umí vytvářet kódy, proto se každé zobrazení zapíše jako událost. Vypnuto: klíč po vytvoření už nikdo neuvidí.",
"Its token": "Jeho token", "Its requests": "Jeho požadavky", "Forget this line": "Zapomenout tento řádek",
"Forget this request": "Zapomenout tento požadavek", "Forget these…": "Zapomenout tyto…", "Forget these lines": "Zapomenout tyto řádky",
"Forget these requests": "Zapomenout tyto požadavky", "Forget them": "Zapomenout", "Forget it": "Zapomenout",
"Take every line the filters above match out of the log. Written down as an event.": "Vyjmout z logu každý řádek, který odpovídá filtrům nahoře. Zapíše se jako událost.",
"Take every request the filters above match out of the log. Written down as an event.": "Vyjmout z logu každý požadavek, který odpovídá filtrům nahoře. Zapíše se jako událost.",
"It is taken out of the log of codes here. What was sent to isemon stays there.": "Vyjme se z logu kódů zde. Co bylo odesláno do isemonu, tam zůstane.",
"It is taken out of the RADIUS log here. What was sent to isemon stays there.": "Vyjme se z RADIUS logu zde. Co bylo odesláno do isemonu, tam zůstane.",
"Make a token": "Vytvořit token",
"It is not a code of this token. If the application shows several accounts of this name, an older one is answering - type the code of the newest, or take the old one out of the application.":
"Není to kód tohoto tokenu. Pokud aplikace ukazuje víc účtů tohoto jména, odpovídá starší z nich – zadejte kód nejnovějšího, nebo starý z aplikace odeberte.",
# database
"Which one it is": "Která to je",
"The settings above say which database to open and how to reach it, and they are the only settings kept in the config file (/etc/otp/config.json) rather than in the database - a database cannot hold the address of itself.":
"Nastavení nahoře říká, kterou databázi otevřít a jak se k ní dostat, a jako jediná se ukládají do konfiguračního souboru (/etc/otp/config.json), ne do databáze – databáze nemůže držet vlastní adresu.",
"Changing the setting moves nothing. The order is: fill the address in, try it, set it up if the database and the account are not there yet, carry everything across, and only then start using it. Until that last step this installation carries on exactly as it is, and what is in it is never touched by any of this.":
"Změna nastavení nic nepřesune. Pořadí je: vyplnit adresu, vyzkoušet, nastavit, pokud databáze a účet ještě neexistují, přenést všechno, a teprve pak začít používat. Až do posledního kroku tato instalace běží přesně jako dosud a toho, co v ní je, se nic z toho nedotkne.",
"Set it up…": "Nastavit…", "Carry everything across…": "Přenést všechno…", "Carry everything across": "Přenést všechno",
"Carry it across": "Přenést", "Empty it…": "Vyprázdnit…", "Start using it…": "Začít používat…", "Start using it": "Začít používat",
"Reach that server with the address above, exactly as the daemon would, and say what answered. Nothing is saved and nothing is written.": "Spojit se se serverem na adrese nahoře přesně jako démon a říct, co odpovědělo. Nic se neukládá a nic nezapisuje.",
"Make the database and the account on that server, with rights on that one database and no other, and a password made here and shown once. It asks for an administrator of that server, uses it for this one connection and stores it nowhere.":
"Vytvořit na tom serveru databázi a účet s právy jen na tuto databázi a s heslem vytvořeným zde a ukázaným jednou. Žádá administrátora toho serveru, použije ho pro toto jediné spojení a nikam ho neuloží.",
"Copy everything that is here into that database: every token, request, setting and account. What is here is left exactly as it is.": "Zkopírovat všechno odsud do té databáze: každý token, požadavek, nastavení a účet. Co je zde, zůstane přesně, jak je.",
"Throw away what is in the OTHER database, so that a move can be tried again. Never the one in use.": "Zahodit obsah té DRUHÉ databáze, aby šel přesun zkusit znovu. Nikdy ne té používané.",
"Start using it. This writes the address into the config file and starts the daemon again on it; nothing in either database is touched, and coming back is the same steps the other way.":
"Začít ji používat. Zapíše adresu do konfiguračního souboru a spustí démona znovu nad ní; v žádné z databází se nic nezmění a návrat je stejný postup opačně.",
"Once everything is in the other database and it is the one in use, the one it came from is just a spare copy. Going the other way is these same steps with the file chosen instead - which is what makes it safe to try a server at all.":
"Jakmile je všechno v druhé databázi a ta se používá, je ta původní jen náhradní kopií. Cesta zpět je tentýž postup se zvoleným souborem – a právě proto je bezpečné server vůbec zkusit.",
"The database server’s own settings": "Vlastní nastavení databázového serveru",
"A database server is installed with settings for a machine of any size, which is to say for a small one. This reads what the machine the server runs on has - its memory, its processors, its disk - works the settings out for it, shows them beside what is there now, and puts them in when you say so.":
"Databázový server se instaluje s nastavením pro stroj libovolné velikosti, tedy pro malý. Tohle zjistí, co má stroj, na kterém server běží – paměť, procesory, disk – spočítá pro něj nastavení, ukáže je vedle současného a nastaví je, až řeknete.",
"Changing them takes an account that may: this program’s own where it has that right, otherwise an administrator of that server, asked for in the popup, used for that one request and stored nowhere.":
"Ke změně je potřeba účet, který smí: vlastní účet tohoto programu, má-li to právo, jinak administrátor toho serveru, zadaný v okně, použitý pro tento jediný požadavek a nikam neuložený.",
"Tune it for this machine…": "Vyladit pro tento stroj…", "Put back as it was…": "Vrátit, jak to bylo…", "Put back as it was": "Vrátit, jak to bylo",
"Read what the machine has, work the settings out and show them beside what is there now. Nothing is changed until you say so.": "Zjistit, co stroj má, spočítat nastavení a ukázat je vedle současného. Nic se nezmění, dokud neřeknete.",
"Put every setting this page changed back to what it was before.": "Vrátit každé nastavení, které tato stránka změnila, na původní hodnotu.",
"What is in it": "Co v ní je",
"Every row in each table. Deleting rows frees room inside the database, which the engine uses again; only Give the disk back hands it to the operating system.":
"Každý řádek v každé tabulce. Smazání řádků uvolní místo uvnitř databáze, které stroj znovu použije; operačnímu systému ho vrátí jen Vrátit místo na disku.",
"Make a copy now": "Vytvořit kopii teď", "Check it": "Zkontrolovat", "Optimise it": "Optimalizovat",
"Apply what is kept, now": "Uplatnit uchovávání teď", "Forget records older than…": "Zapomenout záznamy starší než…",
"Give the disk back": "Vrátit místo na disku", "Give it back": "Vrátit",
"Copy the database as it is into the backups folder on this machine, now, rather than waiting for tonight.": "Zkopírovat databázi, jak je, do složky záloh na tomto stroji hned teď, místo čekání na noc.",
"Ask the database to read itself through and say whether anything in it is broken - SQLite's integrity check, MariaDB's CHECK TABLE, on PostgreSQL every table read through.":
"Nechat databázi, ať se celá přečte a řekne, zda je v ní něco poškozené – integrity check v SQLite, CHECK TABLE v MariaDB, v PostgreSQL přečtení každé tabulky.",
"Fresh statistics for the query planner - ANALYZE, on all three. Quick, and nothing is held shut.": "Čerstvé statistiky pro plánovač dotazů – ANALYZE, u všech tří. Rychlé a nic se nezamyká.",
"Throw away exactly what the keep-for numbers already say is too old. It happens by itself every hour; this is the same thing, now.": "Zahodit přesně to, co je podle nastavení uchovávání už příliš staré. Děje se samo každou hodinu; tohle je totéž hned.",
"Forget the RADIUS requests and the checks of a code older than an age you choose here, whatever the keep-for numbers say. Tokens, accounts and settings are not touched.":
"Zapomenout RADIUS požadavky a kontroly kódu starší, než zde zvolíte, bez ohledu na nastavení uchovávání. Tokeny, účty a nastavení zůstanou.",
"Give the space back to the DISK: SQLite's VACUUM, MariaDB's OPTIMIZE TABLE, PostgreSQL's VACUUM FULL. Each holds a table shut while it works and needs room for a second copy of the biggest one. Worth doing after throwing a lot away, and not otherwise.":
"Vrátit místo DISKU: VACUUM v SQLite, OPTIMIZE TABLE v MariaDB, VACUUM FULL v PostgreSQL. Každý po dobu práce zamkne tabulku a potřebuje místo na druhou kopii té největší. Vyplatí se po zahození velkého množství dat, jinak ne.",
"Table": "Tabulka", "Rows": "Řádky", "Copies": "Kopie", "Where": "Kde",
"A copy goes back into any of the three engines. Put back on the server: otp --restore /var/lib/otp/backups/FILE --yes.": "Kopie jde zpět do kteréhokoli ze tří databázových strojů. Obnova na serveru: otp --restore /var/lib/otp/backups/SOUBOR --yes.",
"It answered": "Odpověděla", "It may write": "Smí zapisovat", "otp’s tables in it": "Tabulky otp v ní", "none yet": "zatím žádné",
"this is the database in use": "tohle je používaná databáze", "Trouble": "Potíž", "yes": "ano",
"it answered": "odpověděla", "it did not answer": "neodpověděla",
"An administrator of that server": "Administrátor toho serveru", "Its password": "Jeho heslo", "Go on": "Pokračovat",
"Used for this one request; kept nowhere.": "Použije se pro tento jediný požadavek; nikam se neukládá.",
"Set it up": "Nastavit", "Empty the other database": "Vyprázdnit druhou databázi", "Empty it": "Vyprázdnit",
"Nothing in it is broken": "Nic v ní není poškozené", "Something in it is broken": "Něco v ní je poškozené",
"The RADIUS requests and the checks of a code older than this are deleted now, whatever the keep-for numbers say. Tokens, accounts, settings and events are not touched.":
"RADIUS požadavky a kontroly kódu starší než toto se smažou hned, bez ohledu na nastavení uchovávání. Tokeny, účty, nastavení a události zůstanou.",
"Older than (days)": "Starší než (dny)",
"Each table is rebuilt and held shut while it is - the RADIUS server waits for its own table meanwhile. It needs room for a second copy of the biggest table.":
"Každá tabulka se přestaví a po tu dobu je zamčená – RADIUS server mezitím na svou tabulku čeká. Potřebuje místo na druhou kopii největší tabulky.",
"Tune it for this machine": "Vyladit pro tento stroj",
"The database server runs on this machine: what it has was read here.": "Databázový server běží na tomto stroji: co má, se zjistilo zde.",
"The database server runs on another machine: say what it has.": "Databázový server běží na jiném stroji: uveďte, co má.",
"Memory (GB)": "Paměť (GB)", "Processors": "Procesory", "Its disk": "Jeho disk", "spinning disk": "rotační disk",
"Setting": "Nastavení", "Now": "Teď", "For this machine": "Pro tento stroj", "Why": "Proč",
"An administrator of that server (empty: otp’s own account)": "Administrátor toho serveru (prázdné: vlastní účet otp)",
"Work it out again": "Spočítat znovu", "Put them in": "Nastavit",
"the file on this machine needs no setting up": "soubor na tomto stroji žádné nastavení nepotřebuje",
"a quarter of the memory: the server’s own cache": "čtvrtina paměti: vlastní cache serveru",
"how much the planner may assume is cached": "kolik smí plánovač předpokládat v cache",
"for VACUUM and building indexes": "pro VACUUM a stavbu indexů", "for each sort and hash": "pro každé řazení a hash",
"the write-ahead log’s buffer": "buffer write-ahead logu", "fewer checkpoints under load": "méně checkpointů pod zátěží",
"kept between checkpoints": "drženo mezi checkpointy", "checkpoints spread out": "rozložené checkpointy",
"an SSD reads anywhere as fast": "SSD čte kdekoli stejně rychle", "reads the disk takes at once": "čtení, která disk zvládne naráz",
"one per processor": "jeden na procesor", "parallel queries over every processor": "paralelní dotazy přes všechny procesory",
"per query": "na dotaz", "a log large enough for a busy hour": "log dost velký na rušnou hodinu",
"no second copy in the system’s cache": "žádná druhá kopie v cache systému", "what the disk takes per second": "co disk zvládne za sekundu",
"...at most": "...nejvýše", "an SSD has no neighbours": "SSD nemá sousedy", "in-memory temporary tables": "dočasné tabulky v paměti",
"...the same": "...totéž", "tables kept open": "otevřené tabulky",
"English": "English",
})
P_EXTRA.update({
"in use: {0}": "používá se: {0}",
"{0} row(s)": "{0} {0:řádek|řádky|řádků}",
"{0} dead row(s)": "{0} {0:mrtvý řádek|mrtvé řádky|mrtvých řádků}",
"{0} free inside": "{0} volných uvnitř",
"{0} group(s). Press a role beside one to put it in that role; press it again to take it out. More than one group may hold a role, and somebody in several gets the highest.":
"{0} {0:skupina|skupiny|skupin}. Stiskem role vedle skupiny ji do role přidáte; dalším stiskem ji vyjmete. Roli může mít víc skupin a kdo je v několika, dostane nejvyšší.",
"{0} group(s) found": "{0} {0:skupina nalezena|skupiny nalezeny|skupin nalezeno}",
"{0} of {1}": "{0} z {1}", "{0} shown": "{0} zobrazeno", "page {0} of {1}": "stránka {0} z {1}",
"Put {0} in this role, or take it out of it. It is a change like any other on this page — nothing happens until you save.":
"Přidat {0} do této role, nebo ji z ní vyjmout. Je to změna jako každá jiná na této stránce — nic se nestane, dokud neuložíte.",
"Show the key of {0}": "Zobrazit klíč tokenu {0}",
"Take the certificate authority of {0} away": "Odebrat certifikační autoritu adresáře {0}",
"Nothing is imported for {0}, so the domain controllers’ certificates have to be signed by an authority this machine already trusts.":
"Pro {0} není nic importováno, takže certifikáty řadičů domény musí podepsat autorita, které tento stroj už věří.",
"Nothing is imported for {0}, so the domain controllers’ certificates have to be signed by an authority this machine already trusts - and plain LDAP checks no certificate at all.":
"Pro {0} není nic importováno, takže certifikáty řadičů domény musí podepsat autorita, které tento stroj už věří – a prosté LDAP žádný certifikát nekontroluje.",
"The certificate authority: {0}, good until {1}. It is imported, read from a file or taken away under The certificate authority, below the list of directories.":
"Certifikační autorita: {0}, platí do {1}. Importuje se, načítá ze souboru nebo odebírá v části Certifikační autorita pod seznamem adresářů.",
"the certificate authority of {0} is {1}": "certifikační autorita adresáře {0} je {1}",
"the certificate authority of {0} is taken away": "certifikační autorita adresáře {0} je odebrána",
"read {0} - press Import it": "načteno {0} – stiskněte Importovat",
"{0} line(s) taken out": "{0} {0:řádek vyjmut|řádky vyjmuty|řádků vyjmuto}",
"{0} request(s) taken out": "{0} {0:požadavek vyjmut|požadavky vyjmuty|požadavků vyjmuto}",
"Forget request {0}": "Zapomenout požadavek {0}",
"{0} took {1} line(s) out of the log of codes": "{0} vyjmul {1} řádků z logu kódů",
"{0} took {1} request(s) out of the RADIUS log": "{0} vyjmul {1} požadavků z RADIUS logu",
"{0} looked at the key of the token of {1}": "{0} zobrazil klíč tokenu uživatele {1}",
"{0} looked at the key of the waiting token of {1}": "{0} zobrazil klíč čekajícího tokenu uživatele {1}",
"{0} checked the database: {1}": "{0} zkontroloval databázi: {1}",
"{0} set up {1} at {2}": "{0} nastavil {1} na {2}",
"{0} emptied {1} at {2}": "{0} vyprázdnil {1} na {2}",
"{0} gave the disk back: {1} -> {2}": "{0} vrátil místo na disku: {1} -> {2}",
"everything was carried into {0} ({1}), by {2}": "vše bylo přeneseno do {0} ({1}), provedl {2}",
"{0} switched the database to {1} at {2}; the daemon starts again on it": "{0} přepnul databázi na {1} na {2}; démon se nad ní znovu spouští",
"{0} forgot the requests and checks older than {1} day(s): {2}": "{0} zapomněl požadavky a kontroly starší než {1} dní: {2}",
"{0} at {1} is ready": "{0} na {1} je připravena",
"the daemon starts again on {0} in a moment": "démon se za chvíli znovu spustí nad {0}",
"emptied: {0} table(s) thrown away": "vyprázdněno: {0} {0:tabulka zahozena|tabulky zahozeny|tabulek zahozeno}",
"forgotten: {0} request(s), {1} check(s) of a code": "zapomenuto: {0} požadavků, {1} kontrol kódu",
"the disk is given back: {0} → {1}": "místo na disku vráceno: {0} → {1}",
"done: {0} → {1}": "hotovo: {0} → {1}",
"It is this token's code, but from {0} s ago: the clock of the phone is wrong - set it to the network's time.": "Je to kód tohoto tokenu, ale z doby před {0} s: hodiny telefonu jdou špatně – nastavte je podle času ze sítě.",
"It is this token's code, but from {0} s ahead: the clock of the phone is wrong - set it to the network's time.": "Je to kód tohoto tokenu, ale o {0} s napřed: hodiny telefonu jdou špatně – nastavte je podle času ze sítě.",
})
S_EXTRA.update({
"a code to try": "kód k vyzkoušení",
"0 is the engine's usual one: 3306 or 5432.": "0 je obvyklý port stroje: 3306 nebo 5432.",
"0 is the engine’s usual one: 3306 or 5432.": "0 je obvyklý port stroje: 3306 nebo 5432.",
"the file on this machine (SQLite)": "soubor na tomto stroji (SQLite)",
})
P_EXTRA.update({"the file on this machine (SQLite) · {0}": "soubor na tomto stroji (SQLite) · {0}"})
S_EXTRA.update({
"What the directory says about one person: who they are, whether the account is switched off or has run out, and every group they are in, those inside groups as well.":
"Co adresář ví o jednom člověku: kdo to je, zda je účet vypnutý nebo mu vypršela platnost, a všechny jeho skupiny, včetně vnořených.",
"Expires": "Platnost do", "Who": "Kdo", "novak@example.cz or novak": "novak@example.cz nebo novak",
"A name as the VPN sends it, or a short one.": "Jméno, jak ho posílá VPN, nebo krátké.",
"Look it up": "Vyhledat", "type a name first": "nejdřív zadejte jméno",
"They choose their own at the next sign-in.": "Při příštím přihlášení si zvolí vlastní.",
"Again": "Znovu", "Set it": "Nastavit", "the two are not the same": "hesla se neshodují",
})
P_EXTRA.update({"Look a name up in {0}": "Vyhledat jméno v {0}", "A new password for {0}": "Nové heslo pro {0}"})
S_EXTRA.update({
"Edit": "Upravit", "Edit: the QR code, the recovery codes, switching it off, the note": "Upravit: QR kód, záložní kódy, vypnutí, poznámka",
"In the directory: who it is, whether the account is switched off, its groups": "V adresáři: kdo to je, zda je účet vypnutý, jeho skupiny",
"In the directory": "V adresáři",
"Every line, whatever its age - the whole log emptied": "Všechny řádky bez ohledu na stáří – vyprázdnit celý log",
"Lines that go back to the VPN with every Access-Accept, Name = value.": "Řádky, které se vrací do VPN s každým Access-Accept, Název = hodnota.",
"Log": "Log", "The log": "Log",
"One log of everything: every RADIUS request this server was asked, with what the token said about its code, and every code checked anywhere else - on the enrolment pages, in a test, on the command line. Newest first. Click a row for every attribute that came, the answer, and each step of the decision. Old lines go by themselves after the days under Settings - The database, which is also where they can be cleared.":
"Jeden log všeho: každý RADIUS požadavek, který server dostal, s tím, co token řekl o jeho kódu, a každý kód zkontrolovaný jinde – na stránkách registrace, v testu, na příkazové řádce. Nejnovější první. Klikněte na řádek pro všechny atributy, odpověď a každý krok rozhodnutí. Staré řádky mizí samy po počtu dní v Nastavení – Databáze, kde je lze také vymazat.",
"Every RADIUS request with what the token said about its code, and every code checked anywhere else - the enrolment pages, a test. Click a row for every attribute and every step of the decision.":
"Každý RADIUS požadavek s tím, co token řekl o kódu, a každý kód zkontrolovaný jinde – na stránkách registrace, v testu. Klikněte na řádek pro všechny atributy a kroky rozhodnutí.",
"RADIUS and codes": "RADIUS i kódy", "RADIUS requests only": "jen RADIUS požadavky", "codes outside RADIUS only": "jen kódy mimo RADIUS",
"let in / right": "vpuštěn / správně", "refused / wrong": "odmítnut / chybně",
"Why - what the token said": "Proč – co řekl token", "a test": "test", "enrolment pages": "stránky registrace", "command line": "příkazová řádka",
"right": "správně", "wrong": "chybně",
"Looking the person up": "Vyhledání člověka", "What it takes": "Co bere",
"The names this realm answers for, and what the password is.": "Jména, za která realm odpovídá, a co je heslem.",
"Where the person is found, and what makes the directory refuse them.": "Kde se člověk najde a co způsobí, že ho adresář odmítne.",
"How it is reached": "Jak se k němu připojit", "Reading it": "Čtení",
"The domain controllers, in the order they are asked, and how.": "Řadiče domény v pořadí, v jakém se ptá, a jak.",
"The account it reads with - it needs nothing but to read - and where it looks.": "Účet, kterým čte – nepotřebuje nic než čtení – a kde hledá.",
"No token": "Žádný token", "The phone": "Telefon", "Signing in": "Přihlašování", "The person": "Člověk",
"Show them": "Zobrazit", "New QR code (a new key)": "Nový QR kód (nový klíč)",
"Not kept to be shown again: made by an older version or brought over. Make new ones.": "Nejsou uloženy k opětovnému zobrazení: vytvořila je starší verze nebo byly převzaty. Vytvořte nové.",
"Whether a code is right for this token now. Nothing is used up and nothing is counted.": "Zda je kód pro tento token teď správný. Nic se nespotřebuje a nic se nepočítá.",
"Who the token belongs to.": "Komu token patří.",
"Switched off it refuses every code; the wrong codes in a row pause it.": "Vypnutý odmítne každý kód; chybné kódy za sebou ho pozastaví.",
"A new key is waiting for a code from it; until then the old one works.": "Nový klíč čeká na kód z něj; do té doby funguje starý.",
"Each of them signs in once in place of a code from the phone. Show them only to their owner; that you looked is written down as an event.":
"Každý z nich jednou přihlásí místo kódu z telefonu. Ukažte je jen majiteli; že jste se podívali, se zapíše jako událost.",
"Each works once, in place of a code from the phone. Give them only to their owner.": "Každý platí jednou, místo kódu z telefonu. Dejte je jen majiteli.",
"Each works once, in place of a code from the phone. Give them to their owner - the old ones no longer work.": "Každý platí jednou, místo kódu z telefonu. Dejte je majiteli – staré už neplatí.",
"The ones there are stop working, and new ones are shown.": "Stávající přestanou platit a ukážou se nové.",
"The key of this token cannot be opened: the key file of the database is not the one it was sealed with. Make a new one.":
"Klíč tohoto tokenu nelze otevřít: klíčový soubor databáze není ten, kterým byl zapečetěn. Vytvořte nový.",
"The default realm": "Výchozí realm", "as the default realm": "jako výchozí realm", "none - a name has to be written whole": "žádný – jméno se musí psát celé",
"The realm a name written without one belongs to: novak is taken as novak@ this, on the enrolment pages and in RADIUS requests from a client that adds no realm of its own - and novak@this works as well. Every other realm still needs its @domain. Empty: a name has to be written whole.":
"Realm, do kterého patří jméno napsané bez realmu: novak se bere jako novak@tento, na stránkách registrace i v RADIUS požadavcích od klienta, který nepřidává vlastní realm – a novak@tento funguje také. Každý jiný realm dál potřebuje svou @doménu. Prázdné: jméno se musí psát celé.",
"Import another…": "Importovat jiný…", "Paste or read another certificate, in place of the one there is.": "Vložit nebo načíst jiný certifikát místo současného.",
"no certificate": "bez certifikátu", "Servers, in order": "Servery v pořadí", "by the name": "podle jména",
"by the form of the name (with an @: userPrincipalName)": "podle tvaru jména (se @: userPrincipalName)",
"nobody": "nikdo",
"No directory yet. A realm without one checks the code and nothing else.": "Zatím žádný adresář. Realm bez adresáře kontroluje kód a nic jiného.",
})
S_EXTRA["default - also without @"] = "výchozí – i bez @"
P_EXTRA.update({
"{0} in the directory": "{0} v adresáři",
"{0} has nobody by that name.": "{0} nikoho takového nezná.",
"{0} has no token: they cannot sign in to the VPN until they enrol one on the enrolment pages, or one is made here.": "{0} nemá token: do VPN se nepřihlásí, dokud si ho nezaregistruje na stránkách registrace nebo ho nevytvoříte zde.",
"{0} left. Each works once, in place of a code from the phone.": "Zbývá {0}. Každý platí jednou, místo kódu z telefonu.",
"Show the recovery codes of {0}": "Zobrazit záložní kódy uživatele {0}",
"account does not pass LDAP group filter(s): {0} is in none of {1}": "účet neprošel skupinovým filtrem LDAP: {0} není v žádné z {1}",
"account does not pass LDAP user filter: {0} is not in {1}": "účet neprošel uživatelským filtrem LDAP: {0} není v {1}",
"a member of {0} group(s), none of them one of: {1}": "člen {0} skupin, žádná z nich není: {1}",
"a member of {0} group(s) (nested counted), none of them one of: {1}": "člen {0} skupin (včetně vnořených), žádná z nich není: {1}",
"{0} may not enrol a token: in none of the groups ({1})": "{0} se nesmí registrovat: není v žádné ze skupin ({1})",
"Not in the groups of the realm {0}: may not enrol": "Není ve skupinách realmu {0}: nesmí se registrovat",
"{0} looked at the recovery codes of {1}": "{0} zobrazil záložní kódy uživatele {1}",
"default - also without @": "výchozí – i bez @",
})
S_EXTRA.update({"free": "volný"})
P_EXTRA.update({"used {0}": "použit {0}", "used {0} · {1}": "použit {0} · {1}", "{0} free, {1} used": "{0} volných, {1} použitých",
                "the token server could not decide: {0}": "tokenový server nemohl rozhodnout: {0}"})
