# 1.0.74: the web address (VRRP) on the command line
S138 = {
"The web address (VRRP)": "Webová adresa (VRRP)",
"Move the address to that node now, by hand - it goes once the node is healthy (its pages answer, RADIUS listens, not in maintenance).":
"Přesune adresu na daný uzel hned, ručně – přejde, jakmile je uzel zdravý (jeho stránky odpovídají, RADIUS naslouchá, není v údržbě).",
"A node out of service and back: RADIUS is not answered, its /healthz says 503 - and the web address leaves it for the other node by itself.":
"Uzel mimo provoz a zpět: na RADIUS se neodpovídá, jeho /healthz vrací 503 – a webová adresa z něj sama přejde na druhý uzel.",
"This node asks root again for what failed (keepalived's configuration, a certificate for nginx, the firewall).":
"Tento uzel znovu požádá roota o to, co selhalo (konfigurace keepalived, certifikát pro nginx, firewall).",
"On the node itself, when the address does not come or does not move: whether keepalived runs, what it said (each change between MASTER and BACKUP is a line), and on which interface the address is. VRRP is IP protocol 112 between the two nodes - the firewall lets it in from the other node by itself.":
"Přímo na uzlu, když adresa nenaběhne nebo se nepřesune: zda keepalived běží, co hlásil (každá změna mezi MASTER a BACKUP je jeden řádek) a na kterém rozhraní adresa je. VRRP je mezi oběma uzly IP protokol 112 – firewall ho od druhého uzlu povolí sám.",
"The web address on or off: root writes keepalived's configuration and starts it, or stops it and takes the address away - on both nodes.":
"Webová adresa zapnutá nebo vypnutá: root zapíše konfiguraci keepalived a spustí ho, nebo ho zastaví a adresu odebere – na obou uzlech.",
"The address itself: with its prefix, its host name, the VRRP id (1-255, default 51; another id for every cluster on the same network) and on each node the interface it goes on (default: the one with the node's own address). Run on one node; the other takes it within a few seconds.":
"Samotná adresa: s prefixem, názvem hostitele, VRRP id (1–255, výchozí 51; každý cluster ve stejné síti potřebuje jiné id) a na každém uzlu rozhraní, na které se dává (výchozí: to s vlastní adresou uzlu). Spusťte na jednom uzlu; druhý to převezme během několika sekund.",
}
P138 = {}
R138 = {
"Where the web address is now and how each node sees it (VRRP: master or backup), its settings, and the certificates of the nodes and of the address. <code>--json</code> for a script.":
"Kde adresa právě je a jak ji vidí každý uzel (VRRP: master nebo backup), její nastavení a certifikáty uzlů i adresy. <code>--json</code> pro skript.",
"Where it goes after a failure is over: always back to that node, or <i>stay</i> - it stays where it is until that node fails or it is moved by hand.":
"Kam se vrátí po skončení výpadku: vždy zpět na daný uzel, nebo <i>stay</i> – zůstane, kde je, dokud ten uzel neselže nebo ji nepřesunete ručně.",
}
S138.update({
"The commands": "Příkazy",
"replication · the web address (VRRP) · maintenance": "replikace · webová adresa (VRRP) · údržba",
"The authenticator app with its codes": "Aplikace authenticator se svými kódy",
"How a code is made: the key and the time (TOTP)": "Jak vzniká kód: klíč a čas (TOTP)",
"The six digits, good for 30 seconds": "Šest číslic, platných 30 sekund",
"The name, the password and the code": "Jméno, heslo a kód",
"The VPN asking for the code": "VPN se ptá na kód",
"The codes in time, a step either side": "Kódy v čase, krok na každou stranu",
"Recovery codes when the phone is gone": "Záložní kódy, když telefon chybí",
"An authenticator app with a code for each account": "Aplikace authenticator s kódem pro každý účet",
"A code is made of the key and the time": "Kód vzniká z klíče a času",
"A one-time password, good for 30 seconds": "Jednorázové heslo platné 30 sekund",
"The name, the password and the code from the phone": "Jméno, heslo a kód z telefonu",
"The VPN asks for the code from the phone": "VPN se ptá na kód z telefonu",
"A new code every 30 seconds; the server takes one step either side": "Každých 30 sekund nový kód; server přijme i jeden krok na každou stranu",
"Recovery codes, each works once, for when the phone is gone": "Záložní kódy, každý funguje jednou, pro případ, že telefon chybí",
"THE AUTHENTICATOR APP": "APLIKACE AUTHENTICATOR",
"THE KEY": "KLÍČ",
"STAYS IN IT": "ZŮSTÁVÁ V NÍ",
"SIGNED IN": "PŘIHLÁŠEN",
"THE TIME": "ČAS",
"THE PHONE AND THE SERVER WORK OUT THE SAME CODE": "TELEFON I SERVER SPOČÍTAJÍ STEJNÝ KÓD",
"YOUR ONE-TIME PASSWORD": "VAŠE JEDNORÁZOVÉ HESLO",
"GOOD FOR 30 SECONDS · ONCE": "PLATÍ 30 SEKUND · JEDNOU",
"NAME · PASSWORD · CODE": "JMÉNO · HESLO · KÓD",
"NAME": "JMÉNO",
"PASSWORD": "HESLO",
"CODE": "KÓD",
"ONE CODE EVERY 30 SECONDS": "JEDEN KÓD KAŽDÝCH 30 SEKUND",
"NOW": "TEĎ",
"THE SERVER TAKES ONE STEP EITHER SIDE": "SERVER PŘIJME I KROK NA KAŽDOU STRANU",
"NO PHONE?": "BEZ TELEFONU?",
"RECOVERY CODES": "ZÁLOŽNÍ KÓDY",
"EACH WORKS ONCE": "KAŽDÝ FUNGUJE JEDNOU",
"STILL IN": "PŘESTO DOVNITŘ",
})
