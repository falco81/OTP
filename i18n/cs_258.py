# 1.0.249: gaps of a sweep in Czech - the database note, the alerts, high security, the root
# helper not answering, the events of the local users and of the sign-in by the load balancer.
S258 = {
 # Settings → Database → Which one it is (the text before <b id="db-engine-file">).
 'This installation keeps everything in one database: the file on this machine (SQLite), PostgreSQL or MariaDB. Moving to another one is done by the wizard below, step by step - which kind, its address, reaching it (and setting it up when it is not there yet), what will happen - and then all of it: a copy of what is here first, every table carried across and counted, and the daemon started again on the new one. What is here now is never changed by it, so going back is the same wizard the other way. Where it is kept is the only thing written into':
  'Tato instalace drží vše v jedné databázi: v souboru na tomto stroji (SQLite), v PostgreSQL nebo v MariaDB. Přesun do jiné obstará průvodce níže, krok za krokem – jaký druh, její adresa, spojení s ní (a její zřízení, když ještě neexistuje), co se stane – a pak všechno: nejdřív kopie toho, co je tady, každá tabulka přenesená a spočítaná a daemon znovu spuštěný na nové. To, co je tu teď, se tím nikdy nezmění, takže návrat je tentýž průvodce opačným směrem. Kde je databáze uložena, je jediné, co se zapíše v',
 "This node is one of a cluster: its database is the cluster's, and it is not moved from here - make this node one alone first (Settings → High availability), then move it, then build the cluster again from it.":
  'Tento uzel je součástí clusteru: jeho databáze patří clusteru a odsud se nepřesouvá – nejdřív z tohoto uzlu udělejte samostatný (Nastavení → Vysoká dostupnost), pak ji přesuňte a potom z něj cluster sestavte znovu.',
 # Alerts (parts/88z_alerts.py).
 'Two nodes under one name': 'Dva uzly pod jedním jménem',
 'No code can be checked there - sign-ins through this node do not pass. Put secrets.key back from a backup.':
  'Žádný kód tam nelze ověřit – přihlášení přes tento uzel neprojdou. Vraťte soubor secrets.key ze zálohy.',
 'Codes were let in on both nodes while they were apart': 'Během rozpojení prošly kódy na obou uzlech',
 'code(s):': 'kód(ů):',
 'Changes on one node do not reach the other.': 'Změny z jednoho uzlu se nedostávají na druhý.',
 'This node does not answer RADIUS.': 'Tento uzel neobsluhuje RADIUS.',
 'This node answers RADIUS alone.': 'Tento uzel obsluhuje RADIUS sám.',
 'Set both to the same time servers (Settings → Time).': 'Nastavte na obou čas ze stejných serverů (Nastavení → Čas).',
 'are worked out with the corrected time': 'se počítají s opraveným časem',
 'may be refused': 'mohou být odmítány',
 'Codes from the apps are worked out with the corrected time there.': 'Kódy z aplikací se tam počítají s opraveným časem.',
 'Codes from the apps may be refused there.': 'Kódy z aplikací tam mohou být odmítány.',
 'is not in sync': 'není synchronizované',
 'Whoever asks it gets no answer - neither the pages nor RADIUS through it.':
  'Kdo se na ni ptá, nedostane odpověď – stránky ani RADIUS přes ni.',
 'keepalived says FAULT.': 'keepalived hlásí FAULT.',
 'The node does not take the VIP address if the other goes.': 'Uzel VIP adresu nepřevezme, kdyby druhý vypadl.',
 'The certificate of the VIP address ran out': 'Certifikát VIP adresy vypršel',
 'The certificate of the VIP address runs out soon': 'Certifikát VIP adresy brzy vyprší',
 'The CA did not renew the certificate of the VIP address': 'CA neobnovila certifikát VIP adresy',
 'Its port could not be opened.': 'Port se nepodařilo otevřít.',
 'the link between the nodes (TLS)': 'spojení uzlů (TLS)',
 'The update of the system failed': 'Aktualizace systému se nepovedla',
 'A source blocked': 'Zablokovaný zdroj',
 'A change on trial went back': 'Změna na zkoušku se vrátila',
 'A sign-in by the load balancer refused': 'Přihlášení přes load balancer odmítnuto',
 'the clock is not synchronised (timedatectl): Settings → Time': 'hodiny nejsou synchronizované (timedatectl): Nastavení → Čas',
 # The clock guard's events.
 'this node answers again': 'tento uzel opět odpovídá',
 # High security (parts/88h_hisec.py).
 'isemon is sent plain syslog (UDP/TCP) - only over TLS (1.0.172)':
  'do isemonu jde prostý syslog (UDP/TCP) – jen přes TLS (1.0.172)',
 # The root helper not answering.
 'the root helper of this node did not answer in 2 minutes - is otp-web.path running?  systemctl status otp-web.path':
  'root helper tohoto uzlu neodpověděl do 2 minut – běží otp-web.path?  systemctl status otp-web.path',
 'the root helper of this node did not answer in a minute - is otp-web.path running?  systemctl status otp-web.path':
  'root helper tohoto uzlu neodpověděl do minuty – běží otp-web.path?  systemctl status otp-web.path',
 'the root helper of this node did not answer - is otp-web.path running?  systemctl status otp-web.path':
  'root helper tohoto uzlu neodpověděl – běží otp-web.path?  systemctl status otp-web.path',
 'root did not answer in time - it may still put the network in and restart; waiting for that':
  'root neodpověděl včas – síť možná ještě nastaví a restartuje; čeká se na to',
 'it stopped while root put the network in (the service restarted?) - waiting for the restart':
  'zastavilo se, zatímco root nastavoval síť (restartovala se služba?) – čeká se na restart',
 'root had not said yet': 'root se ještě neozval',
 # The local users (parts/90u_osusers.py).
 'no such thing to do with a user': 's uživatelem nelze udělat nic takového',
 "openssl is not on this node - it makes the password's hash": 'openssl na tomto uzlu není – vytváří hash hesla',
 'that is not a shell': 'to není shell',
 'nothing missing': 'nic nechybí',
 # The sign-in by the load balancer (parts/90o_sso.py) and the enrolment (parts/90_api.py).
 "nginx does not say which machine the request came from (OTP_PEER) - the node's nginx has not been set up for it yet":
  'nginx neříká, ze kterého stroje požadavek přišel (OTP_PEER) – nginx uzlu na to ještě není nastavený',
 'no key is set (Make a key)': 'není nastavený žádný klíč (Vytvořit klíč)',
 'the key in X-Otp-Sso-Key is not the one set': 'klíč v X-Otp-Sso-Key není ten nastavený',
 'the key in X-Otp-Sso-Key is not there': 'klíč v X-Otp-Sso-Key chybí',
 'no realm with a directory for that name': 'pro toto jméno není žádný realm s adresářem',
 'refused sign-ins by the load balancer': 'odmítnutá přihlášení přes load balancer',
 'no e-mail address': 'chybí e-mailová adresa',
 'no mobile number': 'chybí mobilní číslo',
 'nothing to send it to': 'není kam ho poslat',
 'no e-mail address;': 'chybí e-mailová adresa;',
 'no mobile number;': 'chybí mobilní číslo;',
 # The same, when a text before it ends in ': ' and the line is taken apart.
 'the root helper of this node did not answer in 2 minutes - is otp-web.path running?':
  'root helper tohoto uzlu neodpověděl do 2 minut – běží otp-web.path?',
 'the root helper of this node did not answer in a minute - is otp-web.path running?':
  'root helper tohoto uzlu neodpověděl do minuty – běží otp-web.path?',
 'the root helper of this node did not answer - is otp-web.path running?':
  'root helper tohoto uzlu neodpověděl – běží otp-web.path?',
}
P258 = {
 # Alerts (parts/88z_alerts.py): titles.
 'The key that opens the tokens is missing on {0}': 'Na {0} chybí klíč, který otevírá tokeny',
 'RADIUS on {0} is in trouble': 'RADIUS na {0} má potíže',
 '{0} cannot reach the other node': '{0} nevidí druhý uzel',
 '{0} cannot reach the other node and stepped aside': '{0} nevidí druhý uzel a ustoupil stranou',
 '{0} stepped aside': '{0} ustoupil stranou',
 '{0} cannot ask for the right time': '{0} se nemůže zeptat na přesný čas',
 'The clock of {0} is {1} s off': 'Hodiny {0} jdou o {1} s',
 'The clocks of {0} and {1} differ by {2} s': 'Hodiny {0} a {1} se liší o {2} s',
 '{0} cannot reach the directory': '{0} nedosáhne na adresář',
 'No node holds the VIP address {0}': 'VIP adresu {0} nedrží žádný uzel',
 'Both nodes hold the VIP address {0}': 'VIP adresu {0} drží oba uzly',
 '{0} cannot hold the VIP address': '{0} nemůže držet VIP adresu',
 'keepalived is not running on {0}': 'keepalived na {0} neběží',
 'The backup of {0} cannot be put back': 'Zálohu z {0} nejde obnovit',
 'The logs of {0} do not reach {1}': 'Logy z {0} nedochází do {1}',
 'The SNMP agent on {0} is not listening': 'SNMP agent na {0} neposlouchá',
 'SNMP traps from {0} do not go': 'Trapy SNMP z {0} neodchází',
 'The CA did not renew the certificate of {0}': 'CA neobnovila certifikát {0}',
 'The certificate of {0} on {1} ran out': 'Certifikát {0} na {1} vypršel',
 'The certificate of {0} on {1} runs out soon': 'Certifikát {0} na {1} brzy vyprší',
 'The update of the system failed on {0}': 'Aktualizace systému na {0} se nepovedla',
 '{0} cannot look for updates': '{0} se nemůže podívat po aktualizacích',
 'The upgrade of otp to {0} failed': 'Upgrade otp na {0} se nepovedl',
 '{0} refused rows of the database not written by otp': '{0} odmítl řádky databáze, které nezapsal otp',
 '{0} mail(s) with a code or a token did not go':
  '{0} {0:mail|maily|mailů} s kódem nebo tokenem {0:neodešel|neodešly|neodešlo}',
 'The replication is {0} behind': 'Replikace zaostává o {0}',
 'SELinux on {0}: something is not as otp needs it': 'SELinux na {0}: něco není, jak otp potřebuje',
 'The security check: {0} thing(s)': 'Kontrola zabezpečení: {0} {0:věc|věci|věcí}',
 # Alerts: what is said under them.
 'Changes on one node do not reach the other ({0}).': 'Změny z jednoho uzlu se nedostávají na druhý ({0}).',
 'RADIUS on {0} could not use the database: {1}': 'RADIUS na {0} nemohl použít databázi: {1}',
 "The other node's database has not answered since {0}. {1}": 'Databáze druhého uzlu neodpovídá od {0}. {1}',
 '{0} code(s): {1}': '{0} {0:kód|kódy|kódů}: {1}',
 'The other node answers RADIUS for it: {0}': 'RADIUS tohoto uzlu obsluhuje druhý uzel: {0}',
 'No reference time server answered: {0}': 'Žádný referenční časový server neodpověděl: {0}',
 'Codes from the apps {0} there.': 'Kódy z aplikací tam {0}.',
 'The nodes do not see each other over VRRP ({0}) - answers come from either.':
  'Uzly se přes VRRP nevidí ({0}) – odpovědi chodí střídavě z obou.',
 '{0} ({1} lines dropped)': '{0} (zahozeno {1} řádků)',
 'Good until {0} ({1} days) - it renews itself; when it does not, Settings → {2}.':
  'Platí do {0} ({1} dní) – obnovuje se sám; když ne, Nastavení → {2}.',
 # The clock guard's events.
 'this node answers again - {0}': 'tento uzel opět odpovídá – {0}',
 'this node steps aside: {0} - RADIUS is answered by the other node, the VIP address goes to it':
  'tento uzel ustupuje stranou: {0} – RADIUS obsluhuje druhý uzel, VIP adresa přechází na něj',
 # High security.
 'there is no such rule: {0}': 'takové pravidlo není: {0}',
 'high security is on and this is not as it wants it - put it right first ({0}), then take the exception back':
  'vysoká bezpečnost je zapnutá a tohle není tak, jak ji chce – nejdřív to napravte ({0}), pak výjimku zrušte',
 # The root helper not answering, and its siblings.
 'the root helper of this node did not answer in {0} s - is otp-web.path running?  systemctl status otp-web.path':
  'root helper tohoto uzlu neodpověděl do {0} s – běží otp-web.path?  systemctl status otp-web.path',
 'the root helper of this node did not answer in {0} s - is otp-web.path running?':
  'root helper tohoto uzlu neodpověděl do {0} s – běží otp-web.path?',
 '{0} is not here: the root helper of this node is not installed (install.sh --upgrade puts it in)':
  '{0} tu není: pomocník roota na tomto uzlu není nainstalovaný (doinstaluje ho install.sh --upgrade)',
 "this node's PostgreSQL answers with a certificate the cluster's authority did not sign ({0})":
  'PostgreSQL tohoto uzlu odpovídá certifikátem, který nepodepsala autorita clusteru ({0})',
 'only {0} answers: restarting it would stop the service - bring the other node back first (or out of maintenance)':
  'odpovídá jen {0}: jeho restart by zastavil službu – nejdřív vraťte druhý uzel (nebo ho vyveďte z údržby)',
 # The local users: the events.
 '{0} made the local user {1} (UID {2}, sudo, a password set) on {3}':
  '{0} vytvořil místního uživatele {1} (UID {2}, sudo, heslo nastaveno) na {3}',
 '{0} made the local user {1} (UID {2}, sudo, no password) on {3}':
  '{0} vytvořil místního uživatele {1} (UID {2}, sudo, bez hesla) na {3}',
 '{0} made the local user {1} (UID {2}, a password set) on {3}':
  '{0} vytvořil místního uživatele {1} (UID {2}, heslo nastaveno) na {3}',
 '{0} made the local user {1} (UID {2}, no password) on {3}':
  '{0} vytvořil místního uživatele {1} (UID {2}, bez hesla) na {3}',
 '{0} set a new password for the local user {1} on {2}': '{0} nastavil nové heslo místnímu uživateli {1} na {2}',
 '{0} locked the local user {1} on {2}': '{0} zamkl místního uživatele {1} na {2}',
 '{0} unlocked the local user {1} on {2}': '{0} odemkl místního uživatele {1} na {2}',
 '{0} gave the local user {1} sudo on {2}': '{0} dal místnímu uživateli {1} sudo na {2}',
 '{0} took from the local user {1} sudo on {2}': '{0} odebral místnímu uživateli {1} sudo na {2}',
 '{0} changed the local user {1} on {2}': '{0} změnil místního uživatele {1} na {2}',
 '{0} took away the local user {1} on {2}': '{0} odebral místního uživatele {1} na {2}',
 '{0} took away the local user {1} and the home folder on {2}':
  '{0} odebral místního uživatele {1} i s domovskou složkou na {2}',
 '{0} set the password aging of the local user {1} ({2}) on {3}':
  '{0} nastavil stárnutí hesla místního uživatele {1} ({2}) na {3}',
 '{0} set the password policy of the local users: at least {1} characters, {2} kinds, {3}, history {4}, {5}':
  '{0} nastavil politiku hesel místních uživatelů: nejméně {1} znaků, {2} {2:druh|druhy|druhů}, {3}, historie {4}, {5}',
 '{0} gave back to the system the password policy of the local users':
  '{0} vrátil politiku hesel místních uživatelů systému',
 'good for {0} days': 'platí {0} {0:den|dny|dní}',
 'locked after {0} wrong': 'zamčení po {0} chybných',
 # The local users: what the page says of a node.
 '{0} change(s) asked of it more than five minutes ago are not done - is otp-web.path running there?':
  '{0} {0:změna zadaná|změny zadané|změn zadaných} před více než pěti minutami {0:není provedená|nejsou provedené|není provedeno} – běží tam otp-web.path?',
 'its users could not be read: {0}': 'jeho uživatele se nepodařilo načíst: {0}',
 'the password for {0} could not be opened here - is the key that opens the tokens the same on this node?':
  'heslo pro {0} se tu nepodařilo otevřít – je klíč, který otevírá tokeny, na tomto uzlu stejný?',
 'it came too late: the password for {0} is no longer kept': 'přišlo pozdě: heslo pro {0} se už neuchovává',
 'no UID of the normal range is free on {0}': 'na {0} není volné žádné UID z běžného rozsahu',
 "openssl did not make the password's hash: {0}": 'openssl nevytvořil hash hesla: {0}',
 "what the backup kept of {0}'s machine could not be put back ({1} tries): {2} - otp --machine-kept putback tries again":
  'co záloha uchovala ze stroje {0}, se nepodařilo vrátit ({1} pokusů): {2} – otp --machine-kept putback to zkusí znovu',
 'put back on {0} what the backup kept of the machine: {1}': 'na {0} vráceno, co záloha uchovala ze stroje: {1}',
 # The sign-in by the load balancer.
 'a sign-in by the load balancer was refused (from {0}, for {1}): {2}':
  'přihlášení přes load balancer bylo odmítnuto (z {0}, pro {1}): {2}',
 '{0} made a new key for the sign-in by the load balancer - the one before is no longer taken':
  '{0} vytvořil nový klíč pro přihlašování přes load balancer – dosavadní se už nepřijímá',
 'not from the balancers named ({0})': 'ne od uvedených balancerů ({0})',
 'no name in {0}': 'v {0} není žádné jméno',
 'the directory: {0}': 'adresář: {0}',
 'the enrolment pages could not reach the directory: {0}': 'stránky registrace nedosáhly na adresář: {0}',
 '{0} signed in to the enrolment pages from {1} - signed in by the load balancer':
  '{0} se přihlásil na stránky registrace z {1} – přihlášen přes load balancer',
 # The enrolment.
 "{0} signed in, and {1} is another account's name: no token here":
  '{0} se přihlásil a {1} je jméno jiného účtu: token tu nebude',
 '{0} cannot enrol: a one-time code is needed first, and neither the mail nor the SMS is set up':
  '{0} se nemůže registrovat: nejdřív je potřeba jednorázový kód a není nastavený mail ani SMS',
 '{0} cannot enrol here: a one-time code is needed first, and the directory has {1}':
  '{0} se tu nemůže registrovat: nejdřív je potřeba jednorázový kód a v adresáři: {1}',
 'the e-mail address {0}: {1}': 'e-mailová adresa {0}: {1}',
 'the mobile number {0}: {1}': 'mobilní číslo {0}: {1}',
}
