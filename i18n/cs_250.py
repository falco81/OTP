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
S250.update({
 "PEM files - the certificate, its key, the chain, the root, in any order or all in one - or one PFX / PKCS#12 file. An RSA and an ECDSA certificate of the same names together (both keys in the PEM, or two PFX files): both are put in, the ECDSA one beside - nginx gives each client the one it takes. A request waits here: the certificate the authority sent back is enough, its key is here.":
  "Soubory PEM – certifikát, jeho klíč, řetěz, kořen, v libovolném pořadí nebo vše v jednom – nebo jeden soubor PFX / PKCS#12. Certifikát RSA a ECDSA se stejnými jmény zároveň (oba klíče v PEM, nebo dva soubory PFX): vloží se oba, ECDSA vedle – nginx dá každému klientovi ten, který bere. Čeká tu žádost: stačí certifikát, který autorita poslala zpět, jeho klíč je tady.",
 "PEM files - the certificate, its key, the chain, the root, in any order or all in one - or one PFX / PKCS#12 file. An RSA and an ECDSA certificate of the same names together (both keys in the PEM, or two PFX files): both are put in, the ECDSA one beside - nginx gives each client the one it takes. The key has to come with it.":
  "Soubory PEM – certifikát, jeho klíč, řetěz, kořen, v libovolném pořadí nebo vše v jednom – nebo jeden soubor PFX / PKCS#12. Certifikát RSA a ECDSA se stejnými jmény zároveň (oba klíče v PEM, nebo dva soubory PFX): vloží se oba, ECDSA vedle – nginx dá každému klientovi ten, který bere. Klíč musí přijít s ním.",
 "two PFX / PKCS#12 files at most - an RSA and an ECDSA one": "nejvýš dva soubory PFX / PKCS#12 – jeden RSA a jeden ECDSA",
 "Which certificate": "Který certifikát",
 "Both (.zip)": "Oba (.zip)",
 "Both: one .zip with the two files in the format below - each key locked with the same password.":
  "Oba: jeden .zip se dvěma soubory ve formátu níže – každý klíč zamčený stejným heslem.",
 "there is no second (ECDSA) certificate beside this one": "vedle tohoto certifikátu není druhý (ECDSA)",
})
P250.update({
 "RSA ({0})": "RSA ({0})",
 "ECDSA ({0})": "ECDSA ({0})",
 "two certificates come with two keys - one RSA, one ECDSA ({0} key(s) came)": "dva certifikáty přicházejí se dvěma klíči – jeden RSA, jeden ECDSA (přišlo klíčů: {0})",
 "two certificates: one with an RSA key and one with an ECDSA key (these are {0})": "dva certifikáty: jeden s klíčem RSA a jeden s klíčem ECDSA (tyto jsou {0})",
 "the two certificates are not of the same names ({0} / {1})": "ty dva certifikáty nemají stejná jména ({0} / {1})",
})
S250.update({
 "Click to select it all": "Kliknutím označíte celý",
 "the key is on the clipboard": "klíč je ve schránce",
 "the token is on the clipboard": "token je ve schránce",
 "Put it into the balancer now: NetScaler - the rewrite action otp_key; F5 - the iRule; nginx - proxy_set_header. Lost, make a new one: the old one stops at once.":
  "Vložte ho do balanceru hned: NetScaler – rewrite action otp_key; F5 – iRule; nginx – proxy_set_header. Ztracený? Vytvořte nový: starý hned přestane platit.",
})
R250 = {
 "Its <b>public</b> half goes into <code>~{0}/.ssh/authorized_keys</code> of {1} - written as {2}, so that the folder and the file are theirs. The <b>private</b> half is never kept here: it is shown to you once, to hand over.":
  "Jeho <b>veřejná</b> část se zapíše do <code>~{0}/.ssh/authorized_keys</code> na {1} – zapisuje ji {2} sám, takže složka i soubor jsou jeho. <b>Soukromá</b> část se zde nikdy neukládá: zobrazí se vám jen jednou, k předání.",
}
