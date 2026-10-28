# 1.0.77: old, weak certificates of a directory
S140 = {
"Take old, weak certificates": "Přijímat staré, slabé certifikáty",
"For domain controllers whose certificate has a 1024-bit key or a SHA-1 signature, or that speak TLS 1.0 only: refused by default (\"EE certificate key too weak\"). The certificate is still checked against its authority and the server’s name; the encryption is as weak as the server’s. Better: give the servers new certificates.":
"Pro řadiče domény, jejichž certifikát má 1024bitový klíč nebo podpis SHA-1, případně umějí jen TLS 1.0: ve výchozím stavu se odmítají („EE certificate key too weak“). Certifikát se i tak ověřuje proti své certifikační autoritě a jménu serveru; šifrování je ale jen tak silné jako na serveru. Lepší je dát serverům nové certifikáty.",
"weak certificates taken": "přijímá slabé certifikáty",
" · weak taken": " · slabé přijímány",
}
P140 = {
"the server’s certificate was not accepted: {0}. Its key or its signature is older than OpenSSL takes by default (a 1024-bit key, SHA-1): switch on \"Take old, weak certificates\" for this directory - or better, give the server a new certificate.":
"certifikát serveru nebyl přijat: {0}. Jeho klíč nebo podpis je starší, než OpenSSL ve výchozím stavu přijímá (1024bitový klíč, SHA-1): u tohoto adresáře zapněte „Přijímat staré, slabé certifikáty“ – nebo lépe dejte serveru nový certifikát.",
"TLS to {0}:{1} did not start: {2} - an old server (a weak key, TLS 1.0): switch on \"Take old, weak certificates\" for this directory":
"TLS k {0}:{1} se nenavázalo: {2} – starý server (slabý klíč, TLS 1.0): u tohoto adresáře zapněte „Přijímat staré, slabé certifikáty“",
}
R140 = {}
