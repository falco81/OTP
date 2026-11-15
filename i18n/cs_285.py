# 1.0.285: the card of a sign-in with a certificate watched (the kit "card-removal-watch" - its Czech).
import json as _json, os as _os
S285 = {
    'When the card is taken out': 'Když se karta vytáhne',
    'Checked every (seconds)': 'Kontrolovat každých (sekund)',
    '...put back within (seconds)': '...vrátit do (sekund)',
    'Only for a sign-in made with a certificate. off: nothing is watched. signout: the page checks the card every few seconds - a new connection to the certificate\'s port the card has to sign - and the first time it is not there the session ends and the sign-in page comes. grace: the page says the card is out and waits; the session ends unless it is back in time. Another card than the one signed in with ends it at once. The server ends a watched session too when the page stops asking.':
        'Jen pro přihlášení certifikátem. off: nic se nehlídá. signout: stránka každých pár sekund kontroluje kartu – nové spojení na port certifikátu, které karta musí podepsat – a když tam karta poprvé není, session skončí a ukáže se přihlašovací stránka. grace: stránka oznámí, že karta je venku, a čeká; session skončí, pokud se karta včas nevrátí. Jiná karta, než kterou se člověk přihlásil, ji ukončí hned. Hlídanou session ukončí i server, když se stránka přestane ptát.',
    'How often the card is checked. Each check is a signature by the card (no PIN while it stays in; a YubiKey with touch or PIN policy "always" asks every time - leave this off for one). A tab in the background is checked about once a minute.':
        'Jak často se karta kontroluje. Každá kontrola je podpis kartou (dokud je vložená, bez PINu; YubiKey s touch nebo PIN policy "always" se ptá pokaždé – u něj to nechte vypnuté). Karta na pozadí se kontroluje zhruba jednou za minutu.',
    'With grace: how long the card may be out before the session ends.': 'S grace: jak dlouho smí být karta venku, než session skončí.',
    'nothing - the session goes on': 'nic – session pokračuje',
    'Put the card back': 'Vraťte kartu zpět',
    'The smart card or YubiKey was taken out, so this sign-in is locked. Put it back - the page goes on where you left off.':
        'Čipová karta nebo YubiKey byla vytažena, proto je toto přihlášení zamčené. Vraťte ji zpět – stránka sama pokračuje tam, kde jste skončili.',
    'seconds': 'sekund',
    'Signed out: the card you signed in with was taken out.': 'Odhlášeno: karta, kterou jste se přihlásili, byla vytažena.',
    'Signed out: the card you signed in with was not put back in time.': 'Odhlášeno: karta, kterou jste se přihlásili, nebyla včas vrácena.',
    'Signed out: another card than the one you signed in with was offered.': 'Odhlášeno: byla nabídnuta jiná karta, než kterou jste se přihlásili.',
    'The card is back.': 'Karta je zpět.',
    'The card you signed in with is watched from now on - save and reload the page.': 'Karta, kterou jste se přihlásili, se od teď hlídá – uložte změny a načtěte stránku znovu.',
    'the card is out - put back the card you signed in with': 'karta je vytažená – vraťte kartu, kterou jste se přihlásili',
    'signed out: the card was taken out': 'odhlášeno: karta byla vytažena',
    'the card is out': 'karta je vytažená',
    'the card they signed in with was taken out': 'karta, kterou se přihlásil, byla vytažena',
    'the card they signed in with was not put back in time': 'karta, kterou se přihlásil, nebyla včas vrácena',
    'another certificate than the one signed in with was offered (the card was changed)': 'byl nabídnut jiný certifikát, než kterým se přihlásil (karta byla vyměněna)',
    'their page stopped checking the card they signed in with': 'jeho stránka přestala kontrolovat kartu, kterou se přihlásil',
}
P285 = {
    'Signed out in {0} s unless the card is back': 'Odhlášení za {0} s, pokud se karta nevrátí',
    'signed out at the next check (every {0} s)': 'odhlášení při další kontrole (každých {0} s)',
    'a notice, then signed out unless it is back within {0} s (checked every {1} s)': 'upozornění, pak odhlášení, pokud se karta nevrátí do {0} s (kontrola každých {1} s)',
    '{0} was signed out: {1}': '{0} byl odhlášen: {1}',
    '{0}: the card they signed in with is out - the session waits {1} s for it': '{0}: karta, kterou se přihlásil, je vytažená – session na ni čeká {1} s',
    '{0}: the card they signed in with is back': '{0}: karta, kterou se přihlásil, je zpět',
}
