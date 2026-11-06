# 1.0.256 (ui): the token window as the API's roles, one's own account asked first, and
# Czech that was wrong or missing (the trust of a certificate for the mail server and the
# SMS gateway read "u adresáře", texts drawn with no Czech).
S256_UI = {
 'Test it': 'Vyzkoušet',
 'A message the way a code goes, with a code that opens nothing.':
  'Zpráva tou cestou, kterou chodí kódy, s kódem, který nic neotevře.',
 'In the directory - asked by a token administrator or a full administrator':
  'V adresáři – ptá se správce tokenů nebo plný správce',
 'Change your own role': 'Změnit vlastní roli',
 'Change my role': 'Změnit mou roli',
 'Switch your own account off': 'Vypnout vlastní účet',
 'Switch me off': 'Vypnout mě',
 'It cannot sign in until it is switched on again; its sign-ins now are ended.':
  'Nepřihlásí se, dokud ho znovu nezapnete; jeho otevřená přihlášení se ukončí.',
}
P256_UI = {
 # Tagged ones go to the rich patterns (make_cs.py moves them); each is longer than
 # "<b>{0}</b> is no longer trusted for {1}. The others stay." and so tried before it.
 '<b>{0}</b> is no longer trusted for the mail server. The others stay.':
  'Certifikátu <b>{0}</b> se u poštovního serveru přestane věřit. Ostatní zůstanou.',
 '<b>{0}</b> is no longer trusted for the SMS gateway. The others stay.':
  'Certifikátu <b>{0}</b> se u SMS brány přestane věřit. Ostatní zůstanou.',
 '{0} no longer signs in with <code>{1}</code> ({2}) on {3}.':
  '{0} se už nepřihlásí klíčem <code>{1}</code> ({2}) na {3}.',
 '{0} no longer signs in with <code>{1}</code> on {2}.':
  '{0} se už nepřihlásí klíčem <code>{1}</code> na {2}.',
 'Put <b>{0}</b> in this role, or take it out of it. It is a change like any other on this page — nothing happens until you save.':
  'Přidat <b>{0}</b> do této role, nebo ji z ní vyjmout. Je to změna jako každá jiná na této stránce — nic se nestane, dokud neuložíte.',
 'You are signed in as <b>{0}</b>. Made {1}, you can no longer change the settings, the accounts or this role on these pages - another full administrator has to give it back.':
  'Jste přihlášeni jako <b>{0}</b>. S rolí {1} už na těchto stránkách nezměníte nastavení, účty ani tuto roli – vrátit vám ji musí jiný plný správce.',
 'You are signed in as <b>{0}</b>. Switched off, you are signed out at once and cannot sign in again - only another full administrator can switch it back on.':
  'Jste přihlášeni jako <b>{0}</b>. Po vypnutí budete hned odhlášeni a znovu se nepřihlásíte – zapnout ho zpět může jen jiný plný správce.',
 # Plain ones.
 'Time servers set {0}': 'Časové servery nastaveny {0}',
 'Time servers NOT set {0}': 'Časové servery NENASTAVENY {0}',
 '{0} token(s) in {1}, locked - left out, their keys cannot be opened here: {2}':
  '{0} {0:token|tokeny|tokenů} v {1}, zamčeno – vynechány, jejich klíče tu nelze otevřít: {2}',
 '{0} token(s) in {1}, not locked - left out, their keys cannot be opened here: {2}':
  '{0} {0:token|tokeny|tokenů} v {1}, nezamčeno – vynechány, jejich klíče tu nelze otevřít: {2}',
 'tried until {0}': 'zkouší se do {0}',
 'Switch the account {0} off': 'Vypnout účet {0}',
}

S256_UI.update({
    'Showing the keys of tokens is switched off (Settings - Tokens), and with it this download with its key':
        'Zobrazování klíčů tokenů je vypnuté (Nastavení – Tokeny), a s ním i toto stažení s klíčem',
})
