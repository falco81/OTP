# 1.0.258: to be done by hand after an update - Settings → Upgrades, the count beside Upgrades in
# the menu and on the Settings tab, the bands of the daemon's entries (88n_after.py).
S266 = {
 'To be done by hand': 'Zbývá udělat ručně',
 'What otp cannot do itself and somebody has to - a step a new version needs on the command line, what the installer left to you (SELinux, the firewall, a package). Kept here, counted beside Upgrades in the menu, said in the alerts and in the console until it is done. One that can be checked goes by itself once it is so.':
  'Co otp samo udělat nemůže a musí to udělat někdo jiný – krok na příkazové řádce, který potřebuje nová verze, co vám nechal instalátor (SELinux, firewall, balíček). Drží se to tady, počítá se to vedle Aktualizace v nabídce, hlásí se to v upozorněních a v konzoli, dokud to není hotové. Co lze ověřit, zmizí samo, jakmile to tak je.',
 'Nothing is to be done by hand.': 'Ručně není potřeba nic udělat.',
 'Done lately': 'Nedávno hotovo',
 'Nothing yet.': 'Zatím nic.',
 'Just seen': 'Právě zjištěno',
 'Mark it as done?': 'Označit jako hotové?',
 'Mark it as done': 'Označit jako hotové',
 'the command is on the clipboard': 'příkaz je ve schránce',
 'This node looks again now.': 'Tento uzel se podívá znovu hned teď.',
 'taken back': 'vráceno zpět',
 'the command line': 'příkazová řádka',
 'looked again': 'zkontrolováno znovu',
 'marked as done': 'označeno jako hotové',
 'which one?': 'které?',
 # the alerts' switch
 'An upgrade of otp that failed, or left to be done by hand': 'Upgrade otp, který selhal, nebo co zbývá udělat ručně',
 'An upgrade of otp (Settings → Upgrades) that failed on a node, or one left stuck - and what an update left to be done by hand (To be done by hand, there).':
  'Upgrade otp (Nastavení → Aktualizace), který na uzlu selhal nebo zůstal viset – a co aktualizace nechala udělat ručně (tamtéž, Zbývá udělat ručně).',
 # the entries: titles, leads, footnotes
 'an install.sh older than 1.0.258': 'install.sh starší než 1.0.258',
 'This band goes by itself once it is so.': 'Tento pruh zmizí sám, jakmile to tak bude.',
 'Once it is done, press Done.': 'Až to bude hotové, stiskněte Hotovo.',
 'A new version cannot be put in from these pages on this node': 'Na tomto uzlu nelze novou verzi nainstalovat z těchto stránek',
 'otp_upgrade.py or otp-upgrade.path, which root uses to put in a package sent here, is not installed. Upgrades from the pages wait on this node until install.sh --upgrade has put them in once.':
  'Není nainstalovaný otp_upgrade.py nebo otp-upgrade.path, kterými root instaluje sem poslaný balíček. Upgrady ze stránek na tomto uzlu čekají, dokud je install.sh --upgrade jednou nenainstaluje.',
 'nginx did not take the additions of the last upgrade': 'nginx nepřijal doplňky posledního upgradu',
 'nginx did not take the guard for big uploads': 'nginx nepřijal ochranu velkých nahrávání',
 'As root: what nginx says of the file now': 'Jako root: co nginx o souboru říká teď',
 'Then, once what it refused is put right, in the folder of the package:': 'Pak, až bude opraveno, co odmítl, ve složce balíčku:',
 'This band goes by itself once an install.sh --upgrade gets the additions in.': 'Tento pruh zmizí sám, jakmile install.sh --upgrade doplňky vloží.',
 'This band goes by itself once an install.sh --upgrade gets the guard in.': 'Tento pruh zmizí sám, jakmile install.sh --upgrade ochranu vloží.',
 "SELinux: otp's module is not the one this version needs": 'SELinux: modul otp není ten, který tato verze potřebuje',
 'As root, on the server:': 'Jako root na serveru:',
 'Then see that nothing else is missing:': 'Pak ověřte, že nic dalšího nechybí:',
 'Or on Settings → High security → SELinux: Put in what otp needs (while permissive).':
  'Nebo v Nastavení → Vysoké zabezpečení → SELinux: Vložit, co otp potřebuje (v režimu permissive).',
 'This band goes by itself once the module is in (SELinux of the node is looked at every half hour; Look again asks sooner).':
  'Tento pruh zmizí sám, jakmile bude modul vložen (SELinux uzlu se kontroluje každou půlhodinu; Zkontrolovat znovu se zeptá dřív).',
 'is not in its policy': 'v jeho politice není',
 'in its policy is older than the one of this version': 'je v jeho politice starší než ten z této verze',
 'SELinux refuses otp something on this node': 'SELinux na tomto uzlu něco otp odmítá',
 'As root, on the server - what is refused, and what otp needs:': 'Jako root na serveru – co je odmítáno a co otp potřebuje:',
 "The report, for whoever looks after otp's module:": 'Zpráva pro toho, kdo se stará o modul otp:',
 'Settings → High security → SELinux says the same, with what otp needs.': 'Nastavení → Vysoké zabezpečení → SELinux říká totéž, i s tím, co otp potřebuje.',
 'This band goes by itself once nothing is refused any more (put right, or after the next start of the machine). Done takes it away until something more is refused.':
  'Tento pruh zmizí sám, jakmile už nebude nic odmítáno (po opravě nebo po příštím startu stroje). Hotovo ho skryje, dokud nebude odmítnuto něco dalšího.',
 'CVE-2026-109618 and CVE-2026-109619: remote code execution by anybody who can reach the web server. Update PHP to the fixed release of your distribution and restart php-fpm - install.sh --upgrade does both.':
  'CVE-2026-109618 a CVE-2026-109619: vzdálené spuštění kódu kýmkoli, kdo se dostane na webový server. Aktualizujte PHP na opravené vydání vaší distribuce a restartujte php-fpm – install.sh --upgrade udělá obojí.',
 'Or, in the folder of the package:': 'Nebo ve složce balíčku:',
 'This band goes by itself within the hour once PHP is fixed.': 'Tento pruh zmizí sám do hodiny po opravě PHP.',
 'Nothing opened the firewall for otp on this node': 'Na tomto uzlu firewall pro otp nic neotevřelo',
 'As root, with firewalld:': 'Jako root, s firewalld:',
 'Or on Settings → Firewall and access.': 'Nebo v Nastavení → Firewall a přístup.',
 'A test: something that goes by itself': 'Zkouška: něco, co zmizí samo',
 'A test: something done by hand': 'Zkouška: něco, co se dělá ručně',
}
P266 = {
 'First seen {0}': 'Poprvé zjištěno {0}',
 '{0} looks again within a minute.': '{0} se podívá znovu do minuty.',
 '{0} looks again within a minute': '{0} se podívá znovu do minuty',
 '{0} to be done by hand': 'Ručně zbývá: {0}',
 '{0} to be done by hand - Settings → Upgrades': 'Ručně zbývá: {0} – Nastavení → Aktualizace',
 'As far as {0} can tell it is not done yet: it looks for it itself and this band would go by itself. Marked done by hand, it goes now, and that is written in the events.':
  'Pokud {0} může posoudit, hotové to ještě není: sám to hlídá a tento pruh by zmizel sám. Označený ručně jako hotový zmizí hned a zapíše se to do událostí.',
 '{0} has nothing called {1} to be done': '{0} nemá nic jménem {1}, co by bylo třeba udělat',
 'otp {0} is running, but the parts root installs are from before it': 'Běží otp {0}, ale části, které instaluje root, jsou starší',
 "The program is new, and what install.sh puts in beside it as root is from {0}: the root helper (certificates, the VIP address, the firewall, SELinux), the upgrade helper, the additions to nginx and SELinux's module. An upgrade from these pages does it all by itself; a package copied by hand, or an install.sh --upgrade that stopped half way, does not. Until it is done, what these pages ask of root may fail or be done as the older version did it.":
  'Program je nový a to, co vedle něj jako root instaluje install.sh, je z {0}: pomocník roota (certifikáty, VIP adresa, firewall, SELinux), pomocník upgradu, doplňky nginx a modul SELinuxu. Upgrade z těchto stránek to udělá sám; balíček zkopírovaný ručně nebo install.sh --upgrade zastavený v půli ne. Dokud se to neudělá, může to, co tyto stránky po rootovi chtějí, selhat nebo proběhnout jako ve starší verzi.',
 'As root, in the folder the otp-{0} package was unpacked in:': 'Jako root ve složce, do které byl rozbalen balíček otp-{0}:',
 'As root, in the folder the otp-{0} package was unpacked in, on {1}:': 'Jako root na {1} ve složce, do které byl rozbalen balíček otp-{0}:',
 'This band goes by itself once install.sh of {0} has run to its end here.': 'Tento pruh zmizí sám, jakmile zde install.sh verze {0} doběhne do konce.',
 'install.sh {0} put what this version needs into /etc/nginx/conf.d/otp.conf, nginx -t refused the file, and it was put back as it was - so what came with the additions is missing (the icon of a home-screen shortcut, GET /healthz and /metrics, the limits of the sign-in). The pages work as before. Usually a change of your own in the file is what nginx refuses; the copy from before the upgrade is in /etc/nginx/otp-backups.':
  'install.sh {0} doplnil do /etc/nginx/conf.d/otp.conf, co tato verze potřebuje, nginx -t soubor odmítl a ten se vrátil, jak byl – chybí tedy, co s doplňky přišlo (ikona zástupce na ploše, GET /healthz a /metrics, limity přihlášení). Stránky fungují jako dřív. Obvykle nginx odmítá vlastní změnu v souboru; kopie z doby před upgradem je v /etc/nginx/otp-backups.',
 'install.sh {0} put in the question nginx asks before it takes a database or a new version sent from these pages (auth_request), nginx -t refused it, and the file was put back as it was: such a body is taken before the pages can say whether a full administrator sends it.':
  'install.sh {0} vložil otázku, kterou nginx klade, než převezme databázi nebo novou verzi poslanou z těchto stránek (auth_request), nginx -t ji odmítl a soubor se vrátil, jak byl: takové tělo se převezme dřív, než stránky řeknou, zda ho posílá plný správce.',
 'As root, on {0}: what nginx says of the file now': 'Jako root na {0}: co nginx o souboru říká teď',
 "SELinux is enforcing on this node, and otp's module (otp_server) {0}: the labels it gives otp's files are missing, and the pages may not read what they need. Do not switch SELinux off for it - put the module in, as install.sh does.":
  'SELinux je na tomto uzlu vynucující a modul otp (otp_server) {0}: chybí štítky, které dává souborům otp, a stránky nemusí přečíst, co potřebují. Nevypínejte kvůli tomu SELinux – vložte modul, jak to dělá install.sh.',
 "SELinux is permissive on this node, and otp's module (otp_server) {0}: the labels it gives otp's files are missing, and the pages may not read what they need. Do not switch SELinux off for it - put the module in, as install.sh does.":
  'SELinux na tomto uzlu jen hlásí (permissive) a modul otp (otp_server) {0}: chybí štítky, které dává souborům otp, a stránky nemusí přečíst, co potřebují. Nevypínejte kvůli tomu SELinux – vložte modul, jak to dělá install.sh.',
 'As root, on {0}:': 'Jako root na {0}:',
 "SELinux is enforcing and refused {0} thing(s) to otp or to the programs it works with (since otp's needs were last put in, or since the machine started): what was refused does not work - the pages, the root helper, SSH with a code. Do not switch SELinux off for it: see what it is, put in what otp needs, or send the report to whoever looks after otp's module.":
  'SELinux vynucuje a odmítl {0:věc|věci|věcí} otp nebo programům, se kterými pracuje (od posledního vložení toho, co otp potřebuje, nebo od startu stroje): co bylo odmítnuto, nefunguje – stránky, pomocník roota, SSH s kódem. Nevypínejte kvůli tomu SELinux: podívejte se, co to je, vložte, co otp potřebuje, nebo pošlete zprávu tomu, kdo se stará o modul otp.',
 'As root, on {0} - what is refused, and what otp needs:': 'Jako root na {0} – co je odmítáno a co otp potřebuje:',
 'PHP {0} here does not have the php2shell fix': 'PHP {0} zde nemá opravu php2shell',
 "firewalld was not running when install.sh {0} ran, so it opened nothing and narrowed nothing. Whatever filters this machine must let through TCP 443 (and 80) to the pages and UDP 1812 and 1813 from the VPN concentrators - or let otp look after the machine's firewall on Settings → Firewall and access.":
  'Když běžel install.sh {0}, firewalld neběžel, takže nic neotevřel ani nezúžil. Cokoli tento stroj filtruje, musí propustit TCP 443 (a 80) ke stránkám a UDP 1812 a 1813 od VPN koncentrátorů – nebo nechte firewall stroje spravovat otp v Nastavení → Firewall a přístup.',
 'As root, on {0}, with firewalld:': 'Jako root na {0}, s firewalld:',
 'Made by the tests of the pages ({0}). It goes when the file says "done".': 'Udělaly to testy stránek ({0}). Zmizí, až soubor řekne „done“.',
 'Made by the tests of the pages ({0}). Press Done.': 'Udělaly to testy stránek ({0}). Stiskněte Hotovo.',
}
