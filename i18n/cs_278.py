# 1.0.278: hunt rounds 1-3 - the words the pages may now say.
S278 = {
    'admin_password_off: no password at all needs Windows or a certificate on - switch one on first (nothing saved)':
        'admin_password_off: úplně bez hesla potřebuje zapnuté Windows nebo certifikát – nejdřív jedno z nich zapněte (nic se neuložilo)',
    'no password at all (admin_password_off) would be in effect after this: sign in with Windows or a certificate first, so it is known to work for you - or switch it off in the same save (nothing saved)':
        'po této změně by platilo úplně bez hesla (admin_password_off): nejdřív se přihlaste přes Windows nebo certifikátem, ať je jisté, že vám to funguje – nebo ho vypněte ve stejném uložení (nic se neuložilo)',
    'with no password at all, nobody could sign in after this: Windows needs its keytab, a certificate an authority - put one in, or switch No password at all off (nothing saved)':
        'úplně bez hesla by se po této změně nikdo nepřihlásil: Windows potřebuje keytab, certifikát autoritu – jedno vložte, nebo vypněte Úplně bez hesla (nic se neuložilo)',
    'you signed in with Windows, which would not sign anybody in after this (switched off, or no keytab) - nothing saved':
        'přihlásili jste se přes Windows, které by po této změně nikoho nepřihlásilo (vypnuté nebo bez keytabu) – nic se neuložilo',
    'you signed in with a certificate, which would not sign anybody in after this (switched off, or no authority) - nothing saved':
        'přihlásili jste se certifikátem, který by po této změně nikoho nepřihlásil (vypnutý nebo bez autority) – nic se neuložilo',
    "the bundle carries the key that opens every token, and keys are not shown on these pages (Administrators may show a token's QR code and key is off) - make it as root: otp --ha-bundle FILE":
        'balíček nese klíč, který otevírá všechny tokeny, a klíče se na těchto stránkách nezobrazují (Administrátoři smí zobrazit QR kód a klíč tokenu je vypnuto) – vytvořte ho jako root: otp --ha-bundle SOUBOR',
    'the destination sends more than it says the file is - stopped':
        'cíl posílá víc, než podle něj soubor má – zastaveno',
}
P278 = {
    '{0} came larger than the destination says it is - not taken': '{0} přišel větší, než cíl uvádí – nepřijato',
    '{0} is not at the destination any more': '{0} už v cíli není',
    'no room for {0} here ({1} MB, {2} MB free)': 'pro {0} tu není místo ({1} MB, volných {2} MB)',
}

S278.update({
    # the CRLs of the sign-in with a certificate (crl-revocation-kit)
    'Revocation lists (CRL)': 'Seznamy odvolaných certifikátů (CRL)',
    'Fetch now': 'Stáhnout teď',
    'Fetching…': 'Stahuje se…',
    'Clear all': 'Vymazat vše',
    'Every CRL fetched again now - on every node of the cluster, each itself: those kept and those the authorities name. One that cannot be fetched lets nobody in: the last good one is kept until its next update, else nobody signs in with a certificate of it.':
        'Každý CRL se teď stáhne znovu – na každém nodu clusteru, každý sám: ty držené i ty, které uvádějí autority. Ten, který stáhnout nejde, nikoho nepustí: poslední dobrý se drží do své další aktualizace, jinak se s certifikátem, který pokrývá, nikdo nepřihlásí.',
    'Forget the CRLs kept on every node: the next sign-in (or Fetch now) fetches them again.':
        'Zapomenout CRL držené na každém nodu: další přihlášení (nebo Stáhnout teď) je stáhne znovu.',
    'Clear every CRL?': 'Vymazat všechny CRL?',
    'Every node forgets the CRLs it keeps; the next sign-in fetches them again. While an address does not answer then, nobody signs in with a certificate of its authority - the last good CRL is gone too.':
        'Každý nod zapomene CRL, které drží; další přihlášení je stáhne znovu. Dokud pak adresa neodpovídá, nikdo se certifikátem její autority nepřihlásí – poslední dobrý CRL je pryč také.',
    'Clear them': 'Vymazat je',
    'None yet: the CRL at a certificate’s CRL Distribution Point is fetched at its first sign-in and kept until its next update.':
        'Zatím žádný: CRL z CRL Distribution Point certifikátu se stáhne při jeho prvním přihlášení a drží se do své další aktualizace.',
    'Revocation is not checked (admin_cert_crl is off).': 'Odvolání se nekontroluje (admin_cert_crl je vypnuté).',
    'Fetched at a sign-in, at most every ten minutes, and kept until the next update - over http, by each node itself, never through the proxy; its signature is checked by openssl against the authorities put in. A row opens to its details and each node’s fetch.':
        'Stahuje se při přihlášení, nejvýš každých deset minut, a drží se do další aktualizace – přes http, každým nodem samostatně, nikdy přes proxy; jeho podpis ověřuje openssl proti vloženým autoritám. Řádek se rozbalí na podrobnosti a stažení na každém nodu.',
    'Issued by': 'Vydal',
    'Next update': 'Další aktualizace',
    'Revoked': 'Odvoláno',
    'Fetched': 'Staženo',
    'Copy the address': 'Zkopírovat adresu',
    'named by ': 'uvádí ',
    'delta': 'delta',
    'base': 'základní',
    'not fetched yet': 'zatím nestaženo',
    'run out': 'prošlý',
    'not had': 'není k dispozici',
    'within a day': 'do jednoho dne',
    'last fetch failed': 'poslední stažení selhalo',
    'Fetch this CRL now - on every node': 'Stáhnout tento CRL teď – na každém nodu',
    'Clear this CRL on every node - fetched again at the next sign-in': 'Vymazat tento CRL na každém nodu – stáhne se znovu při dalším přihlášení',
    'This update': 'Tato aktualizace',
    'CRL number': 'Číslo CRL',
    'Signature': 'Podpis',
    'checked': 'ověřen',
    'not checked': 'neověřen',
    'good - checked by openssl against the authorities put in': 'dobrý – ověřil ho openssl proti vloženým autoritám',
    'NOT good - openssl does not take it: nobody signs in by it': 'NENÍ dobrý – openssl ho nepřijímá: nikdo se podle něj nepřihlásí',
    'not checked - its authority is not put in': 'neověřen – jeho autorita není vložená',
    'checked by openssl at each sign-in': 'openssl ho ověřuje při každém přihlášení',
    'State': 'Stav',
    'not had - nobody signs in with a certificate whose revocation it should say': 'není k dispozici – nikdo se nepřihlásí s certifikátem, jehož odvolání by měl uvádět',
    'not fetched yet - at the first sign-in that needs it, or Fetch now': 'zatím nestaženo – při prvním přihlášení, které ho potřebuje, nebo Stáhnout teď',
    'Named by the authority': 'Uvádí ho autorita',
    'delta CRL (Freshest CRL) - applied over its base CRL': 'delta CRL (Freshest CRL) – použije se nad svým základním CRL',
    'base CRL': 'základní CRL',
    'Last error': 'Poslední chyba',
    'Each node': 'Každý nod',
    'the address copied': 'adresa zkopírována',
    'Clear one CRL': 'Vymazat jeden CRL',
    'Clear every CRL': 'Vymazat všechny CRL',
    'Fetch one CRL now': 'Stáhnout jeden CRL teď',
    'Fetch every CRL now': 'Stáhnout všechny CRL teď',
    'asked of every node…': 'požádány všechny nody…',
    'Hide this': 'Skrýt',
    'waiting': 'čeká se',
    'failed': 'selhalo',
    'cleared': 'vymazáno',
    'fetched': 'staženo',
    'not everything': 'ne vše',
    'cleared on every node': 'vymazáno na každém nodu',
    'fetched - not everything on every node': 'staženo – ne vše na každém nodu',
    'fetched on every node': 'staženo na každém nodu',
    'every node fetches the CRLs again': 'každý nod stahuje CRL znovu',
    'the CRLs are cleared on every node': 'CRL jsou vymazány na každém nodu',
    'no CRL at that address is known here (otp --cert-crl lists them)': 'žádný CRL na té adrese tu není znám (vypíše je otp --cert-crl)',
})
P278.update({
    '{0} forgotten': '{0} zapomenuto',
    '{0} of {1} fetched': 'staženo {0} z {1}',
    'the CRL at {0} could not be had ({1}) - nobody signs in while the certificate cannot be checked for revocation':
        'CRL na {0} nebylo možné získat ({1}) – dokud nejde certifikát ověřit na odvolání, nikdo se nepřihlásí',
})
