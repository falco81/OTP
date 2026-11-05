# 1.0.249: SELinux after the upgrade, and fixes of five rounds of a review - the words the pages show.
S257 = {
 'After the upgrade these are counted since the machine started again - also what was put right before it: when otp\'s needs were last put in is kept in root\'s folder now, the old note is not read. Not new refusals: they go at the next restart of the machine, or when "Put in what otp needs" changes something.':
  'Po upgradu se tyto počítají znovu od startu stroje – i to, co bylo před ním napraveno: kdy otp naposledy doplnil, co potřebuje, se nyní uchovává ve složce roota a stará poznámka se nečte. Nejde o nová zamítnutí: zmizí při příštím restartu stroje nebo když „Doplnit, co otp potřebuje“ něco změní.',
 'To move it: make this node one alone first (Settings → High availability → Switch it off), move it here, and build the cluster again from it.':
  'Postup přesunu: nejdřív z tohoto uzlu udělejte samostatný (Nastavení → Vysoká dostupnost → Vypnout), přesuňte ji sem a cluster z něj sestavte znovu.',
 "Tell the nodes the balancer's address, so that the allow lists, the sign-in pause and every log see the client and not the balancer: Settings → Firewall and access → Behind a load balancer or WAF (once, for every node) - or as root on each node:":
  'Sdělte uzlům adresu balanceru, aby seznamy povolených, pauza přihlašování i všechny logy viděly klienta, a ne balancer: Nastavení → Firewall a přístup → Za load balancerem nebo WAF (jednou, pro všechny uzly) – nebo jako root na každém uzlu:',
 'The nodes not begun stay as they are; a node being updated finishes.':
  'Uzly, které ještě nezačaly, zůstanou, jak jsou; uzel, který se právě aktualizuje, dokončí.',
 'Every node puts the settings below in again and says how much its journal and logs take - the one this page is on at once, the other within a minute.':
  'Každý uzel znovu nastaví hodnoty níže a ohlásí, kolik zabírá jeho žurnál a logy – ten, na kterém je tato stránka, hned, druhý do minuty.',
 'restarted where needed':
  'restartováno, kde bylo potřeba',
 'security updates only':
  'jen bezpečnostní aktualizace',
 'on now':
  'nyní zapnuto',
 'off now':
  'nyní vypnuto',
 'on, as its last heartbeat says':
  'zapnuto, jak říká jeho poslední heartbeat',
 'off, as its last heartbeat says':
  'vypnuto, jak říká jeho poslední heartbeat',
 'not heard from - what it said last':
  'neozval se – co řekl naposledy',
 'its version does not say':
  'jeho verze to neříká',
 'The certificate it had before ACME replaced it. Put back as it was; ACME no longer renews this one. The TLS settings stay.':
  'Certifikát, který měl, než ho ACME nahradilo. Vrátí se, jak byl; ACME ho už neobnovuje. Nastavení TLS zůstanou.',
 'This node is one of a cluster: its database is the cluster’s, and moving it from here would break the cluster.':
  'Tento uzel je součástí clusteru: jeho databáze patří clusteru a přesun odsud by cluster rozbil.',
 'not locked: its files imported as they are - an export of otp is always locked':
  'nezamčený: jeho soubory importovány, jak jsou – export z otp je vždy zamčený',
 'how the server is checked changed: type the password again':
  'změnil se způsob ověření serveru: zadejte heslo znovu',
}
P257 = {
 "SELinux refused {0} thing(s) since the machine started - after the upgrade also what was put right before it (the old note of when otp's needs were put in is not read any more): they go at the next restart of the machine":
  'SELinux od startu stroje zamítl {0} věc(í) – po upgradu i to, co bylo před ním napraveno (stará poznámka o tom, kdy otp doplnil, co potřebuje, se už nečte): zmizí při příštím restartu stroje',
 'This node is one of a cluster ({0}): its database is the cluster’s, and moving it from here would break the cluster.':
  'Tento uzel je součástí clusteru ({0}): jeho databáze patří clusteru a přesun odsud by cluster rozbil.',
 'Started by {0}':
  'Spustil(a) {0}',
 '{0} (this node): {1}':
  '{0} (tento uzel): {1}',
 'The certificate it had before ACME replaced it - from {0}. Put back as it was; ACME no longer renews this one. The TLS settings stay.':
  'Certifikát, který měl, než ho ACME nahradilo – od {0}. Vrátí se, jak byl; ACME ho už neobnovuje. Nastavení TLS zůstanou.',
 'The certificate it had before ACME replaced it, good until {0}. Put back as it was; ACME no longer renews this one. The TLS settings stay.':
  'Certifikát, který měl, než ho ACME nahradilo, platný do {0}. Vrátí se, jak byl; ACME ho už neobnovuje. Nastavení TLS zůstanou.',
 'it waits on the node {0}, and this request reached {1} - open the pages of {2} itself for it (a balancer in front of both should keep one browser on one node)':
  'čeká na uzlu {0} a tento požadavek došel na {1} – otevřete pro to stránky přímo na {2} (balancer před oběma uzly by měl držet jeden prohlížeč na jednom uzlu)',
 'more than one account in the directory answers to {0} - which one the token is cannot be said':
  'v adresáři odpovídá na {0} více účtů – nelze říct, čí token je',
 '{0} is another account in the directory than {1} - a suffix of the realm that names two people differently':
  '{0} je v adresáři jiný účet než {1} – přípona realmu, která pojmenovává dva lidi různě',
}
