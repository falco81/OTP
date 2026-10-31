# 1.0.201: the proxy is for the updates only.
S220 = {
 "An HTTP proxy for the updates only - the new versions of otp and the system updates.":
  "HTTP proxy jen pro aktualizace – nové verze otp a aktualizace systému.",
 "For the updates only: the new versions of otp and the system updates (dnf, apt) are fetched through it - on every node. Nothing the application does to work ever goes through it - RADIUS, the SMS gateway, mail, ACME and its DNS APIs, Active Directory, the database, syslog, isemon, the other node and the VIP address's check all go straight, so a proxy down or wrong never stops a sign-in.":
  "Jen pro aktualizace: nové verze otp a aktualizace systému (dnf, apt) se stahují přes ni – na každém uzlu. Nic, co aplikace dělá ke svému chodu, přes ni nikdy nejde – RADIUS, SMS brána, pošta, ACME a jeho DNS API, Active Directory, databáze, syslog, isemon, druhý uzel i kontrola VIP adresy jdou vždy napřímo, takže nedostupná nebo špatná proxy nikdy nezastaví přihlášení.",
 "An HTTP proxy for the updates only: the new versions of otp and the system updates. Nothing else ever uses it - the SMS gateway, mail, ACME, Active Directory, the database and syslog always go straight.":
  "HTTP proxy jen pro aktualizace: nové verze otp a aktualizace systému. Nic jiného ji nikdy nepoužívá – SMS brána, pošta, ACME, Active Directory, databáze a syslog jdou vždy napřímo.",
}
P220 = {}
