# 1.0.81: a Teltonika SMS gateway; the second window in the tests
S143 = {
"a Teltonika gateway (TRB140, RUT…) on the network - as zigmon uses it": "brána Teltonika (TRB140, RUT…) v síti – stejně jako ji používá zigmon",
"RutOS’s own API (/api, RutOS 7 - the default)": "vlastní API RutOS (/api, RutOS 7 – výchozí)",
"the older Post/Get SMS service (/cgi-bin/sms_send)": "starší služba Post/Get SMS (/cgi-bin/sms_send)",
"The Teltonika’s address": "Adresa Teltoniky",
"Over HTTPS": "Přes HTTPS",
"Check its certificate": "Ověřovat její certifikát",
"Its user": "Její uživatel",
"Its password": "Její heslo",
"Its interface": "Její rozhraní",
"Its modem": "Její modem",
"Without accents (one SMS, not two)": "Bez diakritiky (jedna SMS, ne dvě)",
"The gateway on the network: 192.168.1.1, or host:port. The same box zigmon sends its texts through can send these too.":
"Brána v síti: 192.168.1.1 nebo host:port. Tutéž krabičku, přes kterou posílá SMS zigmon, může používat i otp.",
"A TRB serves both; HTTPS keeps its password and the codes off the wire.": "TRB umí obojí; HTTPS chrání její heslo i kódy na cestě.",
"A TRB makes its own certificate, which nothing can check: off, unless yours has one from an authority this machine trusts.":
"TRB si vyrábí vlastní certifikát, který nejde ověřit: vypnuto, pokud ta vaše nemá certifikát od autority, které tento stroj věří.",
"An account of the gateway that may use its API (admin, or one made for this under System → Administration → User settings).":
"Účet brány, který smí používat její API (admin, nebo účet založený pro tento účel v System → Administration → User settings).",
"Its password, kept sealed in the database. Never shown again.": "Jeho heslo, uložené zapečetěné v databázi. Znovu se nezobrazí.",
"RutOS 7 offers its own API out of the box; the older Post/Get service has to be switched on by hand under Services → Mobile Utilities → SMS gateway.":
"RutOS 7 nabízí vlastní API rovnou; starší službu Post/Get je třeba zapnout ručně v Services → Mobile Utilities → SMS gateway.",
"Which modem sends - 1-1, 3-1… Empty: the one the gateway names first.": "Který modem posílá – 1-1, 3-1… Prázdné: ten, který brána uvede jako první.",
"A letter with an accent makes the whole SMS the wide alphabet, 70 characters a part instead of 160: the code goes in one message when the accents are left out (kód → kod).":
"Jediné písmeno s diakritikou přepne celou SMS do širší abecedy, 70 znaků na část místo 160: bez diakritiky se kód vejde do jedné zprávy (kód → kod).",
"Access-Challenge": "Access-Challenge",
"Send the code": "Poslat kód",
}
P143 = {
"The VPN now shows a second window: ": "VPN teď ukáže druhé okno: ",
}
R143 = {}
S143["The VPN now shows a second window."] = "VPN teď ukáže druhé okno."
S143["The VPN now shows a second window: "] = "VPN teď ukáže druhé okno: "
