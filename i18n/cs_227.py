# 1.0.211: the HA audit of every pane - one thing at a time on the cluster, the database pane's guards.
S227 = {
 "this node is one of a cluster: the database and its account are not set up from here - the other node uses that account too":
  "tento uzel je součástí clusteru: databáze a její účet se odsud nenastavují - druhý uzel ten účet používá také",
 "the other node is not answering: restarting PostgreSQL here would leave nothing to sign people in - bring it back first":
  "druhý uzel neodpovídá: restart PostgreSQL tady by nenechal nic, co by přihlašovalo - nejdřív ho vraťte do provozu",
 "the system is being updated": "probíhá aktualizace systému",
 "otp is being upgraded": "probíhá upgrade otp",
 "The other node reaches the database at the new address (its db_host and pg_hba.conf are changed by hand)":
  "Druhý uzel se k databázi dostane na nové adrese (jeho db_host a pg_hba.conf jsou upravené ručně)",
 "The nodes share one database: a new address of this node is not carried to the other node from here.":
  "Uzly sdílejí jednu databázi: nová adresa tohoto uzlu se odsud na druhý uzel nepřenese.",
}
P227 = {
 "the nodes share this database server: restarted, both stop - restart it at a quiet time as root:  systemctl restart {0}":
  "uzly sdílejí tento databázový server: po restartu se zastaví oba - restartujte ho v klidné době jako root:  systemctl restart {0}",
 "{0} is restarting its PostgreSQL now - one at a time": "{0} právě restartuje svůj PostgreSQL - jeden po druhém",
 "{0} is going on on {1} - one at a time": "na {1} právě probíhá: {0} - jedno po druhém",
 "{0} is going on on {1} - wait for it to end": "na {1} právě probíhá: {0} - počkejte, až skončí",
 "{0} - one thing at a time, so that a node always answers": "{0} - jedno po druhém, aby vždy nějaký uzel odpovídal",
 "{0} - wait for it to end": "{0} - počkejte, až skončí",
 "{0} is changing its network": "{0} mění svou síť",
 "the nodes share one database: the other node reaches it (db_host) or is let into it (pg_hba.conf) at {0} - that is not moved from here. Change it there by hand, then tick that it is done":
  "uzly sdílejí jednu databázi: druhý uzel se k ní připojuje (db_host) nebo je do ní vpuštěn (pg_hba.conf) na adrese {0} - to se odsud nepřesune. Změňte to tam ručně a pak zaškrtněte, že je hotovo",
 "the other node's db_host and pg_hba.conf at {0}: changed by hand, as ticked": "db_host a pg_hba.conf druhého uzlu na {0}: změněno ručně, jak je zaškrtnuto",
 "No other node is answering in service: while {0} is in maintenance nobody can sign in to the VPN. Its pages go on working.":
  "Žádný jiný uzel v provozu neodpovídá: dokud je {0} v údržbě, nikdo se do VPN nepřihlásí. Jeho stránky fungují dál.",
 "{0} - its side as it was": "{0} - jeho strana zůstala, jak byla",
 "the sign-ins and the accounting cannot listen on one port ({0}) on {1}": "přihlašování a accounting nemohou naslouchat na jednom portu ({0}) na {1}",
}
