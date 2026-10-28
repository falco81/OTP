# 1.0.63: where a copy was made
S135 = {
"Made on": "Vytvořeno na",
"Its database": "Jeho databáze",
"Its cluster": "Jeho cluster",
}
P135 = {
"Its {0} (only to read: it is not put back)": "Jeho {0} (jen ke čtení: neobnovuje se)",
"{0}, slot {1}, the other node {2}": "{0}, slot {1}, druhý uzel {2}",
}
R135 = {}
S135.update({
"Save this copy to the machine you are sitting at. It is the whole database as it was when the copy was made, with the key that opens the tokens inside the downloaded file: one file that is all of it, to be kept as safely as the key.":
"Uložit tuto kopii do počítače, u kterého sedíte. Je to celá databáze, jak byla v okamžiku kopie, a ve staženém souboru je i klíč, který otevírá tokeny: jeden soubor, ve kterém je všechno – uchovávejte ho stejně bezpečně jako klíč.",
})
S135.update({
"A node is restarting or the web address is moving to the other node - asking again…": "Uzel se restartuje nebo se webová adresa přesouvá na druhý uzel – ptám se znovu…",
"the server could not be reached": "server není dostupný",
})
P135.update({"the server did not answer in {0} s": "server neodpověděl do {0} s"})
S135.update({"How far": "Průběh"})
P135.update({"{0} % · {1} of {2} node(s) done": "{0} % · hotovo {1} z {2} uzlů"})
S135.update({
"RADIUS and the ports": "RADIUS a porty",
"What it calls itself": "Jak se uzel jmenuje",
"Its copies of the database": "Jeho kopie databáze",
"Writing down more (debug)": "Podrobnější log (debug)",
"Others": "Ostatní",
"its own": "vlastní",
"the machine’s own name": "vlastní jméno stroje",
"every address": "všechny adresy",
"(empty)": "(prázdné)",
"Change the cluster’s value": "Změnit hodnotu clusteru",
"Back to the cluster’s value": "Zpět na hodnotu clusteru",
"The whole cluster": "Celý cluster",
"A value marked “its own” is that node’s alone; the others take the cluster’s. The ports, the address RADIUS listens on and the API port take effect when the node reads its settings again (within seconds); the RADIUS clients must send to the port the node listens on.":
"Hodnota označená „vlastní“ patří jen tomu uzlu; ostatní berou hodnotu clusteru. Porty, adresa, na které RADIUS poslouchá, a port API platí, jakmile si uzel znovu načte nastavení (do pár vteřin); RADIUS klienti musí posílat na port, na kterém uzel poslouchá.",
"the cluster": "cluster",
})
P135.update({
"For {0}": "Pro {0}",
"Change it for {0}": "Změnit pro {0}",
"The cluster’s value: {0} has none of its own.": "Hodnota clusteru: {0} nemá vlastní.",
"Empty: the built-in default ({0}).": "Prázdné: výchozí hodnota ({0}).",
"Empty: the cluster’s value ({0}).": "Prázdné: hodnota clusteru ({0}).",
"{0} only": "jen {0}",
"{0} · {1}": "{0} · {1}",
})
S135.update({"the cluster (every node without its own)": "cluster (každý uzel bez vlastní hodnoty)"})
S135.update({
"Everything else in Settings is the cluster's and goes to every node. These belong to one machine: the address and ports RADIUS listens on, the port the pages ask the daemon on, the name it greets mail servers with and the name isemon files it under, its own copies of the database (whether, when, how many - each node keeps them on its own disk), and the debug switches. Each node shows the value in effect on it: its own, marked, or the cluster's, dimmed.":
"Všechno ostatní v Nastavení patří clusteru a platí na všech uzlech. Tato nastavení patří jednomu stroji: adresa a porty, na kterých poslouchá RADIUS, port, na kterém se stránky ptají démona, jméno, kterým se představuje mailovým serverům, a jméno, pod kterým ho eviduje isemon, jeho vlastní kopie databáze (zda, kdy a kolik – každý uzel je drží na svém disku) a přepínače ladění. U každého uzlu je vidět hodnota, která na něm platí: vlastní, označená, nebo hodnota clusteru, ztlumená.",
"A copy of the database every day": "Každý den kopie databáze",
"Made at": "Kdy se dělá",
"Copies kept": "Uchovávaných kopií",
"RADIUS listens on the address": "RADIUS poslouchá na adrese",
"The name isemon files it under": "Jméno, pod kterým ho eviduje isemon",
"config.json": "config.json",
})
P135.update({
"Set in /etc/otp/config.json of {0} (no value of the cluster’s is saved for it). Changed here, it is saved as the node’s own and takes over.":
"Nastaveno v /etc/otp/config.json uzlu {0} (cluster pro to nemá uloženou vlastní hodnotu). Změna zde se uloží jako vlastní hodnota uzlu a převezme to.",
})
S135.update({"Read it again": "Načíst znovu", "reading…": "načítám…"})
P135.update({
"The whole firewall on {0} (read only)": "Celý firewall na {0} (jen ke čtení)",
"The filter table as iptables-save shows it, read {0}. The marked lines are otp's (the chain OTP-IN and the jump to it); the rest are yours, and otp never changes them. ":
"Tabulka filter, jak ji ukazuje iptables-save, načtená {0}. Zvýrazněné řádky patří otp (řetězec OTP-IN a skok do něj); ostatní jsou vaše a otp je nikdy nemění. ",
})
