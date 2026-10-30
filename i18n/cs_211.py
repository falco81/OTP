# 1.0.182: SNMPv3.
S211 = {
 "Each node answers SNMPv3 itself - an agent of otp, no snmpd: the system group and otp’s own objects (OTP-MIB, <code>deploy/OTP-MIB.txt</code>), read only. authPriv only: a user with a passphrase for each.":
  "Každý uzel odpovídá na SNMPv3 sám – agent otp, žádný snmpd: skupina system a vlastní objekty otp (OTP-MIB, <code>deploy/OTP-MIB.txt</code>), jen pro čtení. Jen authPriv: uživatel s heslem pro každé z obou.",
 "Port (UDP)": "Port (UDP)",
 "161 is SNMP’s. Another where snmpd of the system has it already.": "161 je port SNMP. Jiný tam, kde ho už má snmpd systému.",
 "Listen on": "Naslouchat na",
 "Empty: every address of the node. Or one of its addresses.": "Prázdné: všechny adresy uzlu. Nebo jedna z jeho adres.",
 "The addresses or networks the monitoring asks from, <code>10.0.5.0/24, 192.0.2.7</code>. Empty: anybody with the user and its passphrases. The firewall lets in these only.":
  "Adresy nebo sítě, ze kterých se monitoring ptá, <code>10.0.5.0/24, 192.0.2.7</code>. Prázdné: kdokoli s uživatelem a jeho hesly. Firewall pustí jen tyto.",
 "User": "Uživatel",
 "The SNMPv3 user (securityName) the monitoring asks as - the same on every node.": "Uživatel SNMPv3 (securityName), pod kterým se monitoring ptá – stejný na všech uzlech.",
 "Authentication": "Ověřování",
 "HMAC of every message. SHA-256 or SHA-512; SHA-1 only for old monitoring.": "HMAC každé zprávy. SHA-256 nebo SHA-512; SHA-1 jen pro starý monitoring.",
 "Its passphrase (authentication)": "Jeho heslo (ověřování)",
 "SNMP only from": "SNMP jen z",
 "12 characters at least. Kept sealed.": "Alespoň 12 znaků. Uložené zapečetěné.",
 "Encryption": "Šifrování",
 "Every message encrypted. AES-256 is net-snmp’s and Zabbix’s (“AES256”, not Cisco’s “AES256C”).": "Každá zpráva šifrovaná. AES-256 je ten z net-snmp a Zabbixu („AES256“, ne „AES256C“ od Cisca).",
 "Its passphrase (encryption)": "Jeho heslo (šifrování)",
 "12 characters at least - best not the same as the other. Kept sealed.": "Alespoň 12 znaků – nejlépe jiné než to druhé. Uložené zapečetěné.",
 "Contact (sysContact)": "Kontakt (sysContact)",
 "Who looks after it - as sysContact.0 says.": "Kdo se o něj stará – jak říká sysContact.0.",
 "Location (sysLocation)": "Umístění (sysLocation)",
 "Where it is - as sysLocation.0 says.": "Kde je – jak říká sysLocation.0.",
 "Traps when something is wrong": "Trapy, když je něco špatně",
 "An SNMPv2 trap (authPriv) when something goes wrong - what the alerts see - and when it is right again, from the node that sends the alerts.":
  "SNMPv2 trap (authPriv), když se něco pokazí – co vidí upozornění – a když je to zase v pořádku, z uzlu, který posílá upozornění.",
 "Where traps go": "Kam jdou trapy",
 "host or host:port (162 by default), separated by commas. The receiver knows the user with each node’s engine ID (shown below).":
  "host nebo host:port (výchozí 162), oddělené čárkami. Přijímač zná uživatele s engine ID každého uzlu (uvedené níže).",
 "SNMPv3": "SNMPv3",
 "Off - switch it on above, with the user and its passphrases.": "Vypnuto – zapněte ho výše, s uživatelem a jeho hesly.",
 "On, but the user or a passphrase is not set: nothing is answered yet.": "Zapnuto, ale uživatel nebo heslo není nastavené: zatím se nic neodpovídá.",
 "not heard from": "neozval se",
 "listening": "naslouchá",
 "not listening": "nenaslouchá",
 "Engine ID": "Engine ID",
 "Engine boots": "Starty engine",
 "Asked / answered": "Dotazů / odpovědí",
 "Last asked from": "Naposledy se ptal",
 "Traps sent": "Odeslané trapy",
 "Ask it": "Zeptat se",
 "Send a test trap": "Poslat zkušební trap",
 "In the monitoring": "V monitoringu",
 "The passphrases are not shown here - they are those set above (kept sealed). AES-256 is net-snmp's AES256 and Zabbix's AES256, not Cisco's AES256C.":
  "Hesla se tu neukazují – jsou to ta nastavená výše (uložená zapečetěná). AES-256 je AES256 z net-snmp a Zabbixu, ne AES256C od Cisca.",
 "the engine ID was copied": "engine ID zkopírováno",
}
P211 = {
 "Each node answers by itself, at its own address, with an engine ID of its own - the monitoring asks every node, as with Prometheus. authPriv only: the user and its two passphrases above. otp's objects are under {0} (OTP-MIB, deploy/OTP-MIB.txt in the package).":
  "Každý uzel odpovídá sám, na své vlastní adrese, s vlastním engine ID – monitoring se ptá každého uzlu, stejně jako Prometheus. Jen authPriv: uživatel a jeho dvě hesla výše. Objekty otp jsou pod {0} (OTP-MIB, deploy/OTP-MIB.txt v balíčku).",
 "{0} asks its own agent on 127.0.0.1 as the monitoring would: discovery, then a GET with the user and its passphrases (authPriv).":
  "{0} se zeptá vlastního agenta na 127.0.0.1 jako monitoring: discovery, pak GET s uživatelem a jeho hesly (authPriv).",
 "A trap from {0} to every receiver set, now - with its engine ID, authPriv.": "Trap z {0} hned na všechny nastavené přijímače – s jeho engine ID, authPriv.",
 "The test trap went to {0}": "Zkušební trap odešel na {0}",
 "It answered itself in {0} ms: {1}": "Odpověděl sám sobě za {0} ms: {1}",
 "Last trap: {0}": "Poslední trap: {0}",
}
