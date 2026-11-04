# 1.0.245: Local users -> Password policy; a user's own password aging.
S254 = {
 "Password policy": "Politika hesel",
 "For every local user, however the password is changed - passwd, a password run out at sign-in, these pages. Put into each node's own files: pam_pwquality, pam_pwhistory, pam_faillock and login.defs (with authselect, the features that put the modules in). Not set here, each node keeps what its system has, and nothing is written.":
  "Pro všechny místní uživatele, ať se heslo mění jakkoli – passwd, heslo vypršelé při přihlášení, tyto stránky. Zapíše se do vlastních souborů každého uzlu: pam_pwquality, pam_pwhistory, pam_faillock a login.defs (s authselect i funkce, které moduly zařadí do PAM). Když se tu nenastaví, každý uzel si ponechá, co má jeho systém, a nic se nezapisuje.",
 "Set by otp on every node": "Nastavuje otp na všech uzlech",
 "Off: as each node's system has it - what otp wrote before is taken out again.":
  "Vypnuto: jak to má systém každého uzlu – co otp dřív zapsalo, se zase odebere.",
 "The password": "Heslo",
 "Characters at least": "Znaků nejméně",
 "Kinds of characters at least": "Druhů znaků nejméně",
 "small letters, capitals, digits, the others": "malá písmena, velká písmena, číslice, ostatní",
 "any": "libovolně",
 "all 4": "všechny 4",
 "The same character in a row at most": "Stejný znak za sebou nejvýš",
 "0: as many as wanted": "0: kolikrát chce",
 "Characters not in the old one": "Znaků, které nejsou ve starém",
 "No word of the dictionary": "Žádné slovo ze slovníku",
 "Not the user's name": "Ne jméno uživatele",
 "How long it is good": "Jak dlouho platí",
 "A password runs out": "Heslo vyprší",
 "Good for (days)": "Platí (dní)",
 "Warned so many days before": "Upozornit tolik dní předem",
 "The least days between two changes": "Nejméně dní mezi dvěma změnami",
 "0: changed again at once": "0: lze změnit hned znovu",
 "The last passwords not taken again": "Posledních hesel, která nelze použít znovu",
 "0: any; needs pam_pwhistory": "0: jakékoli; vyžaduje pam_pwhistory",
 "Also for the users there now": "I pro stávající uživatele",
 "Without it, the days are for users made from now on (login.defs); a user's own are in their popup.":
  "Bez toho platí dny jen pro nově vytvořené uživatele (login.defs); vlastní hodnoty uživatele jsou v jeho okně.",
 "Wrong passwords": "Špatná hesla",
 "Locked after so many wrong (faillock)": "Zamknout po tolika špatných (faillock)",
 "0: never locked; root never": "0: nikdy nezamykat; root nikdy",
 "...for (seconds)": "...na (sekund)",
 "0: until unlocked by root (faillock --reset)": "0: dokud ho root neodemkne (faillock --reset)",
 "...counted within (seconds)": "...počítáno během (sekund)",
 "Save the policy": "Uložit politiku",
 "As it is saved": "Jak je uloženo",
 "In effect on the nodes": "Platí na uzlech",
 "Rule": "Pravidlo",
 "pam_pwquality in PAM": "pam_pwquality v PAM",
 "authselect": "authselect",
 "not used": "nepoužívá se",
 "no end": "bez konce",
 "no (pam_pwhistory not in PAM)": "ne (pam_pwhistory není v PAM)",
 "no (pam_faillock not in PAM)": "ne (pam_faillock není v PAM)",
 "as set here": "jak je nastaveno tady",
 "the system's own": "systémové",
 "being put in…": "zapisuje se…",
 "Password aging": "Platnost hesla",
 "99999: no end": "99999: bez konce",
 "Save the aging": "Uložit platnost",
 "each node puts it in within a few seconds": "každý uzel ji zapíše během několika sekund",
 "the least days between two changes is more than the days a password is good":
  "nejméně dní mezi dvěma změnami je víc, než kolik dní heslo platí",
 "the password policy takes no password with the user's name in it":
  "politika hesel nepřijme heslo, ve kterém je jméno uživatele",
}
P254 = {
 "The password runs out on {0}.": "Heslo vyprší {0}.",
 "{0}: pam_pwquality is not in its PAM - the rules of the password are not kept there by passwd.":
  "{0}: pam_pwquality není v jeho PAM – passwd tam pravidla hesla nedodrží.",
 "{0}: pam_faillock is not in its PAM, and authselect does not manage it - the lockout is not in use there.":
  "{0}: pam_faillock není v jeho PAM a authselect ho nespravuje – zamykání se tam nepoužívá.",
 "the password policy wants {0} characters at least": "politika hesel chce nejméně {0} znaků",
 "the password policy wants {0} kinds of characters at least (small letters, capitals, digits, others) - it has {1}":
  "politika hesel chce nejméně {0} druhů znaků (malá a velká písmena, číslice, ostatní) – heslo má {1}",
 "the password policy takes no character more than {0} times in a row": "politika hesel nepřijme žádný znak víc než {0}× za sebou",
 "the password policy does not take it: {0}": "politika hesel ho nepřijme: {0}",
 "{0} is {1} to {2}": "{0} je {1} až {2}",
 "{0} / {1} s": "{0} / {1} s",
}
# Why the database card on the overview has its colour.
S254.update({
 "Red: the key that opens the tokens is not on this node - without it no token can be read. Put it back from beside a backup (Settings → The database).":
  "Červená: na tomto uzlu chybí klíč, který otevírá tokeny – bez něj nejde přečíst žádný token. Vraťte ho z kopie vedle zálohy (Nastavení → Databáze).",
 "Green: a copy of the last two days is here, and one is made every day.": "Zelená: kopie z posledních dvou dnů tu je a každý den se dělá nová.",
 "Green: a copy of the last two days is here, and none is made by itself - Settings → Backups.":
  "Zelená: kopie z posledních dvou dnů tu je, ale sama se nedělá – Nastavení → Zálohy.",
 "Yellow: there is no copy of the database yet; one is made every day.": "Žlutá: zatím tu není žádná kopie databáze; každý den se dělá nová.",
 "Yellow: there is no copy of the database yet; none is made by itself - Settings → Backups.":
  "Žlutá: zatím tu není žádná kopie databáze a sama se nedělá – Nastavení → Zálohy.",
})
P254.update({
 "Green: a copy of the last two days is here, and one is made every day at {0}.": "Zelená: kopie z posledních dvou dnů tu je a každý den v {0} se dělá nová.",
 "Yellow: the last copy is {0} - older than two days; one is made every day at {1}.": "Žlutá: poslední kopie je {0} – starší než dva dny; každý den v {1} se má dělat nová.",
 "Yellow: the last copy is {0} - older than two days; one is made every day.": "Žlutá: poslední kopie je {0} – starší než dva dny; každý den se má dělat nová.",
 "Yellow: the last copy is {0} - older than two days; none is made by itself - Settings → Backups.":
  "Žlutá: poslední kopie je {0} – starší než dva dny, a sama se nedělá – Nastavení → Zálohy.",
 "Yellow: there is no copy of the database yet; one is made every day at {0}.": "Žlutá: zatím tu není žádná kopie databáze; každý den v {0} se dělá nová.",
})
S254.update({
 "The row of the policy in the database is not as otp wrote it - the guard of root's actions refused it: every node keeps the policy it has put in, and changes nothing. Save the policy here again.":
  "Řádek politiky v databázi není takový, jak ho otp zapsalo – ochrana rootových akcí ho odmítla: každý uzel si ponechá politiku, kterou zapsal, a nic nemění. Uložte politiku tady znovu.",
})
