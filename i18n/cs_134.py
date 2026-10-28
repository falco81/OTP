# 1.0.62: the whole configuration as one file, upgrades from any version
S134 = {
"The whole configuration as one file: the settings (each node's own too), the RADIUS clients, the realms, the directories, the accounts of these pages, the certificates of the pages and the web address, the web address, who may reach which page, the firewall and the mail server's authorities. The tokens are not in it: they move with a copy of the database and its key. On the command line: otp --export-config FILE [--with-secrets] and otp --import-config FILE --yes.":
"Celá konfigurace jako jeden soubor: nastavení (i vlastní nastavení každého uzlu), RADIUS klienti, realmy, adresáře, účty těchto stránek, certifikáty stránek a webové adresy, webová adresa, kdo smí na kterou stránku, firewall a certifikační autority mailového serveru. Tokeny v něm nejsou: přenášejí se s kopií databáze a jejím klíčem. Na příkazové řádce: otp --export-config SOUBOR [--with-secrets] a otp --import-config SOUBOR --yes.",
"The shared secrets of the clients, the passwords of the directories and of the mail server, the password hashes of the accounts and the private keys of the certificates go into the file, readable. Keep it somewhere safe.":
"Sdílená tajemství klientů, hesla adresářů a mailového serveru, hashe hesel účtů a privátní klíče certifikátů se zapíšou do souboru čitelně. Uložte ho na bezpečné místo.",
"Clients, realms, directories and accounts of the same name are replaced; the settings, the certificates, the web address, who may reach the pages, the firewall and the mail server's authorities in it are saved. Your own account is left as it is.":
"Klienti, realmy, adresáře a účty stejného jména se nahradí; nastavení, certifikáty, webová adresa, přístup ke stránkám, firewall a autority mailového serveru ze souboru se uloží. Váš vlastní účet zůstane, jak je.",
"Add to what is here: anything not in the file stays. Exactly the file: clients, realms, directories and accounts not in it are taken away, and settings not in it go back to their defaults - as when a whole configuration is put back.":
"Přidat k tomu, co tu je: co v souboru není, zůstane. Přesně podle souboru: klienti, realmy, adresáře a účty, které v něm nejsou, se odeberou a nastavení, která v něm nejsou, se vrátí na výchozí hodnoty – jako při obnově celé konfigurace.",
"Exactly the file": "Přesně podle souboru",
"Add to what is here": "Přidat k tomu, co tu je",
"there is nothing in this file to import - is it an export of otp?": "v tomto souboru není nic k importu – je to export z otp?",
"there is no full administrator who can sign in in that file: putting it back would lock everybody out of these pages (on the command line it can be put back, and an account made after it)":
"v tom souboru není žádný plný administrátor, který se může přihlásit: obnova by všem zamkla tyto stránky (na příkazové řádce ji lze obnovit a účet založit potom)",
}
P134 = {
"Import {0}": "Import {0}",
}
R134 = {}
