# 1.0.234: bug hunt A - SELinux counted since the last change, auditd, the directory cap per account.
S244 = {
 "Nothing refused since otp's needs were put in": "Od doplnění toho, co otp potřebuje, nic neodepřeno",
 "auditd does not run - what SELinux refuses is not written down (systemctl enable --now auditd)": "auditd neběží – co SELinux odepře, se nikam nezapisuje (systemctl enable --now auditd)",
 "Switch the directory on to read its policy": "Pro načtení politiky adresář zapněte",
 "The account is locked at its first wrong password - no cap here can keep that from happening; 1 at least keeps it to one wrong password from here.": "Účet se zamkne hned po prvním špatném hesle – tomu žádný strop tady nezabrání; 1 aspoň zajistí, že odtud projde nejvýš jedno špatné heslo.",
 "the code could not be sent - try again later, or ask the administrator": "kód se nepodařilo odeslat – zkuste to později, nebo se obraťte na správce",
 "the port is 1 to 65535 and the time a number of seconds": "port je 1 až 65535 a čas počet sekund",
}
P244 = {
 "SELinux refused {0} thing(s) since otp's needs were put in": "SELinux od doplnění toho, co otp potřebuje, odepřel {0}×",
 "older than 1.0.231 while the guard against writes to the database is on ({0}): switch it off on every node first": "starší než 1.0.231, zatímco je zapnutá ochrana proti zápisu do databáze ({0}): nejdřív ji vypněte na všech uzlech",
}
