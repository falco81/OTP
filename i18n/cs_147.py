S147 = {
 "Codes": "Kódy",
 "the app": "aplikace",
 "e-mail": "e-mail",
 "every kind": "všechny druhy",
 "codes by e-mail": "kódy e-mailem",
 "codes by SMS": "kódy SMS",
 "as the settings say": "podle nastavení",
 "text": "text",
 "Test it, or another way": "Vyzkoušet, nebo jinak",
 "A message the way a code goes, with a code that opens nothing - or a token in the app, made anew.": "Zpráva stejnou cestou jako kód, s kódem, který nic neotevře – nebo nový token v aplikaci.",
 "how the codes come: app, mail or sms": "jak kódy chodí: app, mail nebo sms",
 "where the codes are sent": "kam se kódy posílají",
 "the language of the codes: cs or en": "jazyk kódů: cs nebo en",
 "a mail token's mail: html or text": "mail tokenu e-mailem: html nebo text",
}
P147 = {
 "{0} in use · {1} never used": "{0} v provozu · {1} nikdy nepoužito",
 "{0} in use · {1} never used · {2} app · {3} e-mail · {4} SMS": "{0} v provozu · {1} nikdy nepoužito · {2} aplikace · {3} e-mail · {4} SMS",
 "kind is app, mail or sms - not {0}": "druh je app, mail nebo sms – ne {0}",
 "lang is cs or en - not {0}": "jazyk je cs nebo en – ne {0}",
 "mail is html or text - not {0}": "mail je html nebo text – ne {0}",
}
R147 = {}
S147.update({
 "The codes": "Kódy",
 "What they say": "Co v nich stojí",
 "SMS": "SMS",
 "The Teltonika gateway": "Brána Teltonika",
 "An HTTP gateway": "HTTP brána",
 "A modem on this machine": "Modem na tomto stroji",
 "TRB140, RUT… on the network: sent through its own API, the way zigmon sends its texts.": "TRB140, RUT… v síti: posílá se přes její vlastní API, stejně jako zprávy zigmonu.",
 "An operator’s or a service’s HTTP API: where, how, with what key, and what it answers when a text went.": "HTTP API operátora nebo služby: kam, jak, s jakým klíčem a co odpoví, když zpráva odešla.",
 "smstools3 or gammu-smsd: every text a file in their spool folder, sent by their own daemon.": "smstools3 nebo gammu-smsd: každá zpráva je soubor v jejich složce spool a odešle ji jejich vlastní démon.",
 "SMS is off: codes by SMS cannot be chosen on the enrolment pages, and the realms do not offer them.": "SMS jsou vypnuté: kódy SMS nelze na stránkách registrace zvolit a realmy je nenabízejí.",
})
S147.update({
 "An SMS gateway with an HTTP API (most operators and services), or a GSM modem on this machine run by smstools3 or gammu-smsd: otp writes each message as a file into its spool folder, or a Teltonika gateway (TRB140, RUT…) on the network through its own API, the way zigmon sends its texts. Off: SMS cannot be chosen on the enrolment pages.": "SMS brána s HTTP API (většina operátorů a služeb), GSM modem na tomto stroji obsluhovaný smstools3 nebo gammu-smsd: otp zapíše každou zprávu jako soubor do jeho složky spool, nebo brána Teltonika (TRB140, RUT…) v síti přes její vlastní API, stejně jako posílá zprávy zigmon. Vypnuto: SMS nelze na stránkách registrace zvolit.",
 "For POST. Starting with { it is JSON and the values are written as JSON strings: {\"to\": \"{to}\", \"text\": \"{text}\"}; otherwise a form: to={to}&text={text}. Empty: the address alone.": "Pro POST. Začíná-li {, je to JSON a hodnoty se zapíší jako řetězce JSON: {\"to\": \"{to}\", \"text\": \"{text}\"}; jinak formulář: to={to}&text={text}. Prázdné: jen adresa.",
 "smstools3: /var/spool/sms/outgoing. A file \"To: 420…\" and the text is written there and the modem's daemon sends it. The service runs as otp: that user needs to be able to write into the folder (a group, chmod g+w).": "smstools3: /var/spool/sms/outgoing. Zapíše se tam soubor „To: 420…“ s textem a démon modemu ho odešle. Služba běží jako otp: ten uživatel musí do složky smět zapisovat (skupina, chmod g+w).",
 "Some gateways answer 200 to everything: a word their answer holds only when it was sent - \"ok\", \"\"status\":\"sent\"\". Empty: any 2xx answer.": "Některé brány odpovídají 200 na všechno: slovo, které jejich odpověď obsahuje jen při odeslání – „ok“, „\"status\":\"sent\"“. Prázdné: jakákoli odpověď 2xx."
})
S147.update({
 "The certificates it is checked against": "Certifikáty, proti kterým se ověřuje",
 "The gateway’s own certificate (a TRB makes one itself), or the root and the chain of the authority that signed it. With some here only these are trusted, and a gateway written as an address is not checked for a name. With none, the authorities this machine trusts - and the name.": "Vlastní certifikát brány (TRB si ho vyrábí sám), nebo kořen a řetězec autority, která ho podepsala. Jsou-li tu nějaké, věří se jen jim a u brány zadané adresou se nekontroluje jméno. Bez nich se věří autoritám tohoto stroje – i se jménem.",
 "Read it from the gateway": "Načíst z brány",
 "none imported": "žádný nenahrán",
 "What the gateway shows - check the fingerprint against the one on the gateway (System → Administration → Certificates) before Save the changes trusts it:": "Co brána ukazuje – než mu Uložit změny dá důvěru, porovnejte otisk s tím na bráně (System → Administration → Certificates):",
 "Take every certificate of the SMS gateway away": "Odebrat všechny certifikáty SMS brány",
 "The gateway’s certificate will then have to be signed by an authority this machine already trusts, or the check has to be switched off.": "Certifikát brány pak bude muset podepsat autorita, které tento stroj už věří, nebo se kontrola musí vypnout.",
 "save the gateway’s address first": "nejdřív uložte adresu brány",
 "Checked against the certificates imported below - the gateway's own (read from it with one click) or the authority and chain that signed it; with none imported, against the authorities this machine trusts. Off: any certificate is taken.": "Ověřuje se proti certifikátům nahraným níže – vlastnímu certifikátu brány (načte se z ní jedním klikem) nebo autoritě a řetězci, které ho podepsaly; bez nich proti autoritám, kterým věří tento stroj. Vypnuto: vezme se jakýkoli certifikát.",
 "is no longer trusted for the SMS gateway. The others stay.": "už není pro SMS bránu důvěryhodný. Ostatní zůstávají.",
})
P147.update({
 "the SMS gateway is checked against {0} certificate(s)": "SMS brána se ověřuje proti {0} certifikátům",
})
S147.update({
 "Typed by hand - the directory has ": "Zadáno ručně – adresář má ",
 "Typed by hand.": "Zadáno ručně.",
 "From the directory (mail) - it can be changed.": "Z adresáře (mail) – lze změnit.",
 "From the directory (mobile) - it can be changed.": "Z adresáře (mobil) – lze změnit.",
 "The directory has no mail address for them: type it.": "Adresář pro něj nemá e-mailovou adresu: zadejte ji.",
 "The directory has no mobile number for them (mobile, telephoneNumber): type it.": "Adresář pro něj nemá mobilní číslo (mobile, telephoneNumber): zadejte ho.",
 "Filled in from the directory once the person is picked.": "Vyplní se z adresáře, jakmile vyberete člověka.",
 "Filled in from the company directory - change it if the codes should go elsewhere.": "Vyplněno z firemního adresáře – změňte, pokud mají kódy chodit jinam.",
 "Filled in from the company directory - change it if the codes should go to another phone.": "Vyplněno z firemního adresáře – změňte, pokud mají kódy chodit na jiný telefon.",
})
P147.update({"Typed by hand - the directory has {0}": "Zadáno ručně – adresář má {0}"})
S147.update({"The gateway does not send the certificate of whom signed it: its own is then trusted as it is - only exactly this certificate passes.": "Brána neposílá certifikát toho, kdo ho podepsal: její vlastní se pak bere tak, jak je – projde jen přesně tento certifikát."})
S147.update({"a name, a note, a mail address, a phone number…": "jméno, poznámka, e-mail, telefonní číslo…",
 "where the codes are sent: a mail address, or a phone number however written": "kam se kódy posílají: e-mail, nebo telefonní číslo zapsané jakkoli"})
