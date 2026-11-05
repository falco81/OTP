# 1.0.251: what each setting of the password policy of the local users does, in its (i).
S261 = {
 "On: otp writes the values below into the files of every node of the cluster - /etc/security/pwquality.conf.d/50-otp.conf, its lines in pwhistory.conf and faillock.conf, the aging lines of /etc/login.defs - and puts them in again on a node that has other ones. With authselect, the features with-pwhistory and with-faillock are switched on only when they are needed. Off: what otp wrote is taken out again, and each node has the policy its system has.":
  'Zapnuto: otp zapíše hodnoty níže do souborů každého uzlu clusteru – /etc/security/pwquality.conf.d/50-otp.conf, své řádky v pwhistory.conf a faillock.conf a řádky stárnutí hesel v /etc/login.defs – a na uzlu, který má jiné, je zapíše znovu. S authselect zapne funkce with-pwhistory a with-faillock, jen když jsou potřeba. Vypnuto: co otp zapsal, se zase odebere a každý uzel má politiku, jakou má jeho systém.',
 'The fewest characters a new password may have (pam_pwquality: minlen). Only a new password is checked - one set before stays until it is changed.':
  'Nejmenší počet znaků nového hesla (pam_pwquality: minlen). Kontroluje se jen nové heslo – dříve nastavené platí, dokud se nezmění.',
 'How many of the four kinds of characters a new password must have at least: small letters, capitals, digits, the others (pam_pwquality: minclass). Any: no kinds asked for.':
  'Kolik ze čtyř druhů znaků musí nové heslo mít nejméně: malá písmena, velká písmena, číslice, ostatní (pam_pwquality: minclass). Libovolně: žádné druhy se nevyžadují.',
 'The most times one character may come in a row - with 3, "aaa" is taken and "aaaa" is not (pam_pwquality: maxrepeat). 0: as many as wanted.':
  'Kolikrát nejvýš smí jeden znak jít za sebou – při 3 projde „aaa“, ale „aaaa“ ne (pam_pwquality: maxrepeat). 0: libovolněkrát.',
 'How many characters of the new password must not be in the old one (pam_pwquality: difok). Checked only where the old password is typed too - passwd by the user, a password run out at sign-in; not when root or these pages set it.':
  'Kolik znaků nového hesla nesmí být ve starém (pam_pwquality: difok). Kontroluje se jen tam, kde se zadává i staré heslo – passwd spuštěný uživatelem, heslo vypršelé při přihlášení; ne když heslo nastavuje root nebo tyto stránky.',
 "A new password that is a word of the dictionary (cracklib's), also turned around or with little changed, is refused (pam_pwquality: dictcheck).":
  'Nové heslo, které je slovem ze slovníku (cracklib), i pozpátku nebo jen málo změněné, se odmítne (pam_pwquality: dictcheck).',
 "A new password with the user's name in it, also turned around, is refused (pam_pwquality: usercheck).":
  'Nové heslo, které obsahuje jméno uživatele, i pozpátku, se odmítne (pam_pwquality: usercheck).',
 "On: a password is good for the days set here; after them the user must change it at the next sign-in - over SSH with a key or otp's code too (login.defs: PASS_MAX_DAYS; chage -M). Off: a password never runs out.":
  'Zapnuto: heslo platí zde nastavený počet dní; potom ho uživatel musí při dalším přihlášení změnit – i přes SSH s klíčem nebo kódem otp (login.defs: PASS_MAX_DAYS; chage -M). Vypnuto: heslo nikdy nevyprší.',
 'How many days a password is good after it was set (login.defs: PASS_MAX_DAYS; chage -M). Then it must be changed at the next sign-in.':
  'Kolik dní heslo platí od nastavení (login.defs: PASS_MAX_DAYS; chage -M). Potom se musí při dalším přihlášení změnit.',
 'How many days before a password runs out the user is told so at sign-in (login.defs: PASS_WARN_AGE; chage -W).':
  'Kolik dní před vypršením hesla na to uživatel dostane upozornění při přihlášení (login.defs: PASS_WARN_AGE; chage -W).',
 'How many days after a change the password may not be changed again - so that the last passwords cannot be gone through at once to come back to the old one (login.defs: PASS_MIN_DAYS; chage -m). 0: changed again at once.':
  'Kolik dní po změně nejde heslo změnit znovu – aby se nedalo hned projít posledními hesly a vrátit se ke starému (login.defs: PASS_MIN_DAYS; chage -m). 0: lze změnit hned znovu.',
 "How many of a user's last passwords cannot be taken again (pam_pwhistory: remember; they are kept hashed in /etc/security/opasswd). 0: any. With authselect, its feature with-pwhistory is switched on for it.":
  'Kolik posledních hesel uživatele nejde použít znovu (pam_pwhistory: remember; uchovávají se jako hashe v /etc/security/opasswd). 0: libovolné. S authselect se pro to zapne funkce with-pwhistory.',
 "login.defs holds the days only for the users made after it. On: the days set here are put on every local user there now too, on every node (chage) - never on root, nor on a user with no password (a key only), who could never give a new one. Off: the users there now keep their own days; each user's are in their popup.":
  'login.defs platí jen pro uživatele vytvořené potom. Zapnuto: zde nastavené dny se dají i všem lokálním uživatelům, kteří už existují, na každém uzlu (chage) – nikdy rootovi ani uživateli bez hesla (jen s klíčem), který by nový nikdy nemohl zadat. Vypnuto: stávající uživatelé si nechají své dny; ty každého uživatele jsou v jeho okně.',
 "After so many wrong passwords - counted within the time set here - the user is locked (pam_faillock: deny). 0: never locked. root is never locked. A key or otp's code for SSH never counts and is never kept out: the lock keeps out the password (at the console, for sudo). With authselect, its feature with-faillock is switched on for it.":
  'Po tolika špatných heslech – počítaných v zde nastavené době – se uživatel zamkne (pam_faillock: deny). 0: nikdy se nezamyká. Root se nezamyká nikdy. Klíč ani kód otp pro SSH se nikdy nepočítá a zámek ho nezastaví: zámek zastaví heslo (na konzoli, pro sudo). S authselect se pro to zapne funkce with-faillock.',
 'How long a locked user stays locked, in seconds (pam_faillock: unlock_time). 0: until root unlocks them - faillock --user NAME --reset.':
  'Jak dlouho zůstane zamčený uživatel zamčený, v sekundách (pam_faillock: unlock_time). 0: dokud ho root neodemkne – faillock --user JMÉNO --reset.',
 'Wrong passwords are counted within so many seconds (pam_faillock: fail_interval) - those before do not count towards the lock.':
  'Špatná hesla se počítají v rámci tolika sekund (pam_faillock: fail_interval) – starší se do zámku nepočítají.',
 'otp --local-policy-set': 'otp --local-policy-set',
}
P261 = {}
