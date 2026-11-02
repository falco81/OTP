# 1.0.230: the cap of wrong directory passwords per person.
S239 = {
 "Wrong directory passwords per person, on these pages and the enrolment pages": "Špatná hesla z adresáře na osobu, na těchto stránkách a na stránkách registrace",
 "...counted over (min)": "…počítaná za (min)",
 "A directory password is tried against Active Directory at each sign-in to the enrolment pages, at each new token there, and at each sign-in to these pages of an administrator from the directory. Each of them counts on its own and on each node alone - together, with many addresses, enough wrong ones for a name reach the directory to lock the account there: e-mail, the VPN and the PC with it. Set below the directory's own lockout threshold (3 for a threshold of 5 to 10): after so many wrong passwords for one name within the time below, from anywhere, on any node, the directory is no longer asked for that name - only these pages wait, the account in the directory stays unlocked. Cleared under Locked out. 0: no cap of its own (as until now). RADIUS is not affected.":
  "Heslo z adresáře se ověřuje v Active Directory při každém přihlášení na stránky registrace, při každém novém tokenu tam a při každém přihlášení správce z adresáře na tyto stránky. Každé z nich se počítá zvlášť a na každém uzlu zvlášť – dohromady, z mnoha adres, tak do adresáře dojde dost špatných hesel na zamčení účtu: a s ním e-mailu, VPN i počítače. Nastavte pod práh zamčení v adresáři (3 pro práh 5 až 10): po tolika špatných heslech pro jedno jméno v čase níže, odkudkoli a na kterémkoli uzlu, se adresáře na to jméno už neptá – čekají jen tyto stránky, účet v adresáři zůstane odemčený. Ruší se v části Zablokovaní. 0: bez vlastního stropu (jako dosud). RADIUS to neovlivní.",
 "How long a wrong directory password counts towards the cap above. As long as the directory's \"Reset account lockout counter after\", or longer.": "Jak dlouho se špatné heslo z adresáře počítá do stropu výše. Stejně dlouho jako „Vynulovat čítač uzamčení účtu po“ v adresáři, nebo déle.",
 "directory passwords tried on the pages": "hesla z adresáře zkoušená na stránkách",
 "wrong directory passwords": "špatná hesla z adresáře",
}
P239 = {
 "too many wrong passwords for this name: try again in {0} min": "příliš mnoho špatných hesel pro toto jméno: zkuste to znovu za {0} min",
}
