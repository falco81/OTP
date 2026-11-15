# 1.0.279: OCSP and CRLs from the directory (the ocsp-ldap-kit).
S279 = {
    'CRLs from the directory (LDAP) too': 'CRL i z adresáře (LDAP)',
    'Ask an OCSP responder': 'Ptát se OCSP respondéru',
    'OCSP responder of its own': 'Vlastní OCSP respondér',
    'off - the CRLs alone': 'vypnuto – jen CRL',
    'first - OCSP, its CRL when it does not answer': 'nejdřív – OCSP, když neodpoví, jeho CRL',
    'only - OCSP alone, no answer no sign-in': 'jen – samotné OCSP, bez odpovědi žádné přihlášení',
    'both - OCSP and the CRL': 'obojí – OCSP i CRL',
    'not checked': 'nekontroluje se',
    'no answer': 'bez odpovědi',
    'and': 'a',
    'none to be had': 'nic k dispozici',
    'no sign-in': 'žádné přihlášení',
    'http, then the directory (LDAP)': 'http, pak adresář (LDAP)',
    'one responder for all': 'jeden respondér pro všechny',
    'each certificate’s responder': 'respondér každého certifikátu',
    'Online status (OCSP)': 'Stav online (OCSP)',
    'Ask again': 'Zeptat se znovu',
    'Asking…': 'Ptám se…',
    'Every responder asked again now, for every certificate it answered for - on every node. One that does not answer changes nothing that lets anybody in.':
        'Každý respondér se teď zeptá znovu, na každý certifikát, za který odpověděl – na každém nodu. Ten, který neodpoví, nezmění nic, co by někoho pustilo dovnitř.',
    'Clear every OCSP answer?': 'Vymazat všechny odpovědi OCSP?',
    'Every answer kept is forgotten on every node; the next sign-in asks the responder again. While it does not answer then, its last good answer is gone too.':
        'Každá držená odpověď se na každém nodu zapomene; další přihlášení se respondéru zeptá znovu. Dokud pak neodpovídá, je pryč i jeho poslední dobrá odpověď.',
    'The responder set is not an address otp asks: ': 'Nastavený respondér není adresa, které se otp ptá: ',
    'None yet: a responder is asked at the first sign-in, and its answer is used ten minutes at most.':
        'Zatím žádná: respondéru se otp zeptá při prvním přihlášení a jeho odpověď používá nejvýš deset minut.',
    'Asked at a sign-in, at most every ten minutes, by each node itself, never through the proxy; the answer is signed by the authority or a responder it named, and checked by openssl against the authorities put in.':
        'Ptá se při přihlášení, nejvýš každých deset minut, každý nod sám, nikdy přes proxy; odpověď je podepsaná autoritou nebo respondérem, kterého určila, a openssl ji ověřuje proti vloženým autoritám.',
    'Certificate': 'Certifikát',
    'Status': 'Stav',
    'Serial': 'Sériové číslo',
    'Asked': 'Dotázáno',
    'Ask the responder again - on every node': 'Zeptat se respondéru znovu – na každém nodu',
    'Clear this answer - asked again at the next sign-in': 'Vymazat tuto odpověď – při dalším přihlášení se zeptá znovu',
    'revoked': 'odvolán',
    'unknown': 'neznámý',
    'last answer kept': 'drží se poslední odpověď',
    'the responder says it is not revoked': 'respondér říká, že odvolaný není',
    'the responder says it is revoked: nobody signs in with it': 'respondér říká, že je odvolaný: nikdo se s ním nepřihlásí',
    'the responder does not know it: nobody signs in with it': 'respondér ho nezná: nikdo se s ním nepřihlásí',
    'no answer to be had: by its CRL instead when OCSP comes first, else nobody signs in with it':
        'odpověď není k dispozici: když je OCSP první, rozhodne jeho CRL, jinak se s ním nikdo nepřihlásí',
    'its next update has passed: asked again at the next sign-in': 'jeho další aktualizace už minula: při dalším přihlášení se zeptá znovu',
    'the last good answer is used until its next update; the latest asking failed': 'poslední dobrá odpověď se používá do své další aktualizace; poslední dotaz selhal',
    'Signed by': 'Podepsal',
    'Responder': 'Respondér',
    'Read from': 'Načteno z',
    'the directory (LDAP), with its connection above': 'adresáře (LDAP), jeho spojením nahoře',
    'CRLs from the directory (LDAP) are read too, after the http ones - with the connection of the directory set for administrators.':
        'Načítají se i CRL z adresáře (LDAP), po těch přes http – spojením adresáře nastaveného pro administrátory.',
    'Clear one OCSP answer': 'Vymazat jednu odpověď OCSP',
    'Clear every OCSP answer': 'Vymazat všechny odpovědi OCSP',
    'Ask one responder again': 'Zeptat se znovu jednoho respondéru',
    'Ask every responder again': 'Zeptat se znovu všech respondérů',
    'answered': 'odpověděl',
    'every responder answered': 'všechny respondéry odpověděly',
    'asked - not every responder answered': 'dotázáno – ne všechny respondéry odpověděly',
    'every responder is asked again': 'všem respondérům se otp zeptá znovu',
    'the OCSP answers are cleared on every node': 'odpovědi OCSP jsou vymazány na každém nodu',
    'no OCSP answer of that is kept here (otp --cert-ocsp lists them)': 'taková odpověď OCSP tu není držená (vypíše je otp --cert-ocsp)',
    'admin_cert_ocsp_url: not an address otp asks (http only, no user or password in it; no loopback, link-local or metadata address)':
        'admin_cert_ocsp_url: není to adresa, které se otp ptá (jen http, bez jména a hesla; žádná loopback, link-local ani adresa metadat)',
}
P279 = {
    '{0} of {1} answered': 'odpovědělo {0} z {1}',
    'the OCSP responder at {0} gave no answer ({1})': 'OCSP respondér na {0} neodpověděl ({1})',
}

S279.update({
    'Asked at a sign-in, at most every ten minutes - over http, by each node itself, never through the proxy; the answer is signed by the authority or a responder it named, and checked by openssl against the authorities put in. A row opens to its details and each node’s answer.':
        'Ptá se při přihlášení, nejvýš jednou za deset minut – přes http, každý uzel sám, nikdy přes proxy; odpověď podepisuje autorita nebo respondér, kterého určila, a ověřuje ji openssl proti vloženým autoritám. Řádek se rozbalí na podrobnosti a odpověď každého uzlu.',
    'CRLs are read from the directory too (LDAP), after the http ones - with the connection of the directory set for administrators, never the host written in the address.':
        'CRL se čtou i z adresáře (LDAP), po těch přes http – spojením adresáře nastaveného pro administrátory, nikdy hostitelem zapsaným v adrese.',
    'Clear this answer on every node - asked again at the next sign-in': 'Smazat tuto odpověď na všech uzlech – při dalším přihlášení se zeptá znovu',
    'Every responder asked again now - on every node, for every certificate it answered for. One that does not answer changes nothing that lets anybody in.':
        'Zeptat se teď znovu každého respondéru – na všech uzlech, za každý certifikát, za který odpověděl. Ten, který neodpoví, nezmění nic, co by někoho pustilo dovnitř.',
    'Forget the OCSP answers kept on every node: the next sign-in asks again.': 'Zapomenout odpovědi OCSP uložené na všech uzlech: další přihlášení se zeptá znovu.',
    'http, by each node itself': 'http, každý uzel sám',
    'the directory': 'adresář',
    'Read from': 'Načteno z',
    'the directory (LDAP), with its connection above': 'adresář (LDAP), jeho spojením uvedeným výše',
})
