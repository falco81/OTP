# 1.0.289: the database on a server of its own (otp-db-agent) - the Czech of isemon's kit (acme's
# web/lang/cs.json for the feature), in otp's names.
S289 = {
    'Database server':
        'Databázový server',
    'The database servers: what this card does reaches them through their agents, and each answers.':
        'Databázové servery: co tato karta dělá, se k nim dostává přes jejich agenty, a každý odpovídá.',
    'The database servers: what this card does reaches them through their agents - not every one answers now.':
        'Databázové servery: co tato karta dělá, se k nim dostává přes jejich agenty – teď ale neodpovídají všechny.',
    'Done on them:':
        'Co se na nich dělá:',
    'heard from':
        'ozval se',
    'agent':
        'agent',
    'its agent does not answer':
        'jeho agent neodpovídá',
    'not heard from lately':
        'poslední dobou se neozval',
    'its database does not run':
        'jeho databáze neběží',
    'not looked at yet':
        'zatím nezjištěno',
    ' - a server no agent looks after':
        ' – server, o který se nestará žádný agent',
    'otp only connects to it: its certificate, its settings and their restart are its administrator’s. With otp-db-agent on that server otp looks after it as it would one on this machine - and the meter in the header shows it.':
        'otp se k němu jen připojuje: jeho certifikát, nastavení i restart má na starosti jeho správce. S otp-db-agent na tom serveru se o něj otp stará jako o databázi na tomto stroji – a ukazuje ho i měřič v záhlaví.',
    'Connect a database server…':
        'Připojit databázový server…',
    'Connect a database server':
        'Připojit databázový server',
    'This node’s database is on':
        'Databáze tohoto uzlu je na',
    'This node’s database is still the file on this machine':
        'Databáze tohoto uzlu je zatím soubor na tomto stroji',
    'This node’s database is still on this machine':
        'Databáze tohoto uzlu je zatím na tomto stroji',
    '- not the agent’s server':
        '– to není server agenta',
    'Looked after by otp-db-agent at':
        'Spravuje ho otp-db-agent na',
    'The agent’s server is ready, but this node uses another database server. Move the database onto the agent’s server to have it looked after.':
        'Server agenta je připravený, ale tento uzel používá jiný databázový server. Přesuňte databázi na server agenta, aby se o ni otp staral.',
    'The agent’s server is ready: move this node’s database onto it - a copy made first, every row copied and checked, otp started again on it.':
        'Server agenta je připravený: přesuňte na něj databázi tohoto uzlu – nejdřív se udělá kopie, každý řádek se zkopíruje a zkontroluje a otp se na něm znovu spustí.',
    'Move it onto the database server…':
        'Přesunout ji na databázový server…',
    'Not looked at yet - it is looked at every 30 s.':
        'Zatím nezjištěno – zjišťuje se každých 30 s.',
    'Ask the agent now what its server is like, rather than within 30 s.':
        'Zeptat se agenta na stav jeho serveru hned, ne až do 30 s.',
    'Restart the database…':
        'Restartovat databázi…',
    'The database server restarted by its agent, and waited for. Every connection to it is cut for a few seconds.':
        'Databázový server restartuje jeho agent a počká na něj. Všechna spojení k němu se na několik sekund přeruší.',
    'Restart the database server?':
        'Restartovat databázový server?',
    'Give MariaDB a new certificate':
        'Dát MariaDB nový certifikát',
    'Turn TLS on':
        'Zapnout TLS',
    'MariaDB given a certificate from otp’s own authority by its agent (restarted the first time, reloaded after) - renewed by itself 45 days before it ends. Then Database → TLS moves this node’s connection to verify-full.':
        'Agent dá MariaDB certifikát od vlastní autority otp (poprvé s restartem, potom jen s načtením) – obnovuje se sám 45 dní před vypršením. Potom Databáze → TLS převede spojení tohoto uzlu na verify-full.',
    'Forget the agent…':
        'Zapomenout agenta…',
    'This node goes back to looking after a database on this machine only. The agent keeps this node’s certificate until it is taken away there (otp_db_agent.py --forget NODE); the database and its data are not touched.':
        'Tento uzel se vrátí ke správě databáze jen na tomto stroji. Agent si certifikát tohoto uzlu ponechá, dokud ho tam neodeberete (otp_db_agent.py --forget UZEL); databáze a její data zůstanou nedotčené.',
    'Forget the database agent?':
        'Zapomenout agenta databáze?',
    'otp no longer renews the database server’s certificate, changes its settings or restarts it, and its row leaves the meter. The database itself is not touched, and this node goes on using it. Connected again with a new join code.':
        'otp už nebude obnovovat certifikát databázového serveru, měnit jeho nastavení ani ho restartovat a jeho řádek zmizí z měřiče. Samotná databáze zůstane nedotčená a tento uzel ji dál používá. Znovu se připojí novým připojovacím kódem.',
    'this node’s':
        'tohoto uzlu',
    'Agent':
        'Agent',
    'Connections':
        'Spojení',
    'Its data’s disk':
        'Disk s jeho daty',
    'RAM':
        'RAM',
    'Agent’s certificate ends':
        'Certifikát agenta vyprší',
    'Node’s client certificate ends':
        'Klientský certifikát uzlu vyprší',
    'looked at now':
        'zjištěno',
    'forgotten: this node looks after a database on this machine only':
        'zapomenuto: tento uzel spravuje jen databázi na tomto stroji',
    'a join code starts with ODBA1. - the one the database server printed':
        'připojovací kód začíná ODBA1. – ten, který vypsal databázový server',
    'cut short or mistyped: copy all of it, from ODBA1. to the end':
        'zkrácený nebo překlepnutý: zkopírujte ho celý, od ODBA1. až do konce',
    'On the database server':
        'Na databázovém serveru',
    'The join code':
        'Připojovací kód',
    'Connecting':
        'Připojení',
    'I have the code':
        'Kód mám',
    'Connect it':
        'Připojit',
    'Move the database onto it…':
        'Přesunout na něj databázi…',
    'otp-db-agent on the database server looks after it for otp':
        'otp-db-agent na databázovém serveru se o něj stará za otp',
    'Its certificate from otp’s own authority and its renewal, pg_hba.conf, its settings and restart, the replication, its firewall - the closed set of things the root helper does on this machine, and nothing else. Every request goes over HTTPS with certificates both ways and is signed; the agent does not run as root on the network side.':
        'Jeho certifikát od vlastní autority otp a jeho obnova, pg_hba.conf, nastavení a restart, replikace, firewall – uzavřený výčet toho, co na tomto stroji dělá pomocník s právy roota, a nic víc. Každý požadavek jde přes HTTPS s certifikáty na obou stranách a je podepsaný; síťová strana agenta neběží jako root.',
    'Which database':
        'Která databáze',
    'Standalone, or the two servers of high availability replicating':
        'Samostatně, nebo dva servery vysoké dostupnosti, které se replikují',
    'Standalone only':
        'Jen samostatně',
    'On the database server, as root':
        'Na databázovém serveru jako root',
    'Copy otp’s installation folder there (the same version), then install the database and the agent:':
        'Zkopírujte tam instalační složku otp (stejnou verzi) a nainstalujte databázi a agenta:',
    'PostgreSQL 16 installed, initialised, listening, wal_level = logical; the database and its account; the nodes let in (pg_hba.conf, firewalld); the agent. It prints a join code at the end.':
        'PostgreSQL 16 se nainstaluje, inicializuje, poslouchá na síti, wal_level = logical; databáze a její účet; uzly mají přístup (pg_hba.conf, firewalld); agent. Na konci vypíše připojovací kód.',
    'MariaDB installed and secured; the database and its account for the nodes; the agent. It prints a join code at the end.':
        'MariaDB se nainstaluje a zabezpečí; databáze a její účet pro uzly; agent. Na konci vypíše připojovací kód.',
    'A database server installed already: the agent alone -':
        'Databázový server už nainstalovaný: jen agent –',
    'The code runs out in an hour; a new one any time:':
        'Kód platí hodinu; nový kdykoli:',
    '--otp-node is the address the database server sees this node by:':
        '--otp-node je adresa, pod kterou databázový server vidí tento uzel:',
    'Printed by install.sh --db-server on the database server (or otp_db_agent.py --new-code). One hour, once.':
        'Vypíše ho install.sh --db-server na databázovém serveru (nebo otp_db_agent.py --new-code). Platí hodinu a jednou.',
    'The agent’s address (optional)':
        'Adresa agenta (nepovinné)',
    'Only when this node reaches the agent by another address than the code says - a NAT, another network. HOST or HOST:PORT.':
        'Jen když tento uzel dosáhne na agenta jinou adresou, než uvádí kód – NAT, jiná síť. HOST nebo HOST:PORT.',
    'Use it as this node’s database':
        'Použít ho jako databázi tohoto uzlu',
    'This node’s database is on that server (or is moved there next): otp looks after the server it connects to. The address below is the one the database is reached at - the agent’s when left empty.':
        'Databáze tohoto uzlu je na tom serveru (nebo se tam hned potom přesune): otp se stará o server, ke kterému se připojuje. Adresa níže je ta, na které je databáze dostupná – prázdná znamená adresu agenta.',
    'The database’s address, as this node reaches it':
        'Adresa databáze, jak ji vidí tento uzel',
    'paste the code - it is checked as it is pasted':
        'vložte kód – zkontroluje se hned při vložení',
    'otp-db-agent at':
        'otp-db-agent na',
    'Reaching the agent, its certificate checked against the code':
        'Spojení s agentem, jeho certifikát ověřený podle kódu',
    'Certificates from otp’s own authority, both ways':
        'Certifikáty od vlastní autority otp, oběma směry',
    'Looking at the server':
        'Zjištění stavu serveru',
    'Nothing was changed on this node. Put right what it says - a new code if this one ran out or was used - and connect again.':
        'Na tomto uzlu se nic nezměnilo. Napravte, co se píše – nový kód, pokud tento vypršel nebo už byl použit – a připojte znovu.',
    'the agent has its certificate; this node its client certificate and signing key':
        'agent má svůj certifikát; tento uzel svůj klientský certifikát a podpisový klíč',
    'Connected: this node’s database is on that server, and otp looks after it from now on.':
        'Připojeno: databáze tohoto uzlu je na tom serveru a otp se o něj od teď stará.',
    'Connected. This node’s database is not on that server yet: move it there next - Move the database onto it…':
        'Připojeno. Databáze tohoto uzlu na tom serveru zatím není: přesuňte ji tam – Přesunout na něj databázi…',
    'paste the join code first':
        'nejdřív vložte připojovací kód',
    'the agent’s address: HOST or HOST:PORT':
        'adresa agenta: HOST nebo HOST:PORT',
    'the database server is connected':
        'databázový server je připojený',
    'The database servers':
        'Databázové servery',
    'Of node':
        'Uzlu',
    'The link’s TLS':
        'TLS spojení',
    'Its agent':
        'Jeho agent',
    'lost':
        'ztraceno',
    'Each node’s database on a server of its own':
        'Databáze každého uzlu na vlastním serveru',
    'This node’s database is looked after by otp-db-agent. Replicated, each node has its own database server: this node on its own, the second node on another - the two servers replicate both ways, set up and encrypted by otp through their agents. --ha-peer is then the other database server, --ha-peer-node the other otp node.':
        'O databázi tohoto uzlu se stará otp-db-agent. Při replikaci má každý uzel svůj databázový server: tento uzel svůj, druhý uzel jiný – oba servery se replikují oběma směry a otp je přes jejich agenty nastaví i zašifruje. --ha-peer je pak druhý databázový server, --ha-peer-node druhý uzel otp.',
    'The other database server':
        'Druhý databázový server',
    'Its address: where the second node’s database runs, with its own agent.':
        'Jeho adresa: tam běží databáze druhého uzlu s vlastním agentem.',
    'The other otp node':
        'Druhý uzel otp',
    'The second otp server’s own address - let into this node’s database server too.':
        'Vlastní adresa druhého serveru otp – dostane přístup i k databázovému serveru tohoto uzlu.',
    'The second node’s name':
        'Jméno druhého uzlu',
    'On this node, as root':
        'Na tomto uzlu jako root',
    'Its agent prepares this node’s database server (wal_level, listening, pg_hba.conf for the other server and the other node), restarts it, publishes the tables and opens its firewall; the bundle for the second node is written to /root.':
        'Jeho agent připraví databázový server tohoto uzlu (wal_level, poslouchání na síti, pg_hba.conf pro druhý server a druhý uzel), restartuje ho, zveřejní tabulky a otevře jeho firewall; balíček pro druhý uzel se zapíše do /root.',
    'On the other database server, as root':
        'Na druhém databázovém serveru jako root',
    'On the second node, as root: its agent, then the join':
        'Na druhém uzlu jako root: jeho agent, potom připojení',
    'Every row is copied from this node’s server to the other one, both directions of replication set up. Then High availability → Repair encrypts the link between the two servers (verify-full) through both agents.':
        'Každý řádek se zkopíruje ze serveru tohoto uzlu na druhý a nastaví se oba směry replikace. Potom Vysoká dostupnost → Opravit zašifruje spojení mezi oběma servery (verify-full) přes oba agenty.',
    'database server':
        'databázový server',
    'its port opened by its agent to the nodes':
        'port otevřel uzlům jeho agent',
    'The database server’s own firewall (firewalld) is its administrator’s; otp lets the nodes and the other database server reach the database’s port there through its agent - when the cluster is made, and when an address changes.':
        'Vlastní firewall databázového serveru (firewalld) patří jeho správci; otp přes agenta otevře port databáze uzlům a druhému databázovému serveru – při vytvoření clusteru a při změně adresy.',
    'TLS on':
        'TLS zapnuto',
    'its agent answers':
        'jeho agent odpovídá',
    'A database server otp should look after itself (its certificate, settings, restarts, the meter)? Connect its agent first:':
        'Databázový server, o který se má otp starat sám (certifikát, nastavení, restarty, měřič)? Nejdřív připojte jeho agenta:',
    'the database server of':
        'databázový server uzlu',
    'Its agent does not answer - nothing read from it now.':
        'Jeho agent neodpovídá – teď se z něj nic nečte.',
    'Waiting to go over (replication)':
        'Čeká na přenos (replikace)',
    'The size of otp’s database':
        'Velikost databáze otp',
    'The machine':
        'Stroj',
    'The database is on a server of its own: whoever is on the network between the nodes and it reads every row going over, and can change them. Encrypt… has its agent put a certificate from otp’s own authority in, then moves each node’s connection to verify-full.':
        'Databáze je na vlastním serveru: kdokoli je v síti mezi uzly a ním, čte každý řádek, který jde přes síť, a může ho změnit. Šifrovat… nechá jeho agenta vložit certifikát od vlastní autority otp a potom převede spojení každého uzlu na verify-full.',
    'the database server - its agent does not answer':
        'databázový server – jeho agent neodpovídá',
    'Another version than otp':
        'Jiná verze než otp',
    '- upgrade the agent on the database server:':
        '- aktualizujte agenta na databázovém serveru:',
    'otp --db-agent-join - reads the join code from its standard input: paste it there, it is never put on a command line.':
        'otp --db-agent-join - čte připojovací kód ze standardního vstupu: vložte ho tam, nikdy se nedává na příkazový řádek.',
    'The client certificate of %s for its database agent ends soon':
        'Klientský certifikát uzlu %s pro agenta databázového serveru brzy vyprší',
    'it ends %s; it is renewed by itself 45 days before, and that did not work - without it the agent no longer lets the node in. Settings → The database → Database server → Renew the certificates (otp --db-agent-renew)':
        'vyprší %s; obnovuje se sám 45 dní předem, a to se nepovedlo - bez něj agent uzel nepustí. Nastavení → Databáze → Databázový server → Obnovit certifikáty (otp --db-agent-renew)',
    'The database agent of %s is another version than otp':
        'Agent databázového serveru uzlu %s má jinou verzi než otp',
    'otp-db-agent %s, otp %s - upgrade the agent on the database server: ./install.sh --db-agent (from this version of otp)':
        'otp-db-agent %s, otp %s - aktualizujte agenta na databázovém serveru: ./install.sh --db-agent (z instalace této verze otp)',
    '%s - start it on the database server %s (systemctl start otp-db-agent), then run this again':
        '%s - spusťte ho na databázovém serveru %s (systemctl start otp-db-agent) a pak to spusťte znovu',
    'PostgreSQL does not answer on the database server %s (its agent does): install it there (install.sh --db-server postgres) and start it':
        'PostgreSQL na databázovém serveru %s neodpovídá (jeho agent ano): nainstalujte ho tam (install.sh --db-server postgres) a spusťte',
    'the database server lets %s in (otp-db-agent): %s':
        'databázový server pouští %s (otp-db-agent): %s',
    'it did already':
        'pouštěl už předtím',
    'the new address is one plain address, not %r':
        'nová adresa je jedna prostá adresa, ne %r',
    'the other node is at %s now (was %s): its database server lets it in through otp-db-agent':
        'druhý uzel je teď na %s (byl na %s): jeho databázový server ho pouští přes otp-db-agent',
    "the database server's firewall was not opened to this node: %s":
        'firewall databázového serveru se pro tento uzel neotevřel: %s',
    'the firewall of the database server was not opened to this node: %s':
        'firewall databázového serveru se pro tento uzel neotevřel: %s',
    "the agent knows this node by its client certificate from otp's authority":
        'agent zná tento uzel podle jeho klientského certifikátu od autority otp',
    "the agent's certificate: the next one announced to every node":
        'certifikát agenta: další je oznámený všem uzlům',
    "the agent's certificate: the next one announced to every node, in use now":
        'certifikát agenta: další je oznámený všem uzlům a už se používá',
    "this node's client certificate":
        'klientský certifikát tohoto uzlu',
    'no join code: paste it on standard input (otp --db-agent-join -) or put it in ACME_DB_AGENT_CODE':
        'chybí připojovací kód: vložte ho na standardní vstup (otp --db-agent-join -) nebo do ACME_DB_AGENT_CODE',
    'The join code (otp_db_agent.py --new-code printed it):':
        'Připojovací kód (vypsal ho otp_db_agent.py --new-code):',
    'NOTE: the agent is otp-db-agent %s, this node otp %s - upgrade it on the database server (./install.sh --db-agent, of this version)':
        'POZOR: agent je otp-db-agent %s, tento uzel otp %s - aktualizujte ho na databázovém serveru (./install.sh --db-agent z této verze)',
    'database agent: otp-db-agent %s, otp %s - upgrade it on the database server (./install.sh --db-agent)':
        'agent databáze: otp-db-agent %s, otp %s - aktualizujte ho na databázovém serveru (./install.sh --db-agent)',
    'letting the other node in at its new address through the database agent: %s':
        'puštění druhého uzlu na jeho nové adrese přes agenta databáze: %s',
    'too many wrong join codes from %s - wait an hour':
        'příliš mnoho chybných připojovacích kódů z %s - počkejte hodinu',
    'the join was not begun with this code from here (or more than 15 minutes ago) - join again':
        'připojení nebylo s tímto kódem odsud zahájeno (nebo před víc než 15 minutami) - připojte se znovu',
    "the authorities of the node's certificate are missing":
        'chybí autority certifikátu uzlu',
    'no authority given: refused - this node would be locked out':
        'nebyla zadána žádná autorita: odmítnuto - tento uzel by se zablokoval',
    "the agent's next certificate is announced to every node joined":
        'další certifikát agenta je oznámený všem připojeným uzlům',
    'a client certificate is needed':
        'je potřeba klientský certifikát',
    'this client certificate is not one enrolled here':
        'tento klientský certifikát tu není zaregistrovaný',
    'the database agent at %s:%s cannot be reached: %s - is its port open to this node? (on the database server: firewall-cmd --permanent --add-rich-rule=\'rule family="ipv4" source address="%s" port port="%s" protocol="tcp" accept\' && firewall-cmd --reload)':
        'agent databázového serveru na %s:%s není dosažitelný: %s - je jeho port pro tento uzel otevřený? (na databázovém serveru: firewall-cmd --permanent --add-rich-rule=\'rule family="ipv4" source address="%s" port port="%s" protocol="tcp" accept\' && firewall-cmd --reload)',
    'The server of this node’s database agent (':
        'Server databázového agenta tohoto uzlu (',
    '): the agent makes the database and the account there and lets this node in - no password typed anywhere. A password is made for the account if none is typed above.':
        '): databázi a účet tam vytvoří agent a pustí k nim tento uzel – nikde se nepíše žádné heslo. Když výše žádné heslo není, účtu se nějaké vymyslí.',
    'Not the server of this node’s database agent (':
        'Toto není server databázového agenta tohoto uzlu (',
    '): once moved there, otp only connects to it. To have it looked after, connect its agent first - one agent a node, it then takes the place of this one.':
        '): po přesunu se k němu otp jen připojuje. Aby se o něj otp staralo, připojte nejdřív jeho agenta – jeden agent na uzel, nahradí tedy tohoto.',
    'The database leaves the server of this node’s database agent (':
        'Databáze odchází ze serveru databázového agenta tohoto uzlu (',
    '): once config.json is switched, the agent is let go - otp asks nothing of it any more and its server leaves this page and the meter. It keeps this node’s certificate until otp_db_agent.py --forget there; moving back means connecting it again.':
        '): jakmile se přepne config.json, agent se uvolní – otp po něm už nic nechce a jeho server zmizí z této stránky i z měřiče. Certifikát tohoto uzlu si ponechá, dokud na něm nespustíte otp_db_agent.py --forget; přesun zpět znamená připojit ho znovu.',
    'Onto the server of this node’s database agent (':
        'Na server databázového agenta tohoto uzlu (',
    '): otp looks after it from the restart on. Then Encryption to the database server: the server’s certificate from otp’s authority, and verify-full.':
        '): od restartu se o něj otp stará. Potom Šifrování k databázovému serveru: certifikát serveru od autority otp a verify-full.',
    'This node is one of a cluster and its database is on the server of the agent at ':
        'Tento uzel je součástí clusteru a jeho databáze je na serveru agenta ',
    ': another agent is not connected instead. Take the cluster apart first.':
        ': jiný agent se místo něj nepřipojí. Nejdřív cluster rozeberte.',
    'This node is connected to the agent at ':
        'Tento uzel je připojen k agentovi ',
    ' and its database is on that server. One agent a node: this one takes its place, and until the database is moved onto the new server (Move the database onto it…, next) nothing of the old server is looked after - its certificate is not renewed. The old agent keeps this node’s certificate until otp_db_agent.py --forget there.':
        ' a jeho databáze je na tom serveru. Jeden agent na uzel: tento nahradí původního a dokud se databáze nepřesune na nový server (Přesunout databázi na něj…, hned potom), o starý server se nikdo nestará – jeho certifikát se neobnovuje. Původní agent si certifikát tohoto uzlu ponechá, dokud na něm nespustíte otp_db_agent.py --forget.',
    ' already. One agent a node: this one takes its place.':
        ' už teď. Jeden agent na uzel: tento nahradí původního.',
    'It takes the place of the agent at ':
        'Nahradil agenta ',
    ' - this node’s database is still on ':
        ' – databáze tohoto uzlu je stále na ',
    ', and nothing of that server is looked after until the database is moved onto the new one. That agent keeps this node’s certificate until otp_db_agent.py --forget ':
        ' a o ten server se nikdo nestará, dokud se databáze nepřesune na nový. Tamní agent si certifikát tohoto uzlu ponechá, dokud tam nespustíte otp_db_agent.py --forget ',
    ' there.':
        '.',
    ' (one agent a node); that one keeps this node’s certificate until otp_db_agent.py --forget ':
        ' (jeden agent na uzel); ten si certifikát tohoto uzlu ponechá, dokud tam nespustíte otp_db_agent.py --forget ',
    'otp-db-agent no longer looks after this node’s database: it is not on that server any more, so nothing is asked of the agent, and its server is off the cards and the meter. The agent keeps this node’s certificate until otp_db_agent.py --forget there.':
        'otp-db-agent se už o databázi tohoto uzlu nestará: na jeho serveru už není, takže se po agentovi nic nechce a jeho server zmizel z karet i z měřiče. Agent si certifikát tohoto uzlu ponechá, dokud na něm nespustíte otp_db_agent.py --forget.',
    'To have that server looked after again, connect its agent first (a new join code), then move back.':
        'Aby se otp o ten server zase staralo, připojte nejdřív jeho agenta (nový kód pro připojení) a potom přesuňte databázi zpět.',
    "this node is one of a cluster (replicated - each node's database on a server of its own, looked after by its agent, the two replicating): its database is the cluster's. Moving it - to another engine, another server or back onto this machine - would break the replication and leave the other node on its own.":
        'tento uzel je součástí clusteru (replikovaný – databáze každého uzlu na vlastním serveru, o který se stará jeho agent, a obě se replikují): jeho databáze patří clusteru. Přesun – na jiný databázový stroj, jiný server nebo zpět na tento počítač – by replikaci rozbil a druhý uzel by zůstal sám.',
    "only a server on this machine, or the server of this node's database agent, is made by otp itself: run the SQL shown on that server, or give an administrator of it":
        'otp samo vytvoří databázi jen na serveru na tomto počítači nebo na serveru databázového agenta tohoto uzlu: spusťte na tom serveru zobrazené SQL, nebo zadejte jeho správce',
    'A new certificate for the agent (a new key, made on its server) and a new client certificate for this node, now, both from otp’s own authority - rather than when they near their end (the agent’s 60 days before, this node’s 45). Nothing stops.':
        'Nový certifikát pro agenta (s novým klíčem vytvořeným na jeho serveru) a nový klientský certifikát pro tento uzel, hned a oba od vlastní autority otp – ne až před koncem platnosti (agentův 60 dní předem, tohoto uzlu 45). Nic se nezastaví.',
    'The server is on this machine: otp can make the database and the account itself, as root - as postgres, with no password typed anywhere. A password is made for the account if none is typed above.':
        'Server je na tomto stroji: otp může databázi a účet vytvořit samo, jako root – jako postgres, bez zadávání jakéhokoli hesla. Pokud výše žádné heslo není, účtu se heslo vytvoří samo.',
    'The server is on this machine: otp can make the database and the account itself, as root - as root over its socket, with no password typed anywhere. A password is made for the account if none is typed above.':
        'Server je na tomto stroji: otp může databázi a účet vytvořit samo, jako root – jako root přes jeho socket, bez zadávání jakéhokoli hesla. Pokud výše žádné heslo není, účtu se heslo vytvoří samo.',
    'This node goes back to looking after a database on this machine only. The agent is told this node leaves it and takes it off its list (if it does not answer, it keeps this node’s certificate until otp_db_agent.py --forget NODE there); the database and its data are not touched.':
        'Tento uzel se vrátí ke správě databáze jen na tomto stroji. Agent dostane zprávu, že ho uzel opouští, a vyřadí ho ze svého seznamu (pokud neodpoví, ponechá si certifikát tohoto uzlu, dokud tam nespustíte otp_db_agent.py --forget UZEL); databáze a její data zůstanou nedotčené.',
    '): once config.json is switched, the agent is let go and told this node leaves it - otp asks nothing of it any more and its server leaves this page and the meter; moving back means connecting it again.':
        '): jakmile se přepne config.json, agent se uvolní a dostane zprávu, že ho tento uzel opouští – otp po něm už nic nechce a jeho server zmizí z této stránky i z měřiče; přesun zpět znamená připojit ho znovu.',
    'otp-db-agent no longer looks after this node’s database: it is not on that server any more, so nothing is asked of the agent, and its server is off the cards and the meter. The agent was told this node leaves it (one that did not answer keeps this node’s certificate until otp_db_agent.py --forget there).':
        'otp-db-agent se už o databázi tohoto uzlu nestará: na jeho serveru už není, takže se po agentovi nic nechce a jeho server zmizel z karet i z měřiče. Agent dostal zprávu, že ho tento uzel opouští (pokud neodpověděl, ponechá si certifikát tohoto uzlu, dokud na něm nespustíte otp_db_agent.py --forget).',
    ' and its database is on that server. One agent a node: this one takes its place, and until the database is moved onto the new server (Move the database onto it…, next) nothing of the old server is looked after - its certificate is not renewed. The old agent is told this node leaves it.':
        ' a jeho databáze je na tom serveru. Jeden agent na uzel: tento nahradí původního a dokud se databáze nepřesune na nový server (Přesunout databázi na něj…, hned potom), o starý server se nikdo nestará – jeho certifikát se neobnovuje. Původní agent dostane zprávu, že ho tento uzel opouští.',
    ', and nothing of that server is looked after until the database is moved onto the new one.':
        ' a o ten server se nikdo nestará, dokud se databáze nepřesune na nový.',
    ' (one agent a node).':
        ' (jeden agent na uzel).',
    'That agent took this node off its list.':
        'Tamní agent tento uzel vyřadil ze svého seznamu.',
    'That agent did not answer: it keeps this node’s certificate until ':
        'Tamní agent neodpověděl: ponechá si certifikát tohoto uzlu, dokud tam nespustíte ',
    'Not heard from':
        'Neozval se',
    ' - not heard from for 30 days, not waited for. One gone for good is taken away on the database server: ':
        ' – neozval se 30 dní, nečeká se na něj. Uzel, který odešel natrvalo, odeberte na databázovém serveru: ',
    'Busy with ':
        'Zaneprázdněn: ',
    ' for ':
        ' pro ',
    'Newer than otp':
        'Novější než otp',
    'Not the one otp ships':
        'Není ten, který dodává otp',
    ' is newer than this otp ':
        ' je novější než toto otp ',
    ' - upgrade otp on this node (or put the agent of this version back on the database server: ':
        ' – aktualizujte otp na tomto uzlu (nebo na databázový server vraťte agenta této verze: ',
    'The agent’s program is not the one otp ':
        'Program agenta není ten, který dodává otp ',
    ' ships (changed there, or from another build) - put it back: ':
        ' (změněn na serveru nebo z jiného sestavení) – vraťte ho: ',
    'Show this machine’s database as a database server':
        'Zobrazit databázi tohoto stroje jako databázový server',
    'PostgreSQL or MariaDB on the same machine as otp drawn as a database server, in a card above Encryption to the database server: a tile for each node’s own - its version, running for how long, TLS and its certificate, the connections, its data’s disk, the memory, the processors and the load. Each node looks at its own every 30 s with its own connection and tells the other node in its row of the database, as it does everything else - no agent, nothing more opened or allowed. Off: nothing of it is read, written or shown. Not for SQLite, nor with otp-db-agent (which has a card of its own).':
        'PostgreSQL nebo MariaDB na stejném stroji jako otp zobrazená jako databázový server, v kartě nad Šifrováním k databázovému serveru: dlaždice pro vlastní databázi každého uzlu – její verze, jak dlouho běží, TLS a její certifikát, spojení, disk s jejími daty, paměť, procesory a zátěž. Každý uzel se na svou dívá každých 30 s vlastním spojením a druhému uzlu to sděluje ve svém řádku databáze, jako vše ostatní – bez agenta, nic dalšího se neotevírá ani nepovoluje. Vypnuto: nic z toho se nečte, nezapisuje ani nezobrazuje. Ne pro SQLite ani s otp-db-agent (ten má kartu vlastní).',
    'Each node’s database is on its own machine':
        'Databáze každého uzlu je na jeho vlastním stroji',
    'This node’s database is on this machine':
        'Databáze tohoto uzlu je na tomto stroji',
    'Look at this node’s database server now, rather than within 30 s.':
        'Zkontrolovat databázový server tohoto uzlu hned, ne až do 30 s.',
    'A new certificate from otp’s own authority for the PostgreSQL of each node, now, not 45 days before the end - as Encryption to the database server does. The connections go on.':
        'Nový certifikát od vlastní autority otp pro PostgreSQL každého uzlu, hned, ne až 45 dní před koncem – jako to dělá Šifrování k databázovému serveru. Spojení běží dál.',
    'PostgreSQL on this machine started again for the settings waiting for its next start, and waited for (asked first).':
        'PostgreSQL na tomto stroji spuštěn znovu kvůli nastavením čekajícím na jeho příští start, a počká se na něj (nejdřív se zeptá).',
    'Its certificate ends':
        'Jeho certifikát končí',
    'looked at by each node itself - no agent':
        'sleduje ji každý uzel sám – bez agenta',
    'The certificates of the link between the databases, made again on both nodes as High availability does - PostgreSQL reloaded, not restarted; replication goes on.':
        'Certifikáty spojení mezi databázemi, vydané znovu na obou uzlech jako to dělá Vysoká dostupnost – PostgreSQL znovu načten, ne restartován; replikace běží dál.',
    # (1.0.289: the words otp split differently from acme)
    ' - not running':
        ' – neběží',
    ' - not the agent’s server':
        ' – není to server agenta',
    ' - this node’s pages and RADIUS wait for it meanwhile.':
        ' – stránky a RADIUS tohoto uzlu na něj mezitím počkají.',
    ' - upgrade the agent on the database server: ':
        ' – aktualizujte agenta na databázovém serveru: ',
    ' and waits for it. Every connection is cut for a few seconds':
        ' a počká na něj. Všechna spojení se na pár sekund přeruší',
    '--otp-node is the address the database server sees this node by: ':
        '--otp-node je adresa, pod kterou databázový server tento uzel vidí: ',
    '; replication catches up by itself afterwards.':
        '; replikace to potom sama dožene.',
    'Looked after by otp-db-agent at ':
        'Stará se o něj otp-db-agent na ',
    'The agent restarts ':
        'Agent restartuje ',
    'This node’s database is on ':
        'Databáze tohoto uzlu je na ',
    'not encrypted':
        'nešifrováno',
    'otp-db-agent at ':
        'otp-db-agent na ',
    'A database server otp should look after itself (its certificate, settings, restarts)? Connect its agent first:':
        'Databázový server, o který se má otp starat samo (jeho certifikát, nastavení, restarty)? Nejdřív připojte jeho agenta:',
}
P289 = {
    'the database server of {0} ({1})':
        'databázový server uzlu {0} ({1})',
    'The database agent of {0} does not answer':
        'Agent databázového serveru uzlu {0} neodpovídá',
    'otp-db-agent at {0} has not answered since {1}: {2}. otp can neither renew nor change its database server meanwhile (the certificate, the settings, a restart); the database itself may well go on - look at the server (systemctl status otp-db-agent).':
        'otp-db-agent na {0} neodpovídá od {1}: {2}. otp mezitím nemůže jeho databázový server obnovovat ani měnit (certifikát, nastavení, restart); samotná databáze ale může běžet dál – podívejte se na server (systemctl status otp-db-agent).',
    'The database server of {0} is down':
        'Databázový server uzlu {0} neběží',
    'its agent ({0}) answers, the database does not: {1}':
        'jeho agent ({0}) odpovídá, databáze ne: {1}',
    'The certificate of the database agent of {0} ends soon':
        'Certifikát agenta databázového serveru uzlu {0} brzy vyprší',
    'The agent restarts {0} on {1} and waits for it. Every connection is cut for a few seconds; replication catches up by itself afterwards.':
        'Agent restartuje {0} na {1} a počká na něj. Všechna spojení se na několik sekund přeruší; replikace to potom dožene sama.',
    'The agent restarts {0} on {1} and waits for it. Every connection is cut for a few seconds - this node’s pages and RADIUS wait for it meanwhile.':
        'Agent restartuje {0} na {1} a počká na něj. Všechna spojení se na několik sekund přeruší – stránky tohoto uzlu a RADIUS na něj zatím počkají.',
    'it ends {0}; the agent renews it by itself 60 days before, and that did not work - Settings → The database → Database server → Renew the certificates':
        'vyprší {0}; agent ho obnovuje sám 60 dní předem, a to se nepovedlo - Nastavení → Databáze → Databázový server → Obnovit certifikáty',
    'this node is one of a cluster and its database is on {0}, looked after by the agent at {1}:{2}: another agent is not joined instead - take the cluster apart first (Settings -> High availability)':
        'tento uzel je součástí clusteru a jeho databáze je na {0}, o který se stará agent {1}:{2}: jiný agent se místo něj nepřipojí – nejdřív cluster rozeberte (Nastavení → Vysoká dostupnost)',
}
