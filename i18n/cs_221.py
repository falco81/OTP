# 1.0.202: the proxy - a switch for each thing that may go through it.
S221 = {
 "The new versions of otp": "Nové verze otp",
 "The system updates (dnf, apt)": "Aktualizace systému (dnf, apt)",
 "ACME: the CA (Let’s Encrypt)": "ACME: certifikační autorita (Let’s Encrypt)",
 "ACME: the DNS APIs (deSEC, Cloudflare, acme-dns)": "ACME: DNS API (deSEC, Cloudflare, acme-dns)",
 "The SMS gateway": "SMS brána",
 "An HTTP proxy for what is switched on below, and for nothing else; all of them off, it is used nowhere. Mail, Active Directory, the database, syslog, isemon, the backups, the other node and the VIP address’s check never use it.":
  "HTTP proxy pro to, co je níže zapnuté, a pro nic jiného; vše vypnuté – nepoužívá se nikde. Pošta, Active Directory, databáze, syslog, isemon, zálohy, druhý uzel a kontrola VIP adresy ji nepoužívají nikdy.",
 "Looking for a new version of otp and fetching it (Upgrades).": "Hledání nové verze otp a její stažení (Upgrady).",
 "dnf or apt fetch the updates of System updates through it.": "dnf nebo apt přes ni stahují aktualizace systému.",
 "Ordering and renewing the certificates, and the CA’s renewal window. A proxy down then stops the renewals - they are tried again, well before one runs out.":
  "Objednávání a obnova certifikátů a okno obnovy od CA. Nedostupná proxy pak obnovy zastaví – zkoušejí se znovu, dlouho předtím, než certifikát vyprší.",
 "The TXT record put in and taken away again (DNS-01) through the API of deSEC, Cloudflare or acme-dns. RFC 2136 updates are DNS, never through it.":
  "Vložení a odebrání záznamu TXT (DNS-01) přes API deSEC, Cloudflare nebo acme-dns. Aktualizace RFC 2136 jsou DNS, přes ni nikdy nejdou.",
 "The HTTP SMS gateway asked through it. A proxy down then stops the codes by SMS - leave it off unless the gateway can be reached no other way.":
  "HTTP SMS brána se volá přes ni. Nedostupná proxy pak zastaví kódy přes SMS – nechte vypnuté, pokud bránu nejde dosáhnout jinak.",
 "An HTTP proxy, for what you switch on: the new versions, the system updates, ACME, the SMS gateway.":
  "HTTP proxy pro to, co zapnete: nové verze, aktualizace systému, ACME, SMS brána.",
 "Where the servers may reach the web only through an HTTP proxy - on every node. Off by default, and switched on it is used only for what is switched on below: the new versions of otp, the system updates, ACME and its DNS APIs, the SMS gateway; all of them off, nowhere. RADIUS, mail, Active Directory, the database, syslog, isemon, the backups, the other node and the VIP address's check never go through it.":
  "Kde servery smí na web jen přes HTTP proxy – na každém uzlu. Ve výchozím stavu vypnutá; zapnutá se použije jen pro to, co je níže zapnuté: nové verze otp, aktualizace systému, ACME a jeho DNS API, SMS brána; vše vypnuté – nikde. RADIUS, pošta, Active Directory, databáze, syslog, isemon, zálohy, druhý uzel a kontrola VIP adresy přes ni nikdy nejdou.",
}
P221 = {}
