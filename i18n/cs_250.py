# 1.0.240: SSH keys of every user who may sign in; the console at login for normal users too.
S250 = {
 "SSH keys": "SSH klíče",
 "The keys that may sign in to each node over SSH - as root or as a user who may sign in there: made here, added or taken away.":
  "Klíče, kterými se lze přes SSH přihlásit na každý uzel – jako root nebo jako uživatel, který se tam smí přihlásit: vytvořené tady, přidané nebo odebrané.",
 "The keys that may sign in to each node over SSH - as root (the lines of /root/.ssh/authorized_keys) or as any user who may sign in there (their own ~/.ssh/authorized_keys, written as they are), read from every node. A key made here is shown once, to be kept by you, and kept nowhere on the server; one of your own is put on by its public half - on every node or on one. Every change is written into Events.":
  "Klíče, kterými se lze přes SSH přihlásit na každý uzel – jako root (řádky /root/.ssh/authorized_keys) nebo jako kterýkoli uživatel, který se tam smí přihlásit (jeho vlastní ~/.ssh/authorized_keys, zapsaný jako on), načtené z každého uzlu. Klíč vytvořený tady se ukáže jednou, uschováte si ho vy a na serveru se neuchovává nikde; vlastní klíč se přidá svou veřejnou polovinou – na všechny uzly nebo na jeden. Každá změna se zapíše do Událostí.",
 "Whose keys": "Čí klíče",
 "Only root: no other user who may sign in (a login shell, UID 1000 and up) is on the nodes.":
  "Jen root: na uzlech není jiný uživatel, který se smí přihlásit (přihlašovací shell, UID od 1000).",
 "Keys that may sign in as": "Klíče, kterými se lze přihlásit jako",
 "A key for": "Klíč pro",
 "The user": "Uživatel",
 "may sign in here": "se tu smí přihlásit",
 "not on this node": "na tomto uzlu není",
 "not yet": "zatím ne",
 "For normal users too: they land in it through sudo, after their own password - only those who may become root with sudo (wheel); anybody else gets a line saying so and the ordinary shell. In Events their changes are marked with their name. On the server: otp --console-users \"alice bob\" (or * or none).":
  "I pro běžné uživatele: dostanou se do ní přes sudo, po zadání vlastního hesla – jen ti, kdo se smí přes sudo stát rootem (wheel); ostatní dostanou řádek s vysvětlením a obyčejný shell. V Událostech jsou jejich změny označené jejich jménem. Na serveru: otp --console-users \"alice bob\" (nebo * či none).",
 "normal users:": "běžní uživatelé:",
 "nobody": "nikdo",
 "every one": "všichni",
 "these…": "tito…",
}
P250 = {
 "root, or one of the {0} users who may sign in on the nodes (a login shell, UID 1000 and up) - their own ~/.ssh/authorized_keys, written as they are.":
  "root, nebo jeden z {0} uživatelů, kteří se smí přihlásit na uzly (přihlašovací shell, UID od 1000) – jejich vlastní ~/.ssh/authorized_keys, zapsaný jako oni.",
 "No key lets {0} in over SSH on {1}.": "Žádný klíč nepustí {0} přes SSH na {1}.",
 "Add a key for {0}": "Přidat klíč pro {0}",
 "Make a key for {0}": "Vytvořit klíč pro {0}",
 "A fresh pair is made here. Its private half is shown to you once, to download or copy, and kept nowhere; its public half goes onto {0}.":
  "Tady se vytvoří nový pár. Soukromá polovina se vám ukáže jednou, ke stažení nebo zkopírování, a nikde se neuchovává; veřejná polovina se dá na {0}.",
 "This is the only time it is shown. Whoever holds it signs in to {0} as {1}.":
  "Zobrazí se jen tentokrát. Kdokoli ho má, přihlásí se na {0} jako {1}.",
 "Then, on your machine: ssh -i {0} {1}@…": "Potom na svém počítači: ssh -i {0} {1}@…",
}
