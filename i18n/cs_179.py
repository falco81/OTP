# 1.0.143: going back to an older version - only a safe one.
S179 = {
 "Going back to an older version": "Návrat na starší verzi",
 "Only to a version that is safe: one that reads what the newer versions wrote into the database the same, and has every security fix that matters - each version says how far back it may go, and the highest of what ran on this database and was installed on this machine counts. The database is not put back nor changed: its tables stay as they are and the older version runs on them, so it does not matter how big it is. The package is checked like an upgrade's, and against this database's tables, before anything is put in; then the nodes go back one at a time, as in an upgrade.": "Jen na verzi, u které je to bezpečné: takovou, která čte, co novější verze zapsaly do databáze, stejně, a má všechny podstatné bezpečnostní opravy – každá verze říká, jak daleko zpět smí, a platí nejvyšší hranice ze všech verzí, které běžely nad touto databází a byly nainstalované na tomto stroji. Databáze se neobnovuje ani nemění: tabulky zůstanou, jak jsou, a starší verze nad nimi běží, takže nezáleží na tom, jak je velká. Balík se před nasazením zkontroluje jako u aktualizace a navíc proti tabulkám této databáze; pak se uzly vracejí jeden po druhém, jako při aktualizaci.",
 "Show the versions to go back to": "Ukázat verze, na které se lze vrátit",
 "Can it go back to it": "Lze se na ni vrátit",
 "No version older than this one is there.": "Žádná starší verze tam není.",
 "Go back on every node, one at a time": "Vrátit všechny uzly, jeden po druhém",
 "Go back on this server": "Vrátit tento server",
 "Go back": "Vrátit",
 "yes": "ano",
}
P179 = {
 "Go back to {0}": "Vrátit na {0}",
 "Go back to otp {0}?": "Vrátit na otp {0}?",
 "otp {0} - older: ready to go back to": "otp {0} – starší: připravená k návratu",
 "At {0} - this server runs {1}; it may go back to {2} or newer.": "Na {0} – tento server běží na {1}; smí se vrátit na {2} nebo novější.",
 "The version running now is replaced by the older {0} on every node, one at a time - each in maintenance while it is, so the service never stops. The database stays as it is. What came in the newer versions is gone until you upgrade again.": "Verze, která teď běží, se na všech uzlech, jednom po druhém, nahradí starší {0} – každý je přitom v údržbě, takže služba nikdy nestojí. Databáze zůstane, jak je. Co přinesly novější verze, zmizí, dokud znovu neaktualizujete.",
 "The version running now is replaced by the older {0} - for a minute nobody can sign in to the VPN. The database stays as it is. What came in the newer versions is gone until you upgrade again.": "Verze, která teď běží, se nahradí starší {0} – na minutu se nikdo nepřihlásí do VPN. Databáze zůstane, jak je. Co přinesly novější verze, zmizí, dokud znovu neaktualizujete.",
 "otp {0} is fetched, checked for this database and ready to go back to": "otp {0} je stažená, zkontrolovaná proti této databázi a připravená k návratu",
 "otp {0} fetched and checked; going back to it has begun": "otp {0} stažená a zkontrolovaná; návrat na ni začal",
 "otp {0} cannot be gone back to: {1}": "na otp {0} se nelze vrátit: {1}",
 "older than {0}: otp {1}, which ran on this database, wrote what older versions do not read the same (or have holes it fixed)": "starší než {0}: otp {1}, která běžela nad touto databází, zapsala data, která starší verze nečtou stejně (nebo mají díry, které opravila)",
 "older than {0}, the oldest the versions installed on this machine allow": "starší než {0}, nejstarší verze, kterou dovolují verze nainstalované na tomto stroji",
 "this machine was never upgraded on the command line to a version that can go back (install.sh --upgrade once)": "tento stroj nebyl nikdy z příkazové řádky aktualizován na verzi, která umí návrat (jednou install.sh --upgrade)",
 "the table {0} has {1}, which otp {2} does not know and every row needs": "tabulka {0} má {1}, které otp {2} nezná a každý řádek to potřebuje",
 "{0} is not older than {1}, which runs here - that is an upgrade": "{0} není starší než {1}, která tu běží – to je aktualizace",
 "Going back to {0} · started by {1} · {2} · {3}": "Návrat na {0} · spustil {1} · {2} · {3}",
}
