# 1.0.107: TLS between the databases switched off again; the Database page says about the link.
S156 = {
 "Switch TLS off…": "Vypnout TLS…",
 "Switch TLS between the databases off?": "Vypnout TLS mezi databázemi?",
 "Switch it off": "Vypnout", "Switch it off again": "Vypnout znovu",
 "Switching TLS between the databases off…": "Vypínám TLS mezi databázemi…",
 "The steps the other way round, so replication never stops: both databases let the other node in without TLS, both links go back, then the certificates leave both PostgreSQLs.": "Kroky v opačném pořadí, aby se replikace nezastavila: obě databáze pustí druhý uzel i bez TLS, obě spojení se vrátí a pak se certifikáty odeberou z obou PostgreSQL.",
 "Back to how it was before: both databases let the other node in without TLS, both links go back to Database → TLS, and the cluster’s certificates leave both PostgreSQLs (ssl as postgresql.conf says). Replication goes on meanwhile. Repair turns it on again.": "Zpět, jak to bylo: obě databáze pustí druhý uzel i bez TLS, obě spojení se vrátí k Databáze → TLS a certifikáty clusteru se odeberou z obou PostgreSQL (ssl podle postgresql.conf). Replikace mezitím běží. Opravit to zase zapne.",
 "without TLS too": "i bez TLS", "link back": "spojení zpět", "certificate away": "certifikát pryč",
 "this node's PostgreSQL lets the other node in without TLS too": "PostgreSQL tohoto uzlu pouští druhý uzel i bez TLS",
 "this node takes the other's rows as before (Database → TLS)": "tento uzel bere řádky druhého jako dřív (Databáze → TLS)",
 "the cluster's certificate leaves this node's PostgreSQL": "certifikát clusteru se odebírá z PostgreSQL tohoto uzlu",
 "pg_hba.conf already lets the other node in without TLS": "pg_hba.conf už pouští druhý uzel i bez TLS",
 "The link to the other node: not encrypted": "Spojení k druhému uzlu: nešifrované",
 "Its own setting, made by Settings → High availability (the cluster’s own authority). This field is only this daemon’s connection to its own PostgreSQL on 127.0.0.1 - leave it empty.": "Vlastní nastavení, které udělalo Nastavení → Vysoká dostupnost (vlastní autorita clusteru). Toto pole je jen spojení démona k vlastnímu PostgreSQL na 127.0.0.1 – nechte ho prázdné.",
 "As this field says. Settings → High availability → Repair encrypts and checks it without touching this field.": "Podle tohoto pole. Nastavení → Vysoká dostupnost → Opravit ho zašifruje a ověří, aniž by na toto pole sáhlo.",
 "Settings → High availability": "Nastavení → Vysoká dostupnost",
 "TLS to a database on another machine - and to the other node of a cluster until Settings → High availability encrypts that link with its own setting. Empty: as the driver decides - encrypted where the server offers it, and nothing stops somebody on the way from saying it does not. require: always encrypted. verify-full: encrypted, and the server's certificate checked against the authority below and the host name - the only one that stops somebody in between. The server must have TLS switched on.": "TLS k databázi na jiném stroji – a k druhému uzlu clusteru, dokud Nastavení → Vysoká dostupnost nezašifruje toto spojení vlastním nastavením. Prázdné: jak rozhodne ovladač – šifrovaně, pokud to server nabídne, a nic nebrání někomu po cestě tvrdit, že nenabízí. require: vždy šifrovaně. verify-full: šifrovaně a s ověřením certifikátu serveru proti autoritě níže a jménu hostitele – jediná volba, která zastaví útočníka uprostřed. Server musí mít TLS zapnuté.",
}
P156 = {
 "The link to the other node: encrypted and checked ({0})": "Spojení k druhému uzlu: šifrované a ověřované ({0})",
 "The link to the other node: {0}": "Spojení k druhému uzlu: {0}",
 "waiting for {0} to let this node in without TLS": "čekám, až {0} pustí tento uzel i bez TLS",
 "waiting for {0} to move its link back": "čekám, až {0} vrátí své spojení",
 "the other node ({0}) is let in with or without TLS again": "druhý uzel ({0}) se zase dostane dovnitř s TLS i bez",
 "PostgreSQL is as it was before (ssl = {0}, by postgresql.conf); taken away: {1}": "PostgreSQL je jako dřív (ssl = {0}, podle postgresql.conf); odebráno: {1}",
 "TLS between the databases is off on {0}": "TLS mezi databázemi je na {0} vypnuté",
 "{0}: TLS between the databases is being switched off on both nodes": "{0}: TLS mezi databázemi se vypíná na obou uzlech",
}
R156 = {
 "<b>Whoever is on the network between the nodes will be able to read every row going over and put rows of their own in.</b><br>Both nodes go through the steps by themselves; replication goes on meanwhile. Repair turns it on again at any time.": "<b>Kdokoli na síti mezi uzly bude moct číst každý přenášený řádek a vkládat vlastní.</b><br>Oba uzly projdou kroky samy; replikace mezitím běží. Opravit to kdykoli zase zapne.",
}
S156.update({"When the name is not known": "Když jméno neznáme"})
R156.update({
 "Every word people get from this server: the mails of a code and of a token, the SMS, what the VPN's second window says - in Czech and in English. A mail is edited as it will look: click into its text and write. What is in blue is filled in when it is sent (the code, the name...). Saved in the database, so every node of a cluster sends the same words; <i>Put back as it comes</i> makes a text exactly as it was before it was changed.":
 "Všechno, co lidé od tohoto serveru dostanou: maily s kódem a s tokenem, SMS, co říká druhé okno VPN – česky i anglicky. Mail se upravuje tak, jak bude vypadat: klikněte do jeho textu a pište. Co je modře, se doplní při odeslání (kód, jméno…). Uloženo v databázi, takže každý uzel clusteru posílá stejné texty; <i>Vrátit výchozí</i> vrátí text přesně tak, jak byl, než se změnil.",
})
