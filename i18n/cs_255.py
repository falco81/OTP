# 1.0.246: Settings in a cluster - each card's pill: in effect on every node?
S255 = {
 "not heard from": "neozývá se",
 "does not say - an older version": "neuvádí – starší verze",
 "in effect": "platí",
 "read in": "načteno",
 "not yet · it reads it within seconds": "zatím ne · načte do pár sekund",
 "What is saved on this card is in effect on both nodes.": "Uložené nastavení této karty platí na obou uzlech.",
 "Not every node has in what is saved yet.": "Ne každý uzel má zatím načtené to, co je uložené.",
 "Look again on both nodes": "Zkontrolovat znovu na obou uzlech",
 "Looked at": "Zkontrolováno",
 "by itself every 15 s": "samo se kontroluje každých 15 s",
}
P255 = {}
S255.update({
 "sudo asks for the user's own password - give them one, or they cannot use sudo": "sudo se ptá na vlastní heslo uživatele – dejte mu ho, jinak sudo nepoužije",
 "May use sudo, but has no password: sudo asks for their own password, so they cannot use it (nor otp --console through it) until they have one - set it above.":
  "Smí používat sudo, ale nemá heslo: sudo se ptá na jeho vlastní heslo, takže ho (ani otp --console přes něj) nepoužije, dokud heslo nedostane – nastavte ho výše.",
 "With SSH keys, otp's codes and sudo": "Se SSH klíči, kódy otp a sudo",
 "A password that runs out is asked to be changed at the next sign-in - over SSH with a key or with otp's code too (sshd asks PAM's account step). A user with no password (a key only) is given no aging, so is never asked for one.":
  "Heslo, které vyprší, se musí změnit při příštím přihlášení – i přes SSH klíčem nebo kódem otp (sshd se ptá kroku account v PAM). Uživatel bez hesla (jen klíč) platnost hesla nedostane, takže se po něm heslo nikdy nechce.",
 "otp's code for SSH is no password: it never counts as a wrong password for the lockout, and the lockout does not keep a key or a code out - it keeps out the password (at the console, for sudo).":
  "Kód otp pro SSH není heslo: nikdy se nepočítá jako špatné heslo pro zamykání a zamčení nezastaví klíč ani kód – zastaví heslo (na konzoli, pro sudo).",
 "sudo - otp --console of a normal user too - asks for the user's own password: the policy is the one for it; a user locked by wrong passwords cannot use sudo until the lock ends.":
  "sudo – i otp --console běžného uživatele – se ptá na vlastní heslo uživatele: platí pro něj tato politika; uživatel zamčený kvůli špatným heslům nepoužije sudo, dokud zámek nevyprší.",
 "root is never locked, and never given aging here.": "root se nikdy nezamyká a platnost hesla mu tu nikdy nenastavíme.",
})
