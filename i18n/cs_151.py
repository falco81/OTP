# 1.0.101: the security review - new words, and words found untranslated.
S151 = {
 "the code was asked for too long ago: sign in again": "kód byl vyžádán příliš dávno: přihlaste se znovu",
 "the code is asked for in a second window": "kód se zadává ve druhém okně",
 "Code sent by mail accepted": "Kód poslaný e-mailem přijat",
 "Code sent by SMS accepted": "Kód poslaný SMS přijat",
 "Code sent accepted": "Poslaný kód přijat",
 "Denied by the token server: no tries left - sign in again": "Zamítnuto tokenovým serverem: nezbývají pokusy – přihlaste se znovu",
 "Denied by the token server: too many answers at once": "Zamítnuto tokenovým serverem: příliš mnoho odpovědí naráz",
 "the password does not decode: the shared secret is probably not the same as on the client": "heslo nejde rozšifrovat: sdílené tajemství se nejspíš neshoduje s tím na klientovi",
 "the account is disabled in the directory": "účet je v adresáři zakázaný",
 "the account has expired in the directory": "účet v adresáři vypršel",
 "it is disabled in the directory": "je v adresáři zakázaný",
 "it is locked out in the directory": "je v adresáři zamčený",
 "its password has expired in the directory": "jeho heslo v adresáři vypršelo",
 "the directory does not say whether it is in use (userAccountControl cannot be read)": "adresář neříká, zda se účet používá (userAccountControl nejde přečíst)",
 "there is no such account": "takový účet není",
 "that code was taken already": "ten kód už byl použit",
 "tests on the other node are running already - try again in a moment": "testy na druhém uzlu už běží – zkuste to za chvíli",
 "the password holds a control character": "heslo obsahuje řídicí znak",
 "no account to check the password of": "není účet, jehož heslo by se ověřilo",
 "Without HTTPS the gateway’s password and every code sent cross the network as they are: anybody on the way reads them.": "Bez HTTPS jde heslo k bráně i každý odeslaný kód sítí tak, jak jsou: kdokoli po cestě je přečte.",
 "The gateway’s certificate is not checked: anybody between this server and the gateway can stand in for it and read its password and every code sent. Switch the check on and read its certificate from it below.": "Certifikát brány se neověřuje: kdokoli mezi tímto serverem a bránou se za ni může vydávat a přečíst její heslo i každý odeslaný kód. Zapněte ověření a níže si její certifikát načtěte.",
 "The link between the two databases is not encrypted: whoever is on the network between the nodes reads every row going over and can put rows of their own in. Set Database → TLS to verify-full.": "Spojení mezi oběma databázemi není šifrované: kdo je v síti mezi uzly, přečte každý přenášený řádek a může vložit vlastní. Nastavte Databáze → TLS na verify-full.",
}
P151 = {
 "no realm takes the name {0}": "žádný realm nebere jméno {0}",
 "A code was sent by mail to {0}": "Kód byl poslán e-mailem na {0}",
 "A code was sent by SMS to {0}": "Kód byl poslán SMS na {0}",
 "the directory has nobody called {0}": "adresář nikoho jménem {0} nemá",
 "the account may not sign in: {0}": "účet se nesmí přihlásit: {0}",
 "Denied by the token server: the account may not sign in: {0}": "Zamítnuto tokenovým serverem: účet se nesmí přihlásit: {0}",
 "the token of {0} is locked out for {1} min after {2} wrong codes in a row - somebody may be guessing its codes": "token {0} je zamčený na {1} min po {2} chybných kódech v řadě – někdo možná hádá jeho kódy",
 "the token of {0} is locked out for {1} min after {2} wrong codes in a row": "token {0} je zamčený na {1} min po {2} chybných kódech v řadě",
 "{0} downloaded {1}, made for it - with the key that opens the tokens in it": "{0} stáhl(a) {1}, vytvořenou pro stažení – s klíčem, který otevírá tokeny",
 "{0} downloaded {1}, made for it - without the key that opens the tokens (showing keys is switched off)": "{0} stáhl(a) {1}, vytvořenou pro stažení – bez klíče, který otevírá tokeny (zobrazování klíčů je vypnuté)",
 "{0} downloaded {1}, made for it": "{0} stáhl(a) {1}, vytvořenou pro stažení",
 "the realm {0} already keeps its tokens under the name alone, with the directory {1}: names alone are one person's only within one directory - keep this realm's under the whole name": "realm {0} už vede tokeny pod samotným jménem, s adresářem {1}: samotné jméno patří jednomu člověku jen v rámci jednoho adresáře – v tomto realmu veďte tokeny pod celým jménem",
 "the directory knows {0}, and none of the groups given a role here holds them (from {1})": "adresář zná {0}, ale není v žádné skupině, která tu dává roli (z {1})",
 "The link between the two databases is encrypted, but whose certificate answers is not checked ({0}): set Database → TLS to verify-full, with the authority that signed the database’s certificate.": "Spojení mezi oběma databázemi je šifrované, ale neověřuje se, čí certifikát odpovídá ({0}): nastavte Databáze → TLS na verify-full s autoritou, která certifikát databáze podepsala.",
 "{0} made a bundle for a second node to join this one (the database at {1}) - it carries the key that opens every token": "{0} vytvořil(a) balíček pro připojení druhého uzlu (databáze na {1}) – nese klíč, který otevírá všechny tokeny",
 "dropped from {0}": "zahozeno od {0}",
 "Denied by the token server: Rate-limit reached, please try again later": "Zamítnuto tokenovým serverem: příliš mnoho pokusů, zkuste to později",
}
R151 = {}
S151.update({"Unlock it": "Odemknout"})
P151.update({"{0} now · locked until {1} {2}.": "teď {0} · zamčeno do {1} {2}."})
P151.update({
 "the recovery codes of {0} are not taken for a day: {1} requests in a day had a wrong password or a wrong recovery code - somebody may be guessing them (Unlock it on the token gives them back)": "záložní kódy {0} se den nepřijímají: {1} požadavků za den mělo špatné heslo nebo špatný záložní kód – někdo je možná hádá (Odemknout na tokenu je vrátí)",
})
