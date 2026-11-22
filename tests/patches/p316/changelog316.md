## 1.0.316 — 22 November 2026

**Bug fix**: in Czech, three hints of the certificate sign-in (*Settings → People*: the CRL Distribution Point in the directory, the OCSP responder, its own address) were still in English, and so were the directory's reasons for a refused sign-in (the password has expired, the account is locked out, may not sign in at this time of day …) and what a database agent puts in. They are in Czech now.

**Bug fix**: on *Settings → Logs*, what a node said when it could not put the settings in (*the root helper of this node did not answer …*) stayed in English on Czech pages; otp's own words are now in the page's language.

**Bug fix**: the API's fetching of the SMS gateway's certificate (*Codes by e-mail and SMS*) with no address of the Teltonika gateway set answered 502, as if the gateway had failed; it now answers 400 - something to put in first. (The pages ask for the address before they ask.)

