# 1.0.239: signed in by a load balancer or WAF (SSO) on the enrolment pages.
S249 = {
 # the settings
 "Signed in by the load balancer or WAF (SSO)": "Přihlášení přes load balancer nebo WAF (SSO)",
 "The balancers that sign people in": "Balancery, které přihlašují",
 "The header with who signed in": "Hlavička se jménem přihlášeného",
 "The key the balancer sends": "Klíč, který balancer posílá",
 "Where signing out goes": "Kam vede odhlášení",
 "The enrolment pages published through a NetScaler, an F5 or another balancer or WAF that signs people in against the directory first: who it signed in comes in a header, and the pages ask no password again. Only from the balancers' own addresses below, and only with the key below - nobody else's header is believed. The directory is still asked who it is, the realm's groups and who may enrol still decide, and the one-time code by mail or SMS before the first token is still sent. The administration pages are not concerned. Off: the pages as until now.":
  "Stránky registrace publikované přes NetScaler, F5 nebo jiný balancer či WAF, který lidi nejdřív sám přihlásí proti adresáři: koho přihlásil, přijde v hlavičce, a stránky se na heslo už znovu neptají. Jen z vlastních adres balancerů níže a jen s klíčem níže – hlavičce od kohokoli jiného se nevěří. Adresář se i tak zeptá, kdo to je, rozhodují skupiny realmu i to, kdo smí registrovat, a jednorázový kód e-mailem nebo SMS před prvním tokenem se i tak pošle. Administrace se to netýká. Vypnuto: stránky jako dosud.",
 "The balancers' own addresses or networks, as this node sees the connection come in (not the client's) - one or more, separated by spaces. Needed to switch it on.":
  "Vlastní adresy nebo sítě balancerů, jak tento uzel vidí přicházet spojení (ne adresa klienta) – jedna nebo víc, oddělené mezerou. Bez nich to zapnout nejde.",
 "Where the balancer puts the name it signed in: X-Otp-User, or the one it already sends. The name as people type it - novak, novak@example.cz or EXAMPLE\\novak - as on the sign-in of these pages.":
  "Kam balancer dává jméno, které přihlásil: X-Otp-User, nebo ta, kterou už posílá. Jméno tak, jak ho lidé píšou – novak, novak@example.cz nebo EXAMPLE\\novak – jako při přihlášení na těchto stránkách.",
 "Sent by the balancer in X-Otp-Sso-Key with every request, so that a header put in by anybody else is never taken. Made below (Make a key), shown once; kept sealed.":
  "Balancer ho posílá v X-Otp-Sso-Key s každým požadavkem, aby se nikdy nevzala hlavička, kterou vložil někdo jiný. Vytvoří se níže (Vytvořit klíč), ukáže se jednou; uložený zapečetěný.",
 "Where Sign out sends the browser afterwards - the balancer's own sign-out (NetScaler: /cgi/tmlogout, F5: /vdesk/hangup.php3), so that it does not sign the person in again at once. Empty: the sign-in of these pages, with a button to sign in through the balancer again.":
  "Kam Odhlásit potom pošle prohlížeč – vlastní odhlášení balanceru (NetScaler: /cgi/tmlogout, F5: /vdesk/hangup.php3), aby člověka hned znovu nepřihlásil. Prázdné: přihlášení těchto stránek, s odkazem pro nové přihlášení přes balancer.",
 "Who is believed": "Komu se věří",
 "The key and signing out": "Klíč a odhlášení",
 # errors
 "signing in through the load balancer is switched off": "přihlášení přes load balancer je vypnuté",
 "the sign-in through the load balancer was not taken here - sign in with your password, or ask the administrator":
  "přihlášení přes load balancer tu nebylo přijato – přihlaste se heslem, nebo se obraťte na správce",
 "the sign-in through the load balancer was not taken here": "přihlášení přes load balancer tu nebylo přijato",
 "sign in again": "přihlaste se znovu",
 "signed in by the load balancer: say which addresses are the balancers first (The balancers that sign people in)":
  "přihlášení přes load balancer: nejdřív uveďte, které adresy jsou balancery (Balancery, které přihlašují)",
 "signed in by the load balancer: make the key first (Make a key)":
  "přihlášení přes load balancer: nejdřív vytvořte klíč (Vytvořit klíč)",
 "portal_sso_header: the name of a header of its own, as X-Otp-User": "portal_sso_header: název vlastní hlavičky, např. X-Otp-User",
 "portal_sso_key: 24 to 200 letters, digits and -_.~+/=": "portal_sso_key: 24 až 200 písmen, číslic a -_.~+/=",
 "portal_sso_logout: an https:// address or a path starting with /": "portal_sso_logout: adresa https:// nebo cesta začínající /",
 # the enrolment pages
 "You signed out.": "Odhlásili jste se.",
 "Sign in through the company sign-in again": "Přihlásit se znovu přes firemní přihlášení",
 ", or with your name and password below.": ", nebo jménem a heslem níže.",
 "To change where your codes go, type a code we send you now - or one of your recovery codes. If you have neither, ask the administrator.":
  "Pro změnu, kam chodí vaše kódy, zadejte kód, který vám teď pošleme – nebo jeden ze záložních kódů. Pokud nemáte ani jedno, obraťte se na správce.",
 "To replace your token, type a code from the token you have now - or one of your recovery codes. If you have lost both, ask the administrator.":
  "Pro výměnu tokenu zadejte kód z tokenu, který teď máte – nebo jeden ze záložních kódů. Pokud jste ztratili obojí, obraťte se na správce.",
 # the card
 "Signed in by a load balancer or WAF (SSO)": "Přihlášení přes load balancer nebo WAF (SSO)",
 "The enrolment pages published through a NetScaler, an F5 or another balancer that signs people in against the directory first: they then come in signed in, without a second password. Off, the pages are as until now.":
  "Stránky registrace publikované přes NetScaler, F5 nebo jiný balancer, který lidi nejdřív sám přihlásí proti adresáři: na stránky pak přijdou už přihlášení, bez druhého hesla. Vypnuto jsou stránky jako dosud.",
 "A key is set": "Klíč je nastaven",
 "No key yet": "Zatím bez klíče",
 "From": "Z",
 "No balancer named": "Žádný balancer neuveden",
 "Header": "Hlavička",
 "Make a new key…": "Vytvořit nový klíč…",
 "Make a key…": "Vytvořit klíč…",
 "A key for the balancer to send in X-Otp-Sso-Key, shown once - the one before is no longer taken at once.":
  "Klíč, který bude balancer posílat v X-Otp-Sso-Key, ukáže se jednou – dosavadní se hned přestane přijímat.",
 "Make a new key for the balancer?": "Vytvořit pro balancer nový klíč?",
 "Make a key for the balancer?": "Vytvořit pro balancer klíč?",
 "The key used now is no longer taken at once - put the new one into the balancer.":
  "Dosavadní klíč se hned přestane přijímat – vložte do balanceru nový.",
 "Shown once: put it into the balancer's configuration below.": "Ukáže se jednou: vložte ho do konfigurace balanceru níže.",
 "The key for the balancer": "Klíč pro balancer",
 "Shown only now - and put into the configuration below until this page is left. The balancer sends it in X-Otp-Sso-Key with every request.":
  "Ukazuje se jen teď – a do konfigurace níže se doplňuje, dokud stránku neopustíte. Balancer ho posílá v X-Otp-Sso-Key s každým požadavkem.",
 "The enrolment pages are switched off (above): nobody is signed in by the balancer either.":
  "Stránky registrace jsou vypnuté (výše): přes balancer se tedy nepřihlásí nikdo.",
 "Switch on Settings → Firewall and access → Behind a load balancer or WAF as well, with the balancer's address: otherwise every client is the balancer's address - the sign-in pause of one is everybody's, and the logs do not say who it was.":
  "Zapněte také Nastavení → Firewall a přístup → Za load balancerem nebo WAF, s adresou balanceru: jinak je každý klient adresou balanceru – pauza přihlášení jednoho je pauzou všech a logy neřeknou, kdo to byl.",
 "Published to the internet: who may reach the enrolment pages (Settings → Firewall and access → the allow lists) must take the clients' own addresses, as the balancer passes them on - the private networks alone keep everybody from outside out.":
  "Publikováno do internetu: kdo smí na stránky registrace (Nastavení → Firewall a přístup → seznamy povolených) musí zahrnout vlastní adresy klientů, jak je balancer předává – samotné privátní sítě nikoho zvenku nepustí.",
 "The last sign-in by the balancer": "Poslední přihlášení přes balancer",
 "None yet. Open the enrolment pages through the balancer, then Look again.": "Zatím žádné. Otevřete stránky registrace přes balancer a pak Podívat se znovu.",
 "None - it is off.": "Žádné – je to vypnuté.",
 "signed in": "přihlášen",
 "refused": "odmítnuto",
 "Switched on, the configuration for NetScaler, F5 and others is shown here, filled in with this server's own values.":
  "Po zapnutí se tu ukáže konfigurace pro NetScaler, F5 a další, vyplněná vlastními hodnotami tohoto serveru.",
 "On the balancer": "Na balanceru",
 "The name people use": "Jméno, které lidé používají",
 "the pages' public name, in the balancer's certificate": "veřejné jméno stránek, v certifikátu balanceru",
 "The balancer's public address": "Veřejná adresa balanceru",
 "its virtual server for the pages": "jeho virtuální server pro stránky",
 "A domain controller": "Řadič domény",
 "LDAPS, port 636": "LDAPS, port 636",
 "Where the accounts are": "Kde jsou účty",
 "the directory's base DN": "základní DN adresáře",
 "The balancer's own account": "Vlastní účet balanceru",
 "reads the directory": "čte adresář",
 "The certificate on the balancer": "Certifikát na balanceru",
 "its name there": "jeho název tam",
 "Check it": "Ověřit",
 "nFactor / LDAP": "nFactor / LDAP",
 "access policy + iRule": "access policy + iRule",
 "any IdP": "jakékoli IdP",
 "1. Who signs in: an authentication virtual server against the directory (LDAPS)":
  "1. Kdo přihlašuje: autentizační virtuální server proti adresáři (LDAPS)",
 "2. The enrolment pages behind it - the service group of the nodes as on High availability → Load balancers":
  "2. Stránky registrace za ním – service group uzlů jako na Vysoká dostupnost → Load balancery",
 "3. The headers: what the client sent taken away first, then who signed in, the key and the client's address":
  "3. Hlavičky: nejdřív pryč, co poslal klient, pak kdo se přihlásil, klíč a adresa klienta",
 "4. Not the administration: /admin never through here": "4. Ne administrace: /admin nikdy tudy",
 "5. The WAF (Web App Firewall) in front of the pages": "5. WAF (Web App Firewall) před stránkami",
 "Signing out: set \"Where signing out goes\" above to /cgi/tmlogout - NetScaler's own sign-out. AAA.USER.NAME is the name as it was typed; with -ldapLoginName userPrincipalName it is novak@example.cz. Check the commands against your ADC's version.":
  "Odhlášení: nastavte výše „Kam vede odhlášení“ na /cgi/tmlogout – vlastní odhlášení NetScaleru. AAA.USER.NAME je jméno tak, jak bylo napsáno; s -ldapLoginName userPrincipalName je to novak@example.cz. Příkazy ověřte podle verze svého ADC.",
 "1. An access profile (Access → Profiles): Logon Page → AD Auth (or LDAP Auth) against the domain controllers → Allow. Its name below: otp_access.":
  "1. Access profile (Access → Profiles): Logon Page → AD Auth (nebo LDAP Auth) proti řadičům domény → Allow. Níže pod názvem otp_access.",
 "2. The iRule - what the client sent taken away, then who signed in and the key, /admin refused":
  "2. iRule – pryč, co poslal klient, pak kdo se přihlásil a klíč, /admin odmítnut",
 "3. tmsh: the iRule and the access profile on the virtual server of the pages (the pool of the nodes as on High availability → Load balancers)":
  "3. tmsh: iRule a access profile na virtuálním serveru stránek (pool uzlů jako na Vysoká dostupnost → Load balancery)",
 "Signing out: set \"Where signing out goes\" above to /vdesk/hangup.php3 - APM's own sign-out. session.logon.last.username is the name as typed; for the UPN use session.ad.last.attr.userPrincipalName.":
  "Odhlášení: nastavte výše „Kam vede odhlášení“ na /vdesk/hangup.php3 – vlastní odhlášení APM. session.logon.last.username je jméno tak, jak bylo napsáno; pro UPN použijte session.ad.last.attr.userPrincipalName.",
 "A reverse proxy that signs in by OIDC or SAML (oauth2-proxy here): the headers set by it, never passed on from the client":
  "Reverse proxy, která přihlašuje přes OIDC nebo SAML (zde oauth2-proxy): hlavičky nastavuje sama, od klienta se nikdy nepředávají",
 "From a machine that is not the balancer: the headers are not taken from anybody else - the page asks for the password":
  "Ze stroje, který není balancer: hlavičky se od nikoho jiného neberou – stránka chce heslo",
 "Refused ones are in Events (enrolment) with the reason: not from the balancers named, the key wrong or missing, a name the directory does not know.":
  "Odmítnutá jsou v Událostech (registrace) s důvodem: ne z uvedených balancerů, klíč špatný nebo chybí, jméno, které adresář nezná.",
 "More, with the reasons: docs/portal-sso.md in the package.": "Víc i s důvody: docs/portal-sso.md v balíčku.",
}
P249 = {
 "Pick yours: the configuration is filled in with what is set here, marked in colour, and follows what you type below. Whatever the balancer: it takes the client's own {0} and X-Otp-Sso-Key away first, puts in its own only after it signed the person in, and never passes /admin on.":
  "Vyberte svůj: konfigurace je vyplněná tím, co je tu nastaveno, barevně vyznačená, a řídí se tím, co napíšete níže. Ať je balancer jakýkoli: nejdřív odstraní {0} a X-Otp-Sso-Key, které poslal klient, vlastní vloží až poté, co člověka přihlásil, a /admin nikdy dál nepustí.",
 "portal_sso_from: {0} is not an address or a network": "portal_sso_from: {0} není adresa ani síť",
}
