# 1.0.280: hunt rounds 1-3; root's SSH keys only shown, a user's key for every node or one.
S280 = {
    'the certificate cannot be checked for revocation (CRL, OCSP) just now - nobody signs in with it until it can; an administrator sees why in the events':
        'certifikát teď nelze ověřit proti odvolání (CRL, OCSP) – nikdo se s ním nepřihlásí, dokud to nepůjde; administrátor vidí proč v událostech',
    'The keys that may sign in to each node over SSH - as root (the lines of /root/.ssh/authorized_keys, only shown here: put on and taken away by root on the node itself) or as any user who may sign in there (their own ~/.ssh/authorized_keys, written as they are), read from every node. A key made here for a user is shown once, to be kept by you, and kept nowhere on the server; one of your own is put on by its public half - on every node or on one. Every change is written into Events.':
        'Klíče, kterými se lze přes SSH přihlásit na každý uzel – jako root (řádky /root/.ssh/authorized_keys, zde jen zobrazené: přidává a odebírá je root přímo na uzlu) nebo jako kterýkoli uživatel, který se tam smí přihlásit (jeho vlastní ~/.ssh/authorized_keys, zapsaný jeho jménem), načtené z každého uzlu. Klíč vytvořený zde pro uživatele se ukáže jednou, abyste si ho uložili, a na serveru se nikde neuchovává; vlastní klíč se přidá jeho veřejnou polovinou – na všechny uzly, nebo na jeden. Každá změna se zapíše do Událostí.',
    'Keys for root': 'Klíče roota',
    'root\'s SSH keys are only shown on these pages - put on and taken away by root on the node itself (/root/.ssh/authorized_keys)':
        'SSH klíče roota se na těchto stránkách jen zobrazují – přidává a odebírá je root přímo na uzlu (/root/.ssh/authorized_keys)',
}
P280 = {
    '{0} - the same key': '{0} – stejný klíč',
    '<b>{0}</b> only': 'jen <b>{0}</b>',
    "Make a fresh pair here - Ed25519, or RSA 4096 where something old needs RSA. Its private half is shown to you once; its public half goes into {0}'s authorized_keys of {1}.":
        'Vytvořit zde nový pár – Ed25519, nebo RSA 4096, kde něco staršího potřebuje RSA. Soukromá část se vám ukáže jednou; veřejná se zapíše do authorized_keys uživatele {0} na {1}.',
    'A fresh pair is made here. Its private half is shown to you once, to download or copy, and kept nowhere; its public half goes onto {0}. A key there before stays until it is taken away in the list below.':
        'Zde se vytvoří nový pár. Soukromá část se vám ukáže jednou, ke stažení nebo zkopírování, a nikde se neuchovává; veřejná se zapíše na {0}. Klíč, který tam byl dřív, zůstane, dokud ho v seznamu níže neodeberete.',
    '{0} left as it is (no password at all is switched on only from the pages)':
        '{0} ponecháno beze změny (přihlášení úplně bez hesla se zapíná jen na stránkách)',
}
R280 = {
    "Its <b>public</b> half goes into <code>~{0}/.ssh/authorized_keys</code> of {1} - written as {2}, so that the folder and the file are theirs. The <b>private</b> half is never kept here: it is shown to you once, to hand over. The key is then in the list below - exported or taken away there; a key of their own is added there too.":
        "Jeho <b>veřejná</b> část se zapíše do <code>~{0}/.ssh/authorized_keys</code> na {1} – zapisuje ji {2} sám, takže složka i soubor jsou jeho. <b>Soukromá</b> část se zde nikdy neukládá: zobrazí se vám jen jednou, k předání. Klíč je pak v seznamu níže – tam se exportuje nebo odebere; vlastní klíč uživatele se přidá tamtéž.",
    'Root\'s keys are only shown here - none is made, put on or taken away from these pages. That is done by root on the node itself, in <code>/root/.ssh/authorized_keys</code>. A key for another user who may sign in on the nodes is made or added here: choose them under <b>Whose keys</b>.':
        'Klíče roota se zde jen zobrazují – na těchto stránkách se žádný nevytváří, nepřidává ani neodebírá. To dělá root přímo na uzlu, v <code>/root/.ssh/authorized_keys</code>. Klíč pro jiného uživatele, který se smí přihlásit na uzly, se zde vytvoří nebo přidá: vyberte ho v poli <b>Čí klíče</b>.',
}
