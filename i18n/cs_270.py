# 1.0.263: the database's connection back to TLS by itself.
S270 = {
    'How many requests are worked on side by side. A request that waits for a slow domain controller does not hold up the others. A change starts or stops workers at once, no restart needed.': 'Kolik požadavků se zpracovává souběžně. Požadavek čekající na pomalý řadič domény nezdrží ostatní. Změna spustí nebo zastaví workery hned, bez restartu.',
    'the server is busy - try again in a moment': 'server je zaneprázdněný – zkuste to za chvíli znovu',
    'the name has more than one @ (a suffix added to a name that had one already?)': 'jméno má víc než jeden @ (přípona přidaná ke jménu, které už ji mělo?)',
    'the name has more than one @ - a suffix added twice?': 'jméno má víc než jeden @ – přípona přidaná dvakrát?',
    'otp (it works with TLS again)': 'otp (s TLS to zase funguje)',
    # 1.0.265: the system's trusted roots (Settings -> Certificates and TLS).
    'Trusted roots of the system': 'Důvěryhodné kořenové certifikáty systému',
    "Certificate authorities of your own - your company's root, an intermediate - trusted by the operating system of every node as a whole: curl, dnf, LDAPS to a domain controller, SMTP, syslog over TLS, otp's own connections - every program that uses the system's trust. The distribution's own list stays as it is and keeps coming with the system's updates; these are added beside it, the way the system itself takes local additions (update-ca-trust on RHEL, AlmaLinux and Rocky, update-ca-certificates on Debian and Ubuntu), and stay there through those updates.":
        'Vlastní certifikační autority – kořenová autorita vaší firmy, mezilehlá autorita – kterým důvěřuje operační systém každého nodu jako celek: curl, dnf, LDAPS na řadič domény, SMTP, syslog přes TLS, vlastní spojení otp – každý program, který používá důvěru systému. Vlastní seznam distribuce zůstává, jak je, a dál přichází s aktualizacemi systému; tyto se přidávají vedle něj, tak jak systém sám přijímá místní doplňky (update-ca-trust na RHEL, AlmaLinuxu a Rocky, update-ca-certificates na Debianu a Ubuntu), a zůstávají tam i přes tyto aktualizace.',
    'Add an authority': 'Přidat autoritu',
    'A root or an intermediate certificate authority of your own - pasted as PEM, or a .pem, .crt or .cer file; a file with a chain adds each authority in it.':
        'Vlastní kořenová nebo mezilehlá certifikační autorita – vložená jako PEM, nebo soubor .pem, .crt či .cer; soubor s řetězcem přidá každou autoritu v něm.',
    'Read it again on every node': 'Načíst znovu na každém nodu',
    "otp has added none - every node trusts its system's own list alone.": 'otp žádnou nepřidalo – každý nod důvěřuje jen vlastnímu seznamu svého systému.',
    'Authority': 'Autorita',
    'Valid': 'Platnost',
    'root': 'kořenová',
    'intermediate': 'mezilehlá',
    'not an authority': 'není autorita',
    'Download it (PEM)': 'Stáhnout (PEM)',
    "Take it out of the system's trust": 'Odebrat z důvěry systému',
    "otp's own connections (the directory, mail, syslog, SMS, ACME, the database with the system's authorities) use the system's list too - what is added here reaches them at their next connection.":
        'Vlastní spojení otp (adresář, pošta, syslog, SMS, ACME, databáze s autoritami systému) používají také seznam systému – co se tu přidá, platí pro ně od jejich dalšího spojení.',
    'as wanted': 'jak má být',
    'nothing added by otp': 'otp nic nepřidalo',
    "The system's own list": 'Vlastní seznam systému',
    'Its package': 'Jeho balíček',
    'Made last': 'Naposledy sestaven',
    'Local additions in': 'Místní doplňky v',
    'Made by': 'Sestavuje',
    "otp's additions there": 'Doplňky otp tam',
    'Added by somebody else - otp leaves them as they are:': 'Přidal někdo jiný – otp je nechává, jak jsou:',
    '- a link': '– odkaz',
    '- no certificate read': '– nenačten žádný certifikát',
    "Add to the system's trust": 'Přidat do důvěry systému',
    'that file is far bigger than certificates are': 'ten soubor je mnohem větší, než certifikáty bývají',
    'there already': 'už tam je',
    'Add them': 'Přidat',
    'A certificate authority of your own - a root, or an intermediate - as PEM (<code>-----BEGIN CERTIFICATE-----</code>), or a <code>.pem</code>, <code>.crt</code> or <code>.cer</code> file. A chain adds every authority in it. Only authorities are taken (CA:TRUE), never a private key.':
        'Vlastní certifikační autorita – kořenová nebo mezilehlá – jako PEM (<code>-----BEGIN CERTIFICATE-----</code>), nebo soubor <code>.pem</code>, <code>.crt</code> či <code>.cer</code>. Řetězec přidá každou autoritu v něm. Berou se jen autority (CA:TRUE), nikdy soukromý klíč.',
    'Every program of both nodes trusts what they sign from then on.': 'Každý program na obou nodech pak důvěřuje tomu, co podepíší.',
    'Every program of this server trusts what they sign from then on.': 'Každý program na tomto serveru pak důvěřuje tomu, co podepíší.',
    'this server': 'tento server',
    'either node': 'žádný z nodů',
    'the SHA-256 fingerprint is copied': 'otisk SHA-256 je zkopírovaný',
    "taken away - every node takes it out of its system's trust within a minute": 'odebráno – každý nod ho do minuty vyjme z důvěry svého systému',
    'asked: every node reads its trusted roots again within a minute': 'požádáno: každý nod do minuty znovu načte své důvěryhodné kořenové certifikáty',
    'nothing added: every certificate in it is there already': 'nic nepřidáno: každý certifikát v něm už tam je',
    'no private key and nothing but certificates (-----BEGIN CERTIFICATE-----)': 'žádný soukromý klíč a nic než certifikáty (-----BEGIN CERTIFICATE-----)',
    'no certificate in it (-----BEGIN CERTIFICATE-----)': 'není v tom žádný certifikát (-----BEGIN CERTIFICATE-----)',
    'the certificates: PEM text, or a file': 'certifikáty: text PEM, nebo soubor',
    'neither PEM (-----BEGIN CERTIFICATE-----) nor one certificate in DER': 'ani PEM (-----BEGIN CERTIFICATE-----), ani jeden certifikát v DER',
    'the SHA-256 fingerprint - 12 characters of it at least': 'otisk SHA-256 – alespoň 12 jeho znaků',
    'otp has added no certificate with that fingerprint': 'otp nepřidalo žádný certifikát s tímto otiskem',
    'more than one certificate begins with that - give more of it': 'tím začíná víc než jeden certifikát – zadejte ho delší',
    'it says nothing of being an authority (no basicConstraints CA:TRUE) - only a certificate authority goes here':
        'neříká, že je autorita (chybí basicConstraints CA:TRUE) – sem patří jen certifikační autorita',
    "it is not a certificate authority (CA:FALSE) - a server's own certificate does not go here":
        'není to certifikační autorita (CA:FALSE) – vlastní certifikát serveru sem nepatří',
    'its key usage does not let it sign certificates (no keyCertSign)': 'jeho použití klíče nedovoluje podepisovat certifikáty (chybí keyCertSign)',
    "an intermediate without its root here: programs that take a partial chain (curl, Python 3.13 on) trust it by itself, others want its root too - add the root as well, unless the system's list has it":
        'mezilehlá autorita bez své kořenové: programy, které berou částečný řetězec (curl, Python od 3.13), jí důvěřují samotné, ostatní chtějí i její kořenovou – přidejte i kořenovou, pokud ji nemá seznam systému',
    "its root is not among these - trusted by itself only where a partial chain is taken (curl, Python 3.13 on), unless the system's list has the root":
        'její kořenová mezi nimi není – samotné se důvěřuje jen tam, kde se bere částečný řetězec (curl, Python od 3.13), pokud kořenovou nemá seznam systému',
    'asked more than five minutes ago and not done - is it of this version, and is otp-web.path running there?':
        'požádáno před víc než pěti minutami a neprovedeno – je ve stejné verzi a běží tam otp-web.path?',
    "The system's trusted roots (certificate authorities) of each node": 'Důvěryhodné kořenové certifikáty systému (certifikační autority) každého nodu',
    # 1.0.267: domain controllers on Windows Server 2025.
    'the domain controller wants a signed or encrypted connection (LDAP signing, the default of Windows Server 2025): reach the directory by LDAPS or STARTTLS':
        'řadič domény vyžaduje podepsané nebo šifrované spojení (LDAP signing, výchozí u Windows Serveru 2025): připojte adresář přes LDAPS nebo STARTTLS',
    'the directory wants this over an encrypted connection: reach it by LDAPS or STARTTLS':
        'adresář to vyžaduje přes šifrované spojení: připojte ho přes LDAPS nebo STARTTLS',
    'Plain LDAP: domain controllers of Windows Server 2025 refuse a sign-in over it (LDAP signing is their default). Reach this directory by LDAPS or STARTTLS.':
        'Nešifrovaný LDAP: řadiče domény s Windows Serverem 2025 přihlášení přes něj odmítnou (LDAP signing je u nich výchozí). Připojte tento adresář přes LDAPS nebo STARTTLS.',
    'Given by its address, while the certificate is checked against the server’s name - a new domain controller’s certificate (Windows Server 2025) usually carries its name only. Give the name (FQDN) instead:':
        'Zadáno IP adresou, přitom se certifikát ověřuje proti jménu serveru – certifikát nového řadiče domény (Windows Server 2025) obvykle obsahuje jen jeho jméno. Zadejte místo toho jméno (FQDN):',
    'its servers by name (FQDN)': 'jeho servery jménem (FQDN)',
    # 1.0.268: put back from a backup - SELinux's mode, the connections to the databases.
    'Settings → High security → SELinux: Make it ready (permissive), restart the machine, then Switch to enforcing once nothing is refused.':
        'Nastavení → Vysoké zabezpečení → SELinux: Připravit (permissive), restartovat stroj, a až nebude nic odmítáno, Přepnout na enforcing.',
    'After the restart, and a while with nothing refused:': 'Po restartu a chvíli bez odmítnutí:',
    'This band goes by itself once SELinux is enforcing on this node again.': 'Tento pruh zmizí sám, jakmile bude SELinux na tomto uzlu opět v režimu enforcing.',
    'SELinux was enforcing on this node before it was put back from a backup': 'SELinux byl na tomto uzlu před obnovou ze zálohy v režimu enforcing',
    # 1.0.269: the whole chain.
    'Upload the missing authority': 'Nahrát chybějící autoritu',
    'Missing in the chain:': 'V řetězci chybí:',
    'Add it to the chain': 'Přidat do řetězce',
    'Complete the chain': 'Doplnit řetězec',
    'Check the chain': 'Zkontrolovat řetězec',
    'Sent': 'Posílá se',
    'The certificate of that authority - the intermediate (or several) your certificate authority gives with the certificate, often called "CA bundle", "intermediate" or "chain" - as PEM or a .cer / .crt file. Only certificates of authorities, never a key; the certificate and its key stay as they are. A root is kept to check with and never sent.':
        'Certifikát té autority – mezilehlý (nebo několik), který certifikační autorita dává k certifikátu, často pod názvem „CA bundle“, „intermediate“ nebo „chain“ – jako PEM nebo soubor .cer / .crt. Jen certifikáty autorit, nikdy klíč; certifikát a jeho klíč zůstávají, jak jsou. Kořen se uloží ke kontrole a nikdy se neposílá.',
    "Checked against the system's root authorities; an intermediate the certificate did not come with is fetched from its CA Issuers address, as browsers do it - so that curl, a VPN client and other clients that fetch nothing take it too.":
        'Ověří se proti kořenovým autoritám systému; mezilehlá autorita, která s certifikátem nepřišla, se stáhne z adresy CA Issuers, jak to dělají prohlížeče – aby ho přijal i curl, VPN klient a další klienti, kteří si nic nestahují.',
    'incomplete - what nginx sends does not lead to a root of the system: curl, a VPN client and other clients refuse it':
        'neúplný – to, co nginx posílá, nevede ke kořeni systému: curl, VPN klient a další klienti ho odmítnou',
    'self-signed - no chain; whoever connects must trust this certificate itself':
        'self-signed – žádný řetězec; kdo se připojuje, musí důvěřovat přímo tomuto certifikátu',
    'checked as a client that fetches nothing: the whole chain is sent':
        'ověřeno jako klient, který si nic nestahuje: posílá se celý řetězec',
    'only the certificates of the authorities - no private key': 'jen certifikáty autorit – žádný soukromý klíč',
    'no certificate in it (-----BEGIN CERTIFICATE-----, or a .cer file)': 'není v tom žádný certifikát (-----BEGIN CERTIFICATE----- nebo soubor .cer)',
    'every certificate in it is there already': 'každý certifikát z toho už tam je',
}
P270 = {
    'this node is busy: {0} requests wait for the directory {1}': 'tento nod je vytížený: na adresář {1} čeká {0} požadavků',
    'this node is busy: {0} requests wait for the directory {1}, which answers slowly ({2} ms a request)': 'tento nod je vytížený: na adresář {1} čeká {0} požadavků a odpovídá pomalu ({2} ms na požadavek)',
    'this node is busy: {0} requests wait for the directory {1} already - this one is not added to them': 'tento nod je vytížený: na adresář {1} už čeká {0} požadavků – tento se k nim nepřidává',
    'The code was not sent: it waited {0} s to be sent, longer than a code is good for': 'Kód nebyl odeslán: na odeslání čekal {0} s, déle, než kód platí',
    'otp (it works with TLS again): the connection of {0} to its database is encrypted ({1}, {2})':
        'otp (s TLS to zase funguje): spojení {0} s jeho databází je šifrované ({1}, {2})',
    # 1.0.265: the system's trusted roots.
    "otp's own connections do not use the system's list here ({0}) - what is added here does not reach them.":
        'Vlastní spojení otp tu nepoužívají seznam systému ({0}) – co se tu přidá, se jich netýká.',
    '{0} authorities': '{0} {0:autorita|autority|autorit}',
    'valid {0} – {1} · {2}': 'platný {0} – {1} · {2}',
    'added {0} - every node puts it into its system\'s trust within a minute': 'přidáno {0} – každý nod ho do minuty vloží do důvěry svého systému',
    'added {0} - every node puts them into its system\'s trust within a minute': 'přidáno {0} – každý nod je do minuty vloží do důvěry svého systému',
    'nothing added: {0}': 'nic nepřidáno: {0}',
    'it ran out on {0} - nothing it signed is trusted': 'vypršela {0} – ničemu, co podepsala, se nedůvěřuje',
    'it is valid only from {0}': 'platí až od {0}',
    "it is signed with {0} - the system's crypto policy (DEFAULT) refuses it, and every chain through it":
        'je podepsaná pomocí {0} – kryptografická politika systému (DEFAULT) ji odmítá, a s ní každý řetězec přes ni',
    "its key has {0} bits - the system's crypto policy (DEFAULT) refuses fewer than 2048":
        'její klíč má {0} bitů – kryptografická politika systému (DEFAULT) odmítá méně než 2048',
    'asked more than five minutes ago and not done - is it of this version, and is otp-web.path running there? (last: {0})':
        'požádáno před víc než pěti minutami a neprovedeno – je ve stejné verzi a běží tam otp-web.path? (naposledy: {0})',
    '{0} certificates at most - {1} are there, {2} more asked': 'nejvýš {0} certifikátů – {1} už tam je, žádá se o {2} další',
    "What <b>{0}</b> (SHA-256 <code>{1}…</code>) signs is no longer trusted by {2} - unless the system's own list has it. Connections that rely on it (LDAPS, mail, syslog…) fail from their next start.":
        'Tomu, co podepisuje <b>{0}</b> (SHA-256 <code>{1}…</code>), už {2} nedůvěřuje – pokud ji nemá vlastní seznam systému. Spojení, která na ní závisejí (LDAPS, pošta, syslog…), od svého dalšího startu selžou.',
    # 1.0.267: domain controllers on Windows Server 2025.
    'the directory {0} is reached over plain LDAP - domain controllers of Windows Server 2025 refuse a sign-in over it (LDAP signing, their default)':
        'adresář {0} se připojuje nešifrovaným LDAPem – řadiče domény s Windows Serverem 2025 přihlášení přes něj odmítnou (LDAP signing, jejich výchozí nastavení)',
    "the directory {0} names its servers by address ({1}) - the certificate is checked against the server's name, and a new domain controller's certificate usually carries its name only":
        'adresář {0} zadává své servery IP adresou ({1}) – certifikát se ověřuje proti jménu serveru a certifikát nového řadiče domény obvykle obsahuje jen jeho jméno',
    # 1.0.268
    '{0}: the connection to its database is encrypted again as the cluster has it ({1})':
        '{0}: spojení s jeho databází je znovu šifrované, jak to má cluster ({1})',
    '{0}: the connection to its database is not encrypted as the cluster has it ({1}) - tried again every {2} minutes: {3}':
        '{0}: spojení s jeho databází není šifrované, jak to má cluster ({1}) – zkouší se znovu každých {2} minut: {3}',
    "This machine was installed anew and the backup put back: otp put back its users, keys, SELinux's booleans and its own module, but SELinux's mode is the machine's - it is {0} here now. Make it as it was: ready (permissive, one restart of the machine), a while with nothing refused, then enforcing - one node at a time in a cluster.":
        'Tento stroj byl nainstalován znovu a záloha vrácena: otp vrátil své uživatele, klíče, booleany SELinuxu i svůj modul, ale režim SELinuxu patří stroji – teď je tu {0}. Vraťte ho, jak byl: připravit (permissive, jeden restart stroje), chvíli bez odmítnutí, pak enforcing – v clusteru jeden uzel po druhém.',
    # 1.0.269: the whole chain.
    'complete - {0} certificates up to {1}': 'úplný – {0} certifikáty až ke {1}',
    'complete - {0} certificate up to {1}': 'úplný – {0} certifikát až ke {1}',
    'complete - {0} certificates up to {1} (fetched: {2} - it was not sent with the certificate)':
        'úplný – {0} certifikáty až ke {1} (staženo: {2} – s certifikátem se neposlalo)',
    'complete - {0} certificates up to {1} - a private root: only clients that trust it take it':
        'úplný – {0} certifikáty až ke {1} – soukromý kořen: přijmou ho jen klienti, kteří mu důvěřují',
    'incomplete - the authority {0} is not sent and could not be completed ({1}); curl, Python, a VPN client and other clients refuse it - only browsers fetch it themselves; upload the certificate with its chain, or the missing authority':
        'neúplný – autorita {0} se neposílá a nepodařilo se ji doplnit ({1}); curl, Python, VPN klient a další klienti ho odmítnou – jen prohlížeče si ji stáhnou samy; nahrajte certifikát s jeho řetězcem, nebo chybějící autoritu',
    'it leads to {0}, a root the system does not trust (a private CA?) - the chain is complete; the clients (curl, a VPN client, monitoring) must trust that root, or upload its root here':
        'vede ke {0}, kořeni, kterému systém nedůvěřuje (soukromá CA?) – řetězec je úplný; klienti (curl, VPN klient, monitoring) musí tomu kořeni důvěřovat, nebo sem nahrajte jeho kořen',
    'a client that fetches nothing (curl, a VPN client) refuses what nginx sends: {0}':
        'klient, který si nic nestahuje (curl, VPN klient), odmítá to, co nginx posílá: {0}',
    'the certificate of {0} is kept; the node puts it in within a few seconds - its chain: {1}':
        'certifikát {0} je uložen; uzel ho za pár sekund nasadí – jeho řetězec: {1}',
    'the certificate of {0} is kept; the nodes put it in within a few seconds - its chain: {1}':
        'certifikát {0} je uložen; uzly ho za pár sekund nasadí – jeho řetězec: {1}',
    'no certificate is kept for {0}': 'pro {0} není uložen žádný certifikát',
    "none of these is the authority that signed the chain's last certificate ({0})":
        'žádný z nich není autorita, která podepsala poslední certifikát řetězce ({0})',
}
