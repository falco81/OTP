# 1.0.181: SSH tokens of their own, otp's gate for SSH on 127.0.0.1.
S210 = {
 "sshd asks for a code where it would ask for the account's password - from an SSH token of the account, below: tokens of their own, not the VPN's, in no realm and no RADIUS client. pam_radius asks otp's own gate on 127.0.0.1 of each node, on a free port of 18129-18199 each node finds for itself.":
  "sshd chce kód tam, kde by chtěl heslo účtu – z SSH tokenu účtu níže: jsou to samostatné tokeny, ne tokeny VPN, nejsou v žádném realmu ani RADIUS klientovi. pam_radius se ptá vlastní brány otp na 127.0.0.1 každého uzlu, na volném portu z 18129–18199, který si každý uzel najde sám.",
 "otp's gate for SSH": "Brána otp pro SSH",
 "not listening": "neposlouchá",
 "SSH tokens": "SSH tokeny",
 "None yet. Each account that is to sign in with a code needs one - its name as on the nodes (jan, root…).":
  "Zatím žádný. Každý účet, který se má přihlašovat s kódem, potřebuje jeden – se jménem jako na uzlech (jan, root…).",
 "Account": "Účet",
 "Note": "Poznámka",
 "Made": "Vytvořen",
 "Last used": "Naposledy použit",
 "never": "nikdy",
 "A new one…": "Nový…",
 "Remove": "Odebrat",
 "Make a new one": "Vytvořit nový",
 "The app's secret is made anew: the one in the app now stops giving codes that work. Scan the new one right after.":
  "Tajný klíč aplikace se vytvoří znovu: ten, který je teď v aplikaci, přestane dávat platné kódy. Nový hned naskenujte.",
 "Add an SSH token…": "Přidat SSH token…",
 "Add an SSH token": "Přidat SSH token",
 "A token of its own for signing in over SSH - not a VPN token. The QR code is shown once, right after: have the app at hand.":
  "Samostatný token pro přihlášení přes SSH – ne token VPN. QR kód se ukáže jen jednou, hned potom: mějte aplikaci po ruce.",
 "The account": "Účet",
 "Its name on the nodes - the name typed at ssh.": "Jeho jméno na uzlech – jméno zadané u ssh.",
 "Whose it is - for you, nothing else.": "Čí je – jen pro vás, nic víc.",
 "Make it": "Vytvořit",
}
P210 = {
 "A new SSH token for {0}": "Nový SSH token pro {0}",
 "Remove the SSH token of {0}": "Odebrat SSH token účtu {0}",
 "{0} then gets no code over SSH - with the system password when otp does not answer off, not in at all but with a key.":
  "{0} pak přes SSH kód nedostane – s vypnutým systémovým heslem při nedostupném otp se nedostane dovnitř vůbec, jen klíčem.",
 "The SSH token of {0}": "SSH token účtu {0}",
 "Scan it with the authenticator application now, or type the key in - it is not shown again. Then ssh {0}@{1} (any node): the code where the password is asked.":
  "Naskenujte ho teď autentizační aplikací, nebo opište klíč – znovu se neukáže. Pak ssh {0}@{1} (kterýkoli uzel): kód tam, kde se ptá na heslo.",
 "the SSH token of {0} is made - scan it now, it is not shown again": "SSH token účtu {0} je vytvořený – naskenujte ho teď, znovu se neukáže",
}
S210.update({
 "PostgreSQL here has a certificate from otp’s own authority, renewed by itself 45 days before it ends - and made again when the machine’s names change. Renewed while everything runs: PostgreSQL takes the new one with a reload, no restart - the connections go on, RADIUS does not notice.":
  "PostgreSQL tady má certifikát od vlastní autority otp, který se sám obnoví 45 dní před koncem – a znovu se vytvoří, když se změní jména stroje. Obnovuje se za chodu: PostgreSQL si nový vezme reloadem, bez restartu – spojení běží dál, RADIUS nic nepozná.",
 "Each node checks its own PostgreSQL with otp’s own authority - its certificate the one the link between the databases has, renewed with it by itself 45 days before it ends (the authority two years before), as the replication’s: with a reload of PostgreSQL, no restart - nothing stops. Either is switched off without the other.":
  "Každý uzel ověřuje svůj PostgreSQL vlastní autoritou otp – jeho certifikát je ten, který má spojení mezi databázemi, a obnovuje se s ním sám 45 dní před koncem (autorita dva roky předem), stejně jako u replikace: reloadem PostgreSQL, bez restartu – nic se nezastaví. Každé z nich jde vypnout bez druhého.",
 "The server’s certificate is checked with the authority given. That server’s certificate is renewed by its administrator - otp only checks it.":
  "Certifikát serveru se ověřuje zadanou autoritou. Ten certifikát obnovuje správce toho serveru – otp ho jen ověřuje.",
 "A token of its own for signing in over SSH - not a VPN token. From an app (the QR code shown once, right after: have the app at hand), or codes sent by mail or SMS where sending is set up.":
  "Samostatný token pro přihlášení přes SSH – ne token VPN. Z aplikace (QR kód se ukáže jen jednou, hned potom: mějte aplikaci po ruce), nebo kódy posílané e-mailem či SMS, kde je odesílání nastavené.",
 "An app": "Aplikace", "By mail": "E-mailem", "By SMS": "SMS",
 "The codes come": "Kódy chodí",
 "By mail or SMS: Enter at the first prompt of ssh, then the code that was sent.":
  "E-mailem nebo SMS: u první výzvy ssh jen Enter, pak kód, který přišel.",
 "Where to": "Kam",
 "The address or the number the codes go to.": "Adresa nebo číslo, kam kódy chodí.",
 "The codes": "Kódy",
 "an app": "aplikace",
 "sending mail is not set up (Settings → Mail)": "odesílání e-mailů není nastavené (Nastavení → Mail)",
 "sending SMS is not set up (Settings → Codes by e-mail and SMS)": "odesílání SMS není nastavené (Nastavení → Kódy e-mailem a SMS)",
 "SSH: a sign-in code by mail": "SSH: kód pro přihlášení e-mailem",
 "SSH: a sign-in code by SMS": "SSH: kód pro přihlášení SMS",
 "Sent when somebody signs in over SSH to the nodes with an SSH token by mail.": "Posílá se, když se někdo přihlašuje přes SSH na uzly s SSH tokenem e-mailem.",
 "Sent when somebody signs in over SSH to the nodes with an SSH token by SMS.": "Posílá se, když se někdo přihlašuje přes SSH na uzly s SSH tokenem přes SMS.",
})
P210.update({
 "The SSH token {0} has now stops working the moment this one is made - an app's secret is made anew.":
  "SSH token, který má {0} teď, přestane platit ve chvíli, kdy se vytvoří tento – tajný klíč aplikace se vytvoří znovu.",
 "mail · {0}": "e-mail · {0}", "SMS · {0}": "SMS · {0}",
 "the SSH token of {0} is made - its codes go to {1}": "SSH token účtu {0} je vytvořený – kódy chodí na {1}",
})
