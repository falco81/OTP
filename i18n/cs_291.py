# 1.0.291: moving the database onto the server of this node's otp-db-agent and off it.
S291 = {
    'This node is one of a cluster (replicated - each node’s database on a server of its own, looked after by its agent, the two replicating): its database is the cluster’s. Moving it - to another engine, another server or back onto this machine - would break the replication and leave the other node on its own.':
        'Tento uzel je součástí clusteru (replikovaný – databáze každého uzlu na vlastním serveru, o který se stará jeho agent, a oba servery se replikují): jeho databáze patří clusteru. Přesunout ji – na jiný typ databáze, na jiný server nebo zpět na tento stroj – by přerušilo replikaci a druhý uzel by zůstal sám.',
    'Switch the replication off: Settings → High availability → Switch it off…, then as root otp --ha-standalone --yes on both nodes.':
        'Vypněte replikaci: Nastavení → Vysoká dostupnost → Vypnout…, pak jako root otp --ha-standalone --yes na obou uzlech.',
    'Then move the database here: Settings → The database → Move to another database.':
        'Potom databázi přesuňte zde: Nastavení → Databáze → Přesun do jiné databáze.',
    'Then build the cluster again: Settings → High availability → Making it two.':
        'Potom cluster znovu sestavte: Nastavení → Vysoká dostupnost → Jak z jednoho udělat dva.',
    'Make it for me':
        'Udělat to za mě',
    'The server of this node’s database agent (':
        'Server databázového agenta tohoto uzlu (',
    'the agent makes the database and the account there and lets this node in - no administrator’s password typed anywhere.':
        'agent tam vytvoří databázi a účet a povolí přístup tomuto uzlu – heslo správce se nikde nezadává.',
    'Make the database and the account for me':
        'Vytvořit databázi a účet za mě',
    'made by its agent':
        'vytvořil to jeho agent',
    'Encryption is that server’s own: after the move, Database → TLS turns it on there (verify-full, its certificate from otp’s authority put in by its agent).':
        'Šifrování patří tomu serveru: po přesunu ho tam zapne Databáze → TLS (verify-full, certifikát od certifikační autority otp nasadí jeho agent).',
    'What its agent did:':
        'Co jeho agent udělal:',
    'onto the server of this node’s database agent: otp looks after it from the restart on. Then Database → TLS: verify-full, its certificate from otp’s authority put in by the agent':
        'na server databázového agenta tohoto uzlu: od restartu se o něj stará otp. Potom Databáze → TLS: verify-full, certifikát od certifikační autority otp nasadí agent',
    'the database leaves the server of this node’s database agent: once the config file is switched, the agent is let go and told this node leaves it - otp asks nothing of it any more and its server leaves this page. To have it looked after again: connect its agent again (a new join code), then move back':
        'databáze opustí server databázového agenta tohoto uzlu: jakmile se přepne konfigurační soubor, agent se uvolní a dostane zprávu, že ho tento uzel opouští – otp po něm už nic nechce a jeho server z této stránky zmizí. Aby se o něj otp znovu staral: připojte jeho agenta znovu (nový kód pro připojení) a databázi přesuňte zpět',
    "this node is one of a cluster (replicated - each node's database on a server of its own, looked after by its agent, the two replicating): its database is the cluster's. Moving it - to another engine, another server or back onto this machine - would break the replication and leave the other node on its own. Switch the replication off first (Settings → High availability), then otp --ha-standalone --yes on both nodes; move it; build the cluster again.":
        'tento uzel je součástí clusteru (replikovaný – databáze každého uzlu na vlastním serveru, o který se stará jeho agent, a oba servery se replikují): jeho databáze patří clusteru. Přesunout ji – na jiný typ databáze, na jiný server nebo zpět na tento stroj – by přerušilo replikaci a druhý uzel by zůstal sám. Nejdřív vypněte replikaci (Nastavení → Vysoká dostupnost), pak otp --ha-standalone --yes na obou uzlech; přesuňte ji; cluster znovu sestavte.',
    "only the server of this node's database agent is made by otp itself: give an administrator of that server instead":
        'otp sám vytvoří databázi jen na serveru databázového agenta tohoto uzlu: zadejte místo toho správce toho serveru',
}
P291 = {
    'its agent did not make it: {0}':
        'jeho agent ji nevytvořil: {0}',
    'otp-db-agent at {0} no longer looks after this node\'s database (it is {1} now): db_admin is local again; {2}':
        'otp-db-agent na {0} se už nestará o databázi tohoto uzlu (ta je teď {1}): db_admin je znovu local; {2}',
}
