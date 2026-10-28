S122 = {
"Say why in a refusal": "Uvádět důvod v odmítnutí",
"Off: a refusal goes back with no reason in it, and the reason is only in the log here. On: the reason goes back as a Reply-Message, which a VPN may show to whoever is signing in - telling a stranger whether a name has a token, or that the code was right and the password not.":
"Vypnuto: odmítnutí odejde bez důvodu a důvod je jen v logu zde. Zapnuto: důvod odejde jako Reply-Message, kterou VPN může ukázat tomu, kdo se přihlašuje – a prozradit cizímu, zda jméno má token, nebo že kód byl správně a heslo ne.",
"Hold a client to the Message-Authenticator": "Držet klienta u Message-Authenticatoru",
"A client that has once sent a right Message-Authenticator must send one with every request from then on: one that arrives without is dropped (BlastRADIUS, CVE-2024-3596). Remembered until the service restarts; Must send a Message-Authenticator on the client holds it always.":
"Klient, který jednou poslal správný Message-Authenticator, ho od té doby musí posílat s každým požadavkem: požadavek bez něj se zahodí (BlastRADIUS, CVE-2024-3596). Pamatuje se do restartu služby; volba Musí posílat Message-Authenticator u klienta ho drží vždy.",
"Wrong codes in a row before a lockout": "Chybných kódů za sebou do zablokování",
"Locked out for (min)": "Zablokováno na (min)",
"Wrong codes one after another - however slowly they come - after which the token takes no code at all for the time below, and again after each further one. The pause above stops a quick guesser; this one stops a slow one, who would otherwise get thousands of guesses a day. A right code starts the count again; Forget them on the token ends it at once. 0 switches it off.":
"Chybné kódy jeden za druhým – jakkoli pomalu přicházejí – po kterých token po dobu níže nepřijme žádný kód, a znovu po každém dalším. Pauza výše zastaví rychlého hádače; tahle zastaví pomalého, který by jinak měl tisíce pokusů denně. Správný kód počítání vynuluje; Zapomenout je u tokenu ho ukončí hned. 0 vypíná.",
"How long a token takes no code once it has been locked out.": "Jak dlouho token po zablokování nepřijme žádný kód.",
"Encryption to the database server": "Šifrování k databázovému serveru",
"Its certificate authority (file)": "Jeho certifikační autorita (soubor)",
"TLS to a database on another machine, and to the other node. Empty: as the driver decides - encrypted where the server offers it, and nothing stops somebody on the way from saying it does not. require: always encrypted. verify-full: encrypted, and the server's certificate checked against the authority below and the host name - the only one that stops somebody in between. The server must have TLS switched on.":
"TLS k databázi na jiném stroji a k druhému uzlu. Prázdné: jak rozhodne ovladač – šifrovaně, pokud to server nabídne, a nic nebrání někomu po cestě tvrdit, že nenabízí. require: vždy šifrovaně. verify-full: šifrovaně a s ověřením certifikátu serveru proti autoritě níže a jménu hostitele – jediná volba, která zastaví útočníka uprostřed. Server musí mít TLS zapnuté.",
"The file of the authority that signed the database server's certificate, for verify-ca and verify-full: /etc/otp/db-ca.pem.":
"Soubor autority, která podepsala certifikát databázového serveru, pro verify-ca a verify-full: /etc/otp/db-ca.pem.",
"Encryption to the recipients’ servers": "Šifrování k serverům příjemců",
"encrypted where the server offers it": "šifrovaně, kde to server nabízí",
"encrypted, or not sent at all": "šifrovaně, jinak vůbec",
"Going direct: whether a server that offers no STARTTLS still gets the mail, in the clear. Required is safer - a token's mail holds its key, and anybody on the way can strip the offer - but a domain whose server has no TLS then gets nothing.":
"Při přímém odesílání: zda server, který STARTTLS nenabízí, dostane poštu i tak – nešifrovaně. Povinné šifrování je bezpečnější – e-mail s tokenem obsahuje jeho klíč a kdokoli po cestě může nabídku TLS odstranit – ale doména, jejíž server TLS nemá, pak nedostane nic.",
"Drop the .totp files here - or a ZIP of them - or press to pick them": "Přetáhněte sem soubory .totp – nebo ZIP s nimi – nebo klikněte a vyberte je",
"Realms it may use": "Realmy, které smí používat",
"None ticked: any. Ticked: a name in any other realm is refused from this client - so nobody signs in to the VPN through the realm of the Wi-Fi, which asks for less.":
"Nic nezaškrtnuto: jakýkoli. Zaškrtnuté: jméno v jakémkoli jiném realmu se od tohoto klienta odmítne – takže se nikdo nepřihlásí do VPN přes realm Wi-Fi, který vyžaduje méně.",
"No realm yet.": "Zatím žádný realm.",
"every name": "každé jméno", "without a realm": "bez realmu",
"Locked out after too many wrong codes, please try again later": "Zablokováno po příliš mnoha chybných kódech, zkuste to později",
"the password is not right": "heslo není správné",
"it broke - the reason is in the log of the service (/var/log/otp/otp.log)": "něco se pokazilo – důvod je v logu služby (/var/log/otp/otp.log)",
"that account may no longer sign in": "tento účet se již nesmí přihlásit",
"enrolling a token here is switched off": "registrace tokenu je zde vypnutá",
"that search has too many NOTs and brackets in it": "hledání obsahuje příliš mnoho NOT a závorek",
"new recovery codes are shown to whoever makes them, and showing codes and keys is switched off (Settings -> The tokens)":
"nové záložní kódy uvidí ten, kdo je vytvoří, a zobrazování kódů a klíčů je vypnuté (Nastavení -> Tokeny)",
}
P122 = {
"the client {0} may not use the realm {1}": "klient {0} nesmí používat realm {1}",
"there is no realm called {0}": "realm {0} neexistuje",
"too many wrong passwords for this name: try again in {0}": "příliš mnoho chybných hesel pro toto jméno: zkuste to znovu za {0}",
"too many wrong passwords from {0}: try again in {1}": "příliš mnoho chybných hesel z {0}: zkuste to znovu za {1}",
"{0} threw away the replacement waiting for {1}": "{0} zahodil čekající náhradu pro {1}",
"{0} changed the note of {1}": "{0} změnil poznámku u {1}",
"{0} ended the sign-in of {1}": "{0} ukončil přihlášení {1}",
"{0} ended the sign-in of {1} from {2}": "{0} ukončil přihlášení {1} z {2}",
"{0} stopped replacing their token": "{0} přestal měnit svůj token",
"{0} threw away the token they had not confirmed": "{0} zahodil nepotvrzený token",
"{0} set a new password for {1}; their sign-ins are ended": "{0} nastavil nové heslo pro {1}; jeho přihlášení jsou ukončena",
"the directory gives {0} the role {1} now (was {2})": "adresář teď dává {0} roli {1} (dříve {2})",
"the directory no longer gives {0} a role here: signed out everywhere": "adresář už {0} nedává žádnou roli: odhlášen všude",
"{0} sent the token of {1} to {2} with its recovery codes - the server said: {3}": "{0} poslal token {1} na {2} i se záložními kódy – server odpověděl: {3}",
"{0} sent the token of {1} to {2} - the server said: {3}": "{0} poslal token {1} na {2} – server odpověděl: {3}",
"{0} sent the token of {1} to {2} again with its recovery codes - the server said: {3}": "{0} znovu poslal token {1} na {2} i se záložními kódy – server odpověděl: {3}",
"{0} sent the token of {1} to {2} again - the server said: {3}": "{0} znovu poslal token {1} na {2} – server odpověděl: {3}",
"not answered and not written down one by one in the last minute: {0} packet(s) - {1}": "za poslední minutu nezodpovězeno a nezapsáno jednotlivě: {0} {0:paket|pakety|paketů} – {1}",
}
R122 = {}
