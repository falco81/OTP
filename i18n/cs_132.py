# 1.0.59: errors under load, the second review's fixes
S132 = {
"a rebuild is running already (on this node or the other one)": "obnova už běží (na tomto nebo na druhém uzlu)",
"fifteen ports at most in one rule (a range counts as two)": "nejvýše patnáct portů v jednom pravidle (rozsah se počítá za dva)",
"the password is longer than RADIUS carries (128 bytes)": "heslo je delší, než RADIUS unese (128 bajtů)",
"the firewall rules are a list, 2000 at most": "pravidla firewallu jsou seznam, nejvýše 2000",
"Not a valid token. Too many wrong codes: the new key was thrown away - the token in use goes on working; make a new one.": "Neplatný token. Příliš mnoho chybných kódů: nový klíč byl zahozen – stávající token dál funguje; vytvořte nový.",
"Too many wrong codes: the new key was thrown away - the token in use goes on working; make a new one.": "Příliš mnoho chybných kódů: nový klíč byl zahozen – stávající token dál funguje; vytvořte nový.",
"A token is the application on your phone that shows a new code every few seconds. The VPN asks for that code.": "Token je aplikace v telefonu, která každých pár vteřin ukáže nový kód. Na ten kód se ptá VPN.",
"the dump is being made; the download starts when it is ready. The key that opens the tokens is not in a dump: keep a copy of /var/lib/otp/secrets.key with it": "dump se připravuje; stahování začne, až bude hotový. Klíč, kterým se otevírají tokeny, v dumpu není: uložte si k němu kopii /var/lib/otp/secrets.key",
"The port on 127.0.0.1 the web pages ask this daemon on. The pages read it from <code>/run/otp/api-port</code>, written when the daemon starts.": "Port na 127.0.0.1, na kterém se webové stránky ptají tohoto démona. Stránky ho čtou z <code>/run/otp/api-port</code>, který démon zapíše při startu.",
"NO KEY CAME WITH IT and its tokens do not open with the key in use: put back the .key file that was beside the dump (or the copy from the download) - until then every token is refused": "NEPŘIŠEL S NÍ KLÍČ a její tokeny se klíčem v provozu neotevřou: vraťte soubor .key, který ležel vedle dumpu (nebo kopii ze stažení) – do té doby bude každý token odmítnut",
}
P132 = {
"this request reached {0}, not {1}: open the page of {2} itself (its own address) to rebuild it": "tento požadavek došel na {0}, ne na {1}: pro obnovu otevřete stránku přímo na {2} (jeho vlastní adresou)",
"{0} has no value: an attribute is never sent empty": "{0} nemá hodnotu: prázdný atribut se nikdy neposílá",
"{0} takes a number from 0 to 16777215, not {1}": "{0} bere číslo od 0 do 16777215, ne {1}",
"{0}: {1} attributes are not laid out as one byte of type and one of length - this server cannot send them by number": "{0}: atributy {1} nemají jeden bajt typu a jeden bajt délky – tento server je podle čísla poslat neumí",
"{0} is a salted key (MS-MPPE): it cannot be sent by number": "{0} je solený klíč (MS-MPPE): podle čísla ho poslat nejde",
"{0} said it is closing the connection": "{0} oznámil, že spojení zavírá",
"{0} did not finish the search within {1} s": "{0} nedokončil hledání do {1} s",
"{0} sent an answer that does not read: {1}": "{0} poslal odpověď, která se nedá přečíst: {1}",
"{0} - left in maintenance: it runs {1}, which did not pass its checks": "{0} – ponecháno v údržbě: běží na {1}, která neprošla kontrolami",
"not heard from for {0} min while {1} - marked failed by {2}": "{0} min bez odezvy během kroku {1} – jako neúspěšné označil {2}",
"the upgrade of {0} to {1} failed: the node has not been heard from": "upgrade {0} na {1} selhal: uzel se neozývá",
"install.sh did not finish in {0} min and was stopped": "install.sh neskončil do {0} min a byl zastaven",
"housekeeping waits for the database: {0}": "údržba čeká na databázi: {0}",
"RADIUS requests go unanswered: the database cannot be reached ({0})": "RADIUS požadavky zůstávají bez odpovědi: databáze není dostupná ({0})",
}
R132 = {}
