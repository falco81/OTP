# 1.0.301: SELinux on a pane of its own, the card as the kit draws it.
S301 = {
    'SELinux': 'SELinux',
    'What SELinux refuses on each node, what otp needs of it, what is put right here - and the steps to enforcing.':
        'Co SELinux na každém uzlu odpírá, co od něj otp potřebuje, co se tu napraví – a kroky k režimu enforcing.',
    'What SELinux refuses to the web server, keepalived, sshd, PostgreSQL and the rest when it is enforcing - and what otp needs of it on each node. Nothing changes here unless asked: disabled stays disabled. In a cluster, one node at a time - the other answers meanwhile. On the server: sudo otp --selinux-check.':
        'Co SELinux v režimu enforcing odpírá webovému serveru, keepalived, sshd, PostgreSQL a dalším – a co od něj otp potřebuje na každém uzlu. Bez požádání se tu nic nemění: vypnutý zůstává vypnutý. V clusteru po jednom uzlu – druhý mezitím odpovídá. Na serveru: sudo otp --selinux-check.',
    'SELinux is each machine\'s own: every node has its own mode, module, refusals and fixes. What is asked on a node\'s card is asked of that node, and done by its root only - never on the other node.':
        'SELinux patří každému stroji zvlášť: každý uzel má svůj režim, modul, zamítnutí i opravy. Co se požádá na kartě uzlu, požádá se po tom uzlu a udělá to jen jeho root – nikdy na druhém uzlu.',
    'SELinux refused nothing on this node': 'SELinux na tomto uzlu nic neodepřel',
    'Nothing since the machine started.': 'Nic od startu stroje.',
    'Nothing since otp\'s needs were put in.': 'Nic od nasazení toho, co otp potřebuje.',
    'a node is doing what was asked': 'uzel dělá, o co byl požádán',
    'looked at every half hour': 'prověřuje se každou půlhodinu',
    'Or on Settings → SELinux: Put in what otp needs (while permissive).': 'Nebo v Nastavení → SELinux: Nasadit, co otp potřebuje (v režimu permissive).',
    'Settings → SELinux says the same, with what otp needs.': 'Nastavení → SELinux říká totéž, i s tím, co otp potřebuje.',
    'Settings → SELinux: Make it ready (permissive), restart the machine, then Switch to enforcing once nothing is refused.':
        'Nastavení → SELinux: Připravit (permissive), restartovat stroj, a až nebude nic odepřeno, přepnout na enforcing.',
    "What SELinux refuses on each node when it is enforcing, and what otp needs of it: its own module (otp_server), the labels of its files, the booleans that let the pages ask the daemon and SSH ask for the code, the ports of sshd and PostgreSQL. Looked at every half hour; what is put right and the steps - made ready and permissive, enforcing, permissive again - are done by each node's root only when asked here or with":
        'Co SELinux v režimu enforcing na každém uzlu odpírá a co od něj otp potřebuje: vlastní modul (otp_server), štítky jeho souborů, přepínače, které stránkám dovolí ptát se démona a SSH ptát se na kód, porty sshd a PostgreSQL. Prověřuje se každou půlhodinu; co se napraví a kroky – připravit a permissive, enforcing, znovu permissive – dělá root každého uzlu jen na požádání zde nebo příkazem',
    '.': '.',
    'One node at a time: each is taken out of service - the VIP address, the load balancer and the VPN go to the other node - upgraded, checked and put back. This page follows it and loads the new version by itself.':
        'Jeden uzel po druhém: každý se vyřadí z provozu – adresa VIP, vyvažovač i VPN přejdou na druhý uzel – aktualizuje se, zkontroluje a vrátí zpět. Tato stránka průběh sleduje a novou verzi si načte sama.',
}
P301 = {
    '{0} of {1} node(s) done': 'hotovo {0} z {1} uzlů',
}
