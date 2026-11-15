# 1.0.283: a CSR made in the browser.
S283 = {
    'Make a CSR…': 'Vytvořit CSR…',
    'A key pair made in this browser - it never leaves it - and its certificate request (CSR) with the values above; what goes in is chosen first.':
        'Pár klíčů vytvořený v tomto prohlížeči – nikdy ho neopustí – a jeho žádost o certifikát (CSR) s hodnotami výše; co do ní půjde, se nejdřív vybere.',
    'Make a certificate request (CSR)': 'Vytvořit žádost o certifikát (CSR)',
    "The key pair is made in this browser and never leaves it: the request and the private key are handed to you as files, and nothing of them is sent to the server. For a smart card or a YubiKey (PIV) the key is made on the card instead - certreq's request.inf of the window before, or ykman.":
        'Pár klíčů se vytvoří v tomto prohlížeči a nikdy ho neopustí: žádost i soukromý klíč dostanete jako soubory a nic z nich se neposílá na server. Pro čipovou kartu nebo YubiKey (PIV) se klíč vytváří přímo na kartě – request.inf pro certreq z předchozího okna, nebo ykman.',
    'RSA 2048 (what AD CS templates ask by default)': 'RSA 2048 (co šablony AD CS chtějí ve výchozím stavu)',
    'The key': 'Klíč',
    'CN (Common Name)': 'CN (Common Name)',
    'O (organization)': 'O (organizace)',
    'OU (its unit)': 'OU (útvar)',
    'L (city)': 'L (město)',
    'ST (region)': 'ST (kraj)',
    'C (country, two letters)': 'C (země, dvě písmena)',
    'Subject Alternative Name': 'Subject Alternative Name',
    'UPN (Other Name - Principal Name)': 'UPN (Other Name – Principal Name)',
    'URL - the SID (strong mapping, KB5014754)': 'URL – SID (strong mapping, KB5014754)',
    'e-mail (RFC 822 Name)': 'e-mail (RFC 822 Name)',
    'What the certificate is for': 'K čemu certifikát slouží',
    'The template of AD CS (optional - written into the request; certreq -attrib names it too)':
        'Šablona AD CS (volitelné – zapíše se do žádosti; uvádí ji i certreq -attrib)',
    'The private key': 'Soukromý klíč',
    'Protected by a passphrase (PKCS#8, AES-256 - openssl and Windows read it)': 'Chráněný heslem (PKCS#8, AES-256 – přečte ho openssl i Windows)',
    'Passphrase': 'Heslo',
    'Again': 'Znovu',
    'Make the CSR': 'Vytvořit CSR',
    'The CN is needed.': 'CN je potřeba.',
    'C is the two letters of a country (CZ).': 'C jsou dvě písmena země (CZ).',
    'The UPN is name@domain.': 'UPN má tvar jméno@doména.',
    'The URL of the SID is tag:microsoft.com,2022-09-14:sid:S-1-5-21-...': 'URL se SID má tvar tag:microsoft.com,2022-09-14:sid:S-1-5-21-...',
    'The e-mail is not an address.': 'E-mail není adresa.',
    'The URL and the e-mail are of plain letters only.': 'URL a e-mail smějí obsahovat jen obyčejná písmena.',
    'At least one: what the certificate is for.': 'Aspoň jedno: k čemu certifikát slouží.',
    'The passphrase: 8 characters at least.': 'Heslo: aspoň 8 znaků.',
    'The passphrase typed twice differs.': 'Heslo zadané dvakrát se liší.',
    'Making the key pair and the request in this browser…': 'Vytvářím pár klíčů a žádost v tomto prohlížeči…',
    'made': 'vytvořeno',
    'Download the CSR': 'Stáhnout CSR',
    'Download the key': 'Stáhnout klíč',
    'Copy the CSR': 'Zkopírovat CSR',
    'the CSR copied': 'CSR zkopírován',
    'The private key is not kept anywhere - download it now: made again, the request has a new key.':
        'Soukromý klíč se nikde neuchovává – stáhněte ho hned: při novém vytvoření má žádost nový klíč.',
}
P283 = {
    'It could not be made: {0}': 'Nepodařilo se ji vytvořit: {0}',
}
S283.update({
    'The request below goes to AD CS (certreq -submit, or the web enrolment); the key stays with you -':
        'Žádost níže patří do AD CS (certreq -submit nebo webová registrace); klíč zůstává u vás –',
    'locked by the passphrase.': 'zamčený heslem.',
    'not locked: keep it where nobody else reads it.': 'nezamčený: uložte ho tam, kde ho nikdo jiný nepřečte.',
})
