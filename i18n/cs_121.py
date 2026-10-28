S121 = {
# mail settings - what each one says
"How a token’s mail leaves this machine: through your mail server, or straight to the server of each recipient’s domain (its MX record) with no relay - which only works where port 25 may go out and the receiving side trusts this machine (SPF, a reverse DNS name).":
"Jak e-mail s tokenem opustí tento stroj: přes váš poštovní server, nebo rovnou na server domény každého příjemce (jeho MX záznam) bez relaye – to funguje jen tam, kde smí ven port 25 a přijímající strana tomuto stroji věří (SPF, reverzní DNS jméno).",
"The mail server’s name or address: smtp.example.cz, or a relay in your network. Its name is what its certificate is checked against.":
"Jméno nebo adresa poštovního serveru: smtp.example.cz, nebo relay ve vaší síti. Proti tomuto jménu se ověřuje jeho certifikát.",
"0 picks the usual one for the encryption: 587 for STARTTLS, 465 for TLS, 25 for none.":
"0 zvolí obvyklý port podle šifrování: 587 pro STARTTLS, 465 pro TLS, 25 bez šifrování.",
"STARTTLS on 587 is what most servers want; SMTPS on 465 is TLS from the first byte; none sends everything - the password too - in the clear, for a relay inside your own network only.":
"STARTTLS na 587 chce většina serverů; SMTPS na 465 je TLS od prvního bajtu; bez šifrování jde vše – i heslo – otevřeně, jen pro relay uvnitř vaší vlastní sítě.",
"How this machine signs in to the server. None where the relay lets this address send by itself. XOAUTH2 (Microsoft 365, Google): the password is an access token.":
"Jak se tento stroj k serveru přihlašuje. Bez přihlášení tam, kde relay nechá tuto adresu odesílat sám. XOAUTH2 (Microsoft 365, Google): heslo je přístupový token.",
"The account it signs in with - often the whole address.":
"Účet, kterým se přihlašuje – často celá e-mailová adresa.",
"Its password (or the OAuth access token for XOAUTH2). Kept in the database sealed with the key that seals the tokens.":
"Jeho heslo (nebo přístupový token OAuth pro XOAUTH2). Uloženo v databázi zapečetěné stejným klíčem jako tokeny.",
"Off is for a test: a server whose certificate is not checked is one anybody on the path can pretend to be. A certificate signed by your own authority is trusted once that authority is added below.":
"Vypnuto jen pro zkoušku: za server, jehož certifikát se neověřuje, se může vydávat kdokoli na cestě. Certifikát podepsaný vaší vlastní autoritou je důvěryhodný, jakmile tu autoritu přidáte níže.",
"How long to wait for the server to answer.": "Jak dlouho čekat na odpověď serveru.",
"Going direct: the port of the recipients’ servers. It is 25 everywhere; another only to test against a server of your own.":
"Při přímém odesílání: port serverů příjemců. Všude je to 25; jiný jen pro zkoušku proti vlastnímu serveru.",
"The sender’s address. Your mail server may allow only its own addresses; going direct, the domain should have this machine in its SPF.":
"Adresa odesílatele. Váš poštovní server může povolit jen své vlastní adresy; při přímém odesílání by doména měla mít tento stroj ve svém SPF.",
"The name beside it, as the recipient sees it. Empty: the name of this installation.":
"Jméno vedle adresy, jak ho uvidí příjemce. Prázdné: název této instalace.",
"Where a reply goes - a helpdesk, say. Empty: back to the sender.":
"Kam půjde odpověď – třeba na helpdesk. Prázdné: zpět odesílateli.",
"The name this machine greets the server with. Empty: its own full name. Going direct, it should be the name its address resolves back to.":
"Jméno, kterým se tento stroj serveru představí. Prázdné: jeho vlastní plné jméno. Při přímém odesílání by to mělo být jméno, na které se jeho adresa zpětně překládá.",
"The language a token’s mail is written in unless it is chosen when the token is made.":
"Jazyk e-mailu s tokenem, pokud se nezvolí při vytváření tokenu.",
"Whether the recovery codes go in the mail as well unless chosen when the token is made. Each signs in once in place of a code from the phone.":
"Zda e-mail obsahuje i záložní kódy, pokud se to nezvolí při vytváření tokenu. Každý přihlásí jednou místo kódu z telefonu.",
# titles and small words seen untranslated
"The menu hides itself at the edge of the screen and slides out when you point at it. Press this to keep it open.":
"Menu se schová na okraj obrazovky a vysune se, když na něj najedete myší. Stiskem ho necháte otevřené.",
"In the directory: who it is, whether the account is switched off, its groups":
"V adresáři: kdo to je, zda je účet vypnutý, jeho skupiny",
"Edit: the QR code, the recovery codes, switching it off, the note":
"Upravit: QR kód, záložní kódy, vypnutí, poznámka",
"Take it away": "Odebrat", "while paused": "během pauzy", "Its token": "Jeho token",
"brought over from totpcgi": "převzato z totpcgi", "brought over from clients.conf": "převzato z clients.conf",
"made by the installer": "vytvořen instalací",
"An account kept here, not in a directory": "Účet vedený zde, ne v adresáři",
"Set a new password": "Nastavit nové heslo", "Stop it signing in": "Zakázat přihlašování", "Remove it": "Odebrat",
"The password is the directory’s: it is changed there": "Heslo patří adresáři: mění se tam",
"How many rows match the filters above, and where in them this page is. How many are shown at a time is the last box in the filter row.":
"Kolik řádků odpovídá filtrům nahoře a kde mezi nimi tato stránka je. Kolik se jich ukáže najednou, určuje poslední pole v řádku filtrů.",
"This dump was taken off a different engine from the one this installation is on now, so it cannot be put back here. Put that engine back on, or use a copy — a copy goes into any of the three.":
"Tento dump pochází z jiného databázového stroje, než na kterém instalace běží teď, takže ho sem nelze vrátit. Přepněte zpět na ten stroj, nebo použijte kopii – kopie jde do kteréhokoli ze tří.",
"Save this dump to the machine you are sitting at. It is what the engine’s own program wrote, so its own tools read it: pg_restore, or the mariadb client. The key that opens the tokens is not in it: it is the .key file beside it.":
"Uložit tento dump do počítače, u kterého sedíte. Zapsal ho vlastní program databáze, takže ho čtou její nástroje: pg_restore nebo klient mariadb. Klíč k tokenům v něm není: je to soubor .key vedle něj.",
"Delete this file, and the key beside it, from the server. The live database is not touched.":
"Smazat tento soubor i klíč vedle něj ze serveru. Živé databáze se to nedotkne.",
"Save this copy to the machine you are sitting at. It is the whole database as it was when the copy was made, and it can be put back here. The key that opens the tokens is not in it: it is the .key file beside it.":
"Uložit tuto kopii do počítače, u kterého sedíte. Je to celá databáze tak, jak byla v okamžiku kopie, a lze ji sem vrátit. Klíč k tokenům v ní není: je to soubor .key vedle ní.",
"Take it off the list": "Odebrat ze seznamu",
"Load balancer": "Load balancer",
}
P121 = {
"Back to the first page of this list. You are on page {0} of {1}.": "Zpět na první stránku seznamu. Jste na stránce {0} z {1}.",
"The page before this one. You are on page {0} of {1}. The filters above stay as they are.": "Předchozí stránka. Jste na stránce {0} z {1}. Filtry nahoře zůstanou, jak jsou.",
"The next page of this list. You are on page {0} of {1}. The filters above stay as they are.": "Další stránka seznamu. Jste na stránce {0} z {1}. Filtry nahoře zůstanou, jak jsou.",
"The last page of this list. You are on page {0} of {1}.": "Poslední stránka seznamu. Jste na stránce {0} z {1}.",
"signed in from {0}": "přihlášen přes {0}",
"{0} token(s), {1} RADIUS request(s)": "{0} {0:token|tokeny|tokenů}, {1} {1:RADIUS požadavek|RADIUS požadavky|RADIUS požadavků}",
"Not the version this node runs ({0}): both nodes should run the same one.": "Jiná verze, než běží na tomto uzlu ({0}): oba uzly by měly běžet na stejné.",
"{0} has every table as it comes: nothing to put back.": "{0} má všechny tabulky ve výchozím stavu: není co vracet.",
"{0} has laid out {1} table(s) by hand. Put every one of them back as it comes: the widths, the order and the hidden columns. Nothing else of theirs changes.":
"{0} si ručně upravil {1} {1:tabulku|tabulky|tabulek}. Vrátit všechny do výchozího stavu: šířky, pořadí i skryté sloupce. Nic jiného se nezmění.",
# events written by the mail and the export
"{0} exported {1} token(s) as .totp files (filter: {2})": "{0} exportoval {1} {1:token|tokeny|tokenů} jako soubory .totp (filtr: {2})",
"{0} exported {1} token(s) as .totp files": "{0} exportoval {1} {1:token|tokeny|tokenů} jako soubory .totp",
"{0} exported the token of {1} as a .totp file": "{0} exportoval token {1} jako soubor .totp",
"{0} sent the token of {1} to {2} with its recovery codes": "{0} poslal token {1} na {2} i se záložními kódy",
"{0} sent the token of {1} to {2}": "{0} poslal token {1} na {2}",
"{0} sent a test mail to {1}": "{0} poslal zkušební e-mail na {1}",
"a test mail to {0} failed: {1}": "zkušební e-mail na {0} selhal: {1}",
"{0} added to the certificate authorities of the mail server": "{0} přidal certifikační autoritu poštovního serveru",
"{0} took one out of the certificate authorities of the mail server": "{0} odebral jednu z certifikačních autorit poštovního serveru",
"{0} emptied the certificate authorities of the mail server": "{0} vyprázdnil certifikační autority poštovního serveru",
"the server would not take mail for {0}": "server nepřijal poštu pro {0}",
"the token of {0} could not be sent to {1}: {2}": "token {0} se nepodařilo poslat na {1}: {2}",
"the server would not take mail from {0}": "server nepřijal poštu od {0}",
"the certificate of {0} is not trusted - add the authority that signed it, or switch the check off": "certifikát {0} není důvěryhodný – přidejte autoritu, která ho podepsala, nebo ověřování vypněte",
}
R121 = {}
S121.update({
"Another realm or another person.": "Jiný realm nebo jiný člověk.",
"Seen only here.": "Vidět jen tady.",
"Take the token away": "Odebrat token",
"the mail server did not take the account or the password": "poštovní server nepřijal účet nebo heslo",
})

S121.update({
"DNS servers for the recipients’ domains": "DNS servery pro domény příjemců",
"Going direct: the DNS servers asked where each recipient’s domain takes its mail (its MX record), separated by commas - 1.1.1.1, 8.8.8.8. Empty: the ones in /etc/resolv.conf. Only for a machine whose own resolver will not answer that.":
"Při přímém odesílání: DNS servery, kterých se ptát, kam doména příjemce přijímá poštu (její MX záznam), oddělené čárkami – 1.1.1.1, 8.8.8.8. Prázdné: ty z /etc/resolv.conf. Jen pro stroj, jehož vlastní resolver na to neodpoví.",
"MX records (dnspython)": "MX záznamy (dnspython)",
"no MX record: the domain itself (dnspython)": "žádný MX záznam: přímo doména (dnspython)",
})
P121.update({
"MX records from DNS {0}": "MX záznamy z DNS {0}",
"no MX record (DNS {0}): the domain itself": "žádný MX záznam (DNS {0}): přímo doména",
"a null MX (DNS {0}): the domain takes no mail": "null MX (DNS {0}): doména poštu nepřijímá",
"no DNS server could say where mail for {0} goes: {1}": "žádný DNS server neřekl, kam jde pošta pro {0}: {1}",
"no DNS server could say where mail for {0} goes": "žádný DNS server neřekl, kam jde pošta pro {0}",
"{0} refused to answer": "{0} odmítl odpovědět",
"{0} failed (SERVFAIL)": "{0} selhal (SERVFAIL)",
"the domain {0} does not exist (DNS {1})": "doména {0} neexistuje (DNS {1})",
"{0} takes no mail (its MX record is a null MX)": "{0} poštu nepřijímá (její MX je null MX)",
"mail_dns: {0} is not the address of a DNS server": "mail_dns: {0} není adresa DNS serveru",
})
P121.update({
"looked up {0}": "vyhledán {0}", "look up {0}": "vyhledat {0}",
"no address found for {0}: {1}": "pro {0} nebyla nalezena adresa: {1}",
"no address found for {0}": "pro {0} nebyla nalezena adresa",
"{0} · DNS {1}": "{0} · DNS {1}",
})
S121.update({"the system resolver": "systémový resolver"})
S121.update({
"a short message": "krátká zpráva", "a sample token mail": "ukázkový e-mail s tokenem",
"Sends a short message - or a sample of a token's mail, with a made-up key - the way a token's mail would go, and shows every step: the server reached, TLS, signing in, the message handed over and what the server said. Save the changes first.":
"Pošle krátkou zprávu – nebo ukázku e-mailu s tokenem s vymyšleným klíčem – stejnou cestou jako e-mail s tokenem a ukáže každý krok: spojení se serverem, TLS, přihlášení, předání zprávy a co server odpověděl. Nejdřív uložte změny.",
"handed the message over": "zpráva předána", "Send by mail": "Poslat e-mailem", "By mail": "E-mailem",
"The QR code to the person’s mailbox.": "QR kód do schránky člověka.",
"Send it": "Odeslat", "Sending…": "Odesílám…",
"From the directory; it can be changed.": "Z adresáře; lze ho změnit.",
"The ones not used yet. Each signs in once, in place of a code from the phone.": "Ty dosud nepoužité. Každý přihlásí jednou, místo kódu z telefonu.",
"Whoever reads this mail can make the person’s codes: send it only to their own mailbox. That it was sent is written down as an event.":
"Kdo tento e-mail přečte, může vytvářet kódy toho člověka: posílejte ho jen do jeho vlastní schránky. Odeslání se zapíše do událostí.",
"Sending mail is switched off - Settings → Mail.": "Odesílání pošty je vypnuté – Nastavení → Pošta.",
})
P121.update({
"greeted it as {0}": "představil se jako {0}",
"for {0} · {1}": "pro {0} · {1}",
"Last sent to {0}, {1}.": "Naposledy odesláno na {0}, {1}.",
"Send the token of {0} by mail": "Poslat token {0} e-mailem",
"Sent to {0}.": "Odesláno na {0}.", "Not sent: {0}": "Neodesláno: {0}",
"Where it went last time, sent by {0} - {1}. It can be changed.": "Kam šel minule, poslal {0} – {1}. Lze ho změnit.",
"Where it went last time - {0}. It can be changed.": "Kam šel minule – {0}. Lze ho změnit.",
"{0} sent the token of {1} to {2} again{3}": "{0} znovu poslal token {1} na {2}{3}",
"{0} sent a test mail shaped as a token's to {1}": "{0} poslal ukázkový e-mail s tokenem na {1}",
"the recovery codes of this token were not kept to be sent again; send it without them, or make new ones first": "záložní kódy tohoto tokenu nebyly uloženy pro opětovné odeslání; pošlete ho bez nich, nebo nejdřív vytvořte nové",
})
S121.update({"details": "podrobnosti", "hide": "skrýt"})
S121.setdefault("Key", "Klíč")
S121.update({
"Six is what everybody expects and what every application shows. Only for tokens made from now on: each token keeps the length it was made with, so imported and older ones go on working beside new ones. Microsoft Authenticator shows six whatever this says - with 8 its codes are refused.":
"Šest čekají všichni a ukazuje je každá aplikace. Platí jen pro tokeny vytvořené od teď: každý token si nechává délku, se kterou vznikl, takže importované a starší fungují dál vedle nových. Microsoft Authenticator ukazuje šest číslic, ať je tu cokoli – s 8 budou jeho kódy odmítnuty.",
"Thirty seconds is the standard, and Google Authenticator knows no other. Only for tokens made from now on; each keeps its own.":
"Třicet sekund je standard a Google Authenticator jiný nezná. Platí jen pro tokeny vytvořené od teď; každý si nechává svůj.",
"SHA-1 is what RFC 6238 says and what every application implements - and it is not weak here: the key is 160 random bits. Only for tokens made from now on; each keeps its own, so imported SHA-1 tokens go on working beside new ones. Microsoft Authenticator and Google Authenticator on Android ignore SHA-256 and SHA-512 and make SHA-1 codes, which are then refused: those two are for hardware tokens and applications that take them (FreeOTP, Google Authenticator on iPhone).":
"SHA-1 předepisuje RFC 6238 a umí ho každá aplikace – a tady není slabý: klíč má 160 náhodných bitů. Platí jen pro tokeny vytvořené od teď; každý si nechává svůj, takže importované SHA-1 tokeny fungují dál vedle nových. Microsoft Authenticator a Google Authenticator na Androidu SHA-256 a SHA-512 ignorují a vytvářejí kódy SHA-1, které pak budou odmítnuty: ty dva jsou pro hardwarové tokeny a aplikace, které je umí (FreeOTP, Google Authenticator na iPhonu).",
})
