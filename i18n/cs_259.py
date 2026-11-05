# 1.0.249, rounds 2-5 of the review: the words the pages show - high security, the backup
# destinations' saved password, the enrolment, the password policy of the local users, the
# root helper's child, the lockouts.
S259 = {
 'it is a link':
  'je to odkaz',
 'it is not a plain file':
  'není to obyčejný soubor',
 'high security is on: SELinux is not switched to permissive - switch high security off first':
  'vysoká bezpečnost je zapnutá: SELinux se na permissive nepřepíná – nejdřív vysokou bezpečnost vypněte',
 'high security is on: the link between the databases stays encrypted - or make ha:tls an exception there first':
  'vysoká bezpečnost je zapnutá: spojení mezi databázemi zůstává šifrované – nebo tam nejdřív z ha:tls udělejte výjimku',
 'trusted - the saved password was taken away with the old key: type it again':
  'ověřeno – uložené heslo bylo odebráno spolu se starým klíčem: zadejte ho znovu',
 'forgotten - the saved password with it: type it again':
  'zapomenuto – a s ním i uložené heslo: zadejte ho znovu',
 'pinned - the saved password was taken away: type it again':
  'připnuto – uložené heslo bylo odebráno: zadejte ho znovu',
 'the file sent is not here any more: send it again':
  'nahraný soubor už tu není: nahrajte ho znovu',
 'its host key forgotten, and its saved password':
  'zapomenut klíč serveru a s ním i uložené heslo',
 'its host key forgotten':
  'zapomenut klíč serveru',
 'Backups stop going there until it is trusted again - and its saved password is forgotten with it, to be typed again.':
  'Zálohy tam přestanou chodit, dokud se znovu neověří – a s ním se zapomene i uložené heslo, které bude potřeba zadat znovu.',
 'the shortest password':
  'nejkratší heslo',
 'days a password is good':
  'počet dní platnosti hesla',
 'the least days between two changes':
  'nejméně dní mezi dvěma změnami',
 'days of warning before':
  'počet dní upozornění předem',
 'passwords remembered':
  'počet pamatovaných hesel',
 'kinds of characters':
  'počet druhů znaků',
 'the same character in a row':
  'stejný znak za sebou',
 'characters other than the old':
  'počet znaků odlišných od starého',
 'days a password is good is 1 to 99999':
  'počet dní platnosti hesla je 1 až 99999',
 "The certificates ordered from Let's Encrypt (or another ACME CA) and renewed by themselves.":
  "Certifikáty objednané u Let's Encrypt (nebo jiné ACME CA), které se samy obnovují.",
 "The operating system's packages updated, one node at a time, the VIP address moved out of the way first; a restart offered when one is needed.":
  'Balíčky operačního systému aktualizované po jednom uzlu, VIP adresa nejdřív přesunutá stranou; restart nabídnut, když je potřeba.',
 'Syslog facility':
  'Syslog facility',
 'Port (UDP)':
  'Port (UDP)',
 'Engine ID':
  'Engine ID',
 'Leap status':
  'Stav přestupné sekundy',
 'SSH port':
  'Port SSH',
}
P259 = {
 "{0} / {1} is PostgreSQL's own, not otp's database and account":
  '{0} / {1} patří samotnému PostgreSQL, nejsou to databáze a účet otp',
 "{0} is a superuser of PostgreSQL - not otp's account":
  '{0} je superuser PostgreSQL – není to účet otp',
 '{0}: a name is read without the dot at its end - make the token for {1}':
  '{0}: jméno se čte bez tečky na konci – vytvořte token pro {1}',
 'the directory cannot be reached just now - whether {0} has a token under another name cannot be said':
  'adresář teď není dosažitelný – nelze říct, zda {0} nemá token pod jiným jménem',
 'the second certificate ({0}) ran out on {1}':
  'platnost druhého certifikátu ({0}) skončila {1}',
 'its host key trusted ({0}), its saved password taken away':
  'klíč serveru ověřen ({0}), uložené heslo odebráno',
 'its host key trusted ({0})':
  'klíč serveru ověřen ({0})',
 "the server's certificate pinned ({0}), its saved password taken away":
  'certifikát serveru připnut ({0}), uložené heslo odebráno',
 "the server's certificate pinned ({0})":
  'certifikát serveru připnut ({0})',
 'the child working as {0} did not answer in 30 s':
  'potomek běžící jako {0} neodpověděl do 30 s',
 'cleared: {0} - not cleared: {1} ({2})':
  'vymazáno: {0} – nevymazáno: {1} ({2})',
 'cleared: {0} - not cleared: {1} (refused)':
  'vymazáno: {0} – nevymazáno: {1} (odmítnuto)',
}
