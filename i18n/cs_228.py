# 1.0.213: the join of a cluster - the first node made ready, the firewall, the check before joining.
S228 = {
 "The second node’s address": "Adresa druhého uzlu",
 "Let into PostgreSQL here (pg_hba.conf) and through this node’s firewall for a day - for good once it has joined.":
  "Pustí se sem do PostgreSQL (pg_hba.conf) a přes firewall tohoto uzlu na jeden den – natrvalo, jakmile se připojí.",
 "This machine’s address when PostgreSQL runs here.": "Adresa tohoto stroje, když tu běží PostgreSQL.",
 "Let it listen on the network - PostgreSQL is restarted for it (a few seconds without sign-ins)":
  "Ať naslouchá na síti – PostgreSQL se kvůli tomu restartuje (pár sekund bez přihlašování)",
 "This node, made ready": "Tento uzel, připravený",
 "This node then opens the cluster’s database and takes its key: what it holds now - its own database, accounts and tokens - is no longer used. Join a node just installed.":
  "Tento uzel pak otevře databázi clusteru a převezme její klíč: co teď drží – vlastní databáze, účty a tokeny – se už nepoužije. Připojujte čerstvě nainstalovaný uzel.",
 "none chosen yet": "zatím nevybrán",
 "otp-join-….json from the first node - drop it here, or press to choose it": "otp-join-….json z prvního uzlu – přetáhněte ho sem, nebo klikněte a vyberte",
 "Shown once on the first node as the bundle was made.": "Ukázaná jednou na prvním uzlu při vytvoření balíčku.",
 "Check it": "Ověřit",
 "Ready to join": "Připraveno k připojení",
 "Not yet": "Ještě ne",
 "this node is the first of a cluster of one shared database (ha_mode = shared)": "tento uzel je první v clusteru nad jednou sdílenou databází (ha_mode = shared)",
}
P228 = {
 "PostgreSQL here listens on this machine alone (listen_addresses = {0}): the second node could not reach it.":
  "PostgreSQL tady naslouchá jen na tomto stroji (listen_addresses = {0}): druhý uzel by se k němu nedostal.",
 "PostgreSQL here listens on the network (listen_addresses = {0})": "PostgreSQL tady naslouchá na síti (listen_addresses = {0})",
 "PostgreSQL listens on the network (listen_addresses = {0})": "PostgreSQL naslouchá na síti (listen_addresses = {0})",
 "pg_hba.conf lets {0} in: {1}": "pg_hba.conf pouští {0}: {1}",
 "this node's firewall lets {0} in for the join (a day at most; for good once it has joined)":
  "firewall tohoto uzlu pouští {0} kvůli připojení (nejvýš na den; natrvalo, jakmile se připojí)",
 "the bundle opens: the cluster {0}, made on {1} ({2})": "balíček jde otevřít: cluster {0}, vytvořený na {1} ({2})",
 "its database answers from here: {0}, {1} row(s)": "jeho databáze odsud odpovídá: {0}, {1} řádků",
 "the bundle: {0}": "balíček: {0}",
 "the node a cluster is being made with ({0}): let in for the join, until {1} at most":
  "uzel, se kterým se vytváří cluster ({0}): puštěn kvůli připojení, nejdéle do {1}",
 "PostgreSQL here listens on this machine alone (listen_addresses = {0}): the second node could not reach it. Tick that it may listen on the network - it is restarted for it":
  "PostgreSQL tady naslouchá jen na tomto stroji (listen_addresses = {0}): druhý uzel by se k němu nedostal. Zaškrtněte, že smí naslouchat na síti – kvůli tomu se restartuje",
}
