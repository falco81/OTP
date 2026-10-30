# 1.0.178: SSH with a code from otp (pam_radius); the isemon wizard comes back.
S208 = {
 "A code from otp": "Kód z otp",
 "asked (pam_radius)": "vyžadován (pam_radius)",
 "not asked": "nevyžadován",
 "pam_radius is not here": "pam_radius tu není",
 "Signing in with a code from otp": "Přihlášení s kódem z otp",
 "sshd asks for a code from the account's token where it would ask for its password, through pam_radius and the RADIUS of the node itself (127.0.0.1). The RADIUS client \"SSH of the nodes - pam_radius\" is made by itself. Users sign in with their token in a realm with no suffix - the name typed at ssh is the name otp looks up.":
  "sshd tam, kde by chtěl heslo účtu, vyžádá kód z jeho tokenu – přes pam_radius a RADIUS samotného uzlu (127.0.0.1). RADIUS klient „SSH of the nodes - pam_radius“ se vytvoří sám. Uživatelé se přihlašují tokenem v realmu bez přípony – jméno zadané u ssh je jméno, které otp hledá.",
 "Ask for a code from otp": "Vyžadovat kód z otp",
 "A key alone still lets in - sshd asks for the code only where it asks for a password.": "Samotný klíč dál pustí dovnitř – sshd chce kód jen tam, kde by chtěl heslo.",
 "Needs otp to set the SSH server, above.": "Vyžaduje, aby SSH server nastavovalo otp (výše).",
 "Only these accounts": "Jen tyto účty",
 "everybody": "všichni",
 "Separated by spaces. Empty: everybody but root, unless root is asked too.": "Oddělené mezerami. Prázdné: všichni kromě roota, pokud není zapnutý i root.",
 "Root too": "I root",
 "Off: root signs in as before - a way in if otp itself is in trouble.": "Vypnuto: root se přihlašuje jako dřív – cesta dovnitř, když má potíže samo otp.",
 "The system password when otp does not answer": "Systémové heslo, když otp neodpovídá",
 "pam_radius steps aside (localifdown) and the account's own password is asked.": "pam_radius ustoupí (localifdown) a vyžádá se vlastní heslo účtu.",
 "Needs passwords on - with them off, nobody gets in without the code.": "Vyžaduje zapnutá hesla – bez nich se bez kódu nedostane nikdo.",
 "Keep the session you have open and try a new one while it is on trial. A kernel booted with ipv6.disable=1 breaks pam_radius 2.0 - nobody gets the code asked.":
  "Nechte otevřenou relaci, kterou máte, a během zkušební doby zkuste novou. Jádro spuštěné s ipv6.disable=1 rozbije pam_radius 2.0 – kód se nevyžádá nikomu.",
 "The file for isemon is saved. Put it in on the isemon machine as README.txt in it says, then Try it on every node and Switch over.": "Soubor pro isemon je uložený. Nasaďte ho na stroji isemonu podle README.txt v něm, pak Vyzkoušet na každém uzlu a Přepnout.",
}
P208 = {
 "pam_radius is not on {0} - otp installs it when this is saved (RHEL: from EPEL - dnf install epel-release first).":
  "pam_radius není na {0} – otp ho nainstaluje po uložení (RHEL: z EPEL – nejdřív dnf install epel-release).",
}
S208.update({
 "Send a test sign-in…": "Poslat zkušební přihlášení…",
 "A test sign-in for isemon": "Zkušební přihlášení pro isemon",
 "As the user": "Jako uživatel",
 "Success or Failure (s / f)": "Úspěch nebo neúspěch (s / f)",
 "Send it": "Poslat",
})
P208.update({
 "A line in the very shape of totpcgi's (totp.cgi), from {0} to every isemon receiver: isemon shows it as a sign-in of the name given - its message says it is a test.":
  "Řádek přesně ve tvaru totpcgi (totp.cgi) z {0} do každého přijímače isemonu: isemon ho ukáže jako přihlášení zadaného jména – jeho zpráva říká, že jde o test.",
 "isemon shows it under this name as a sign-in from {0}, \"Success\" or \"Failure\" as chosen; its message says it is a test from otp. Nothing is checked and nothing is written into this node's files.":
  "isemon ho ukáže pod tímto jménem jako přihlášení z {0}, „Success“ nebo „Failure“ podle volby; jeho zpráva říká, že jde o test z otp. Nic se neověřuje a nic se nezapisuje do souborů tohoto uzlu.",
})
