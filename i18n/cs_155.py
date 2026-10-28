# 1.0.106: a node given a new address, put right in place.
S155 = {
 "The addresses of the two nodes": "Adresy obou uzlů",
 "Replication reaches the other node by its address, kept in three places on each node: config.json, its subscription and the line of pg_hba.conf that lets the other in. When an address changes, tell it here - on the node whose address did <b>not</b> change: it puts its side right and tells the other node, which does its part by itself. Names of the nodes are changed under Each node's own settings; the whole guide is docs/renaming-and-readdressing.md.": "Replikace hledá druhý uzel podle adresy, kterou má každý uzel na třech místech: v config.json, ve svém odběru (subscription) a v řádku pg_hba.conf, který druhý uzel pouští dovnitř. Když se adresa změní, zadejte ji tady – na uzlu, jehož adresa se <b>nezměnila</b>: opraví svou stranu a řekne to druhému uzlu, který svou část udělá sám. Jména uzlů se mění v Nastavení jednotlivých uzlů; celý návod je v docs/renaming-and-readdressing.md.",
 "The other node is at": "Druhý uzel je na",
 "Save the new addresses": "Uložit nové adresy",
 "Change the addresses of the cluster?": "Změnit adresy clusteru?",
 "Change them": "Změnit",
 "The addresses of the cluster": "Adresy clusteru",
 "this node’s address is not on this machine": "adresa tohoto uzlu na tomto stroji není",
 "Start the steps again": "Spustit kroky znovu",
 "nothing to change: both addresses are as this node has them": "není co měnit: obě adresy jsou takové, jaké je uzel má",
 "this node does not replicate": "tento uzel nereplikuje",
 "the two nodes cannot have one address": "dva uzly nemůžou mít jednu adresu",
 "the other node was told and puts its side right by itself (within seconds)": "druhému uzlu bylo řečeno a svou stranu opraví sám (během vteřin)",
}
P155 = {
 "This node ({0}) is reached at": "Tento uzel ({0}) je dosažitelný na",
 "This machine has: {0}": "Tento stroj má: {0}",
 "pg_hba.conf lets the other node in from {0}": "pg_hba.conf pouští druhý uzel z {0}",
 "pg_hba.conf lets the other node in from {0} (was {1})": "pg_hba.conf pouští druhý uzel z {0} (dřív {1})",
 "pg_hba.conf already lets {0} in": "pg_hba.conf už {0} pouští",
 "ha_peer = {0} (was {1})": "ha_peer = {0} (dřív {1})",
 "ha_address = {0} (was {1})": "ha_address = {0} (dřív {1})",
 "this node takes the other's rows from {0} now": "tento uzel teď bere řádky druhého z {0}",
 "Last told by {0} ({1}): {2}": "Naposledy řekl {0} ({1}): {2}",
 "Told by {0}, it could not be done: {1}": "Řekl {0}, ale nešlo to: {1}",
 "{0} reaches this node as {1}, which its certificate did not name: a new one is made": "{0} hledá tento uzel jako {1}, což jeho certifikát neuváděl: vystavuje se nový",
 "{0}: the addresses of the cluster changed on {1} - {2}": "{0}: adresy clusteru se na {1} změnily – {2}",
 "config.json says this node is reached at {0}, which is not an address of this machine any more. If it moved, put its new address above and save here - or, better, on the other node as the other node’s address.": "config.json říká, že tento uzel je na {0}, což už není adresa tohoto stroje. Pokud se přesunul, zadejte jeho novou adresu výše a uložte zde – nebo lépe na druhém uzlu jako adresu druhého uzlu.",
}
R155 = {
 "This node: {0} · the other node: {1}<br>This node’s pg_hba.conf, its subscription and its config.json are put right now, and the other node is told when it can be reached. Replication catches up by itself.": "Tento uzel: {0} · druhý uzel: {1}<br>pg_hba.conf, odběr a config.json tohoto uzlu se opraví hned a druhému uzlu se to řekne, jakmile bude dosažitelný. Replikace se dorovná sama.",
}
