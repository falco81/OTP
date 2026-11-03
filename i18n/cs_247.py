# 1.0.237: SELinux - a refusal otp does not know yet; behind a proxy (X-Forwarded-For).
S247 = {
 "otp does not know this one yet": "Tohle otp zatím nezná",
 "Everything otp knows it needs is in place - what was refused is something its module does not cover yet. \"Put in what otp needs\" changes nothing for it: download the report (top right) and send it, so that the module learns it.":
  "Vše, o čem otp ví, že potřebuje, je na místě – odepřeno bylo něco, co jeho modul zatím nepokrývá. „Doplnit, co otp potřebuje“ s tím nic neudělá: stáhněte report (vpravo nahoře) a pošlete ho, ať se to modul naučí.",
}
S247.update({
 "Behind a load balancer or WAF": "Za load balancerem nebo WAF",
 "The load balancers and WAFs": "Load balancery a WAF",
 "The header with the client's address": "Hlavička s adresou klienta",
 "Through more than one of them": "Přes více z nich",
 "The pages published through a load balancer or a WAF (NetScaler, F5, HAProxy...): nginx takes the client's own address from the header below - only when the request comes from one of the addresses below, never from anybody else - so that the sign-in pause, the caps, who may reach which page and every log see the client and not the balancer. For this node's address and the VIP address's alike, on every node. RADIUS is not concerned. Off: nginx as until now (what otp --trusted-proxy put in stays as it is).":
  "Stránky publikované přes load balancer nebo WAF (NetScaler, F5, HAProxy…): nginx vezme skutečnou adresu klienta z hlavičky níže – jen když požadavek přijde z některé z adres níže, nikdy od nikoho jiného – aby pauza přihlášení, stropy, kdo smí na kterou stránku, i všechny logy viděly klienta, a ne balancer. Pro adresu tohoto uzlu i pro VIP, na každém uzlu. RADIUSu se to netýká. Vypnuto: nginx jako dosud (co zapsal otp --trusted-proxy, zůstane, jak je).",
 "Their addresses or networks, as nginx sees them come in - one or more, separated by spaces. Needed to switch it on: the header of anybody else is never believed.":
  "Jejich adresy nebo sítě, jak je nginx vidí přicházet – jedna nebo víc, oddělené mezerou. Bez nich to zapnout nejde: hlavičce od kohokoli jiného se nikdy nevěří.",
 "Where the balancer puts the client's address: X-Forwarded-For (the usual), X-Real-IP, True-Client-IP, X-Client-IP, CF-Connecting-IP...":
  "Kam balancer dává adresu klienta: X-Forwarded-For (obvyklé), X-Real-IP, True-Client-IP, X-Client-IP, CF-Connecting-IP…",
 "On: in a chain (a WAF in front of a balancer), the last address in the header that is not one of them is taken. Off: the last one, whoever put it there.":
  "Zapnuto: v řetězu (WAF před balancerem) se vezme poslední adresa v hlavičce, která není jedním z nich. Vypnuto: poslední adresa, ať ji tam dal kdokoli.",
 "behind a load balancer or WAF: say which addresses are the balancers first (The load balancers and WAFs)":
  "za load balancerem nebo WAF: nejdřív uveďte, které adresy jsou balancery (Load balancery a WAF)",
})
P247 = {}
