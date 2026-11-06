# 1.0.259: the load balancer - the layer (L7, L4 with the PROXY protocol, L4 without an address),
# the nodes' own port for the balancer (web_proxy_port), the enrolment pages alone through it;
# the administration's second step by mail or SMS - the first code by itself, the countdown.
S267 = {
 # ---- High availability → The load balancer
 'Both nodes answer everything, so any balancer spreads the pages round robin, without sticky sessions. Each node says GET /healthz: 200 "ok NODE" while it really works (the daemon, its database), 503 in maintenance or an upgrade - so the balancer takes it out by itself. Through the balancer only the enrolment pages are published - never the administration, /metrics or /healthz. Pick yours below: the configuration is filled in with this cluster\'s own names, addresses and ports, marked in colour, and follows what you type here.':
  'Oba uzly odpovídají na všechno, takže jakýkoli balancer rozkládá stránky dokola (round robin), bez lepivých relací. Každý uzel na GET /healthz říká 200 „ok UZEL“, dokud opravdu funguje (démon, jeho databáze), a 503 při údržbě nebo upgradu – balancer ho tak vyřadí sám. Přes balancer se zveřejňují jen stránky registrace – nikdy administrace, /metrics ani /healthz. Vyberte svůj níže: konfigurace je vyplněná vlastními jmény, adresami a porty tohoto clusteru, barevně vyznačená, a řídí se tím, co sem napíšete.',
 'The address it comes to the nodes from': 'Adresa, ze které přichází k uzlům',
 'what the nodes see: its own address, the SNIP, the self IP': 'co vidí uzly: jeho vlastní adresu, SNIP, self IP',
 "The nodes' port for the balancer": 'Port uzlů pro balancer',
 'the enrolment pages only (web_proxy_port)': 'jen stránky registrace (web_proxy_port)',
 'Layer': 'Vrstva',
 'L7 - TLS ended on the balancer': 'L7 – TLS končí na balanceru',
 'L4 - TLS passed through, PROXY protocol': 'L4 – TLS projde, protokol PROXY',
 'L4 - no client address (not advised)': 'L4 – bez adresy klienta (nedoporučeno)',
 'Settings → Firewall and access': 'Nastavení → Firewall a přístup',
 "The balancer puts the client's address in, never adds to what the client sent; only the enrolment pages pass (an exact list of paths), everything else ends on the balancer with 404.":
  'Balancer adresu klienta vkládá, nikdy nepřidává k tomu, co poslal klient; projdou jen stránky registrace (přesný seznam cest), všechno ostatní skončí na balanceru s 404.',
 'The administration pages are for everybody now: through the balancer they are refused, but straight to the nodes they are not.':
  'Stránky administrace jsou teď pro každého: přes balancer se odmítnou, ale přímo na uzlech ne.',
 'The administration pages are for everybody now: through the balancer that is the internet.':
  'Stránky administrace jsou teď pro každého: přes balancer je to celý internet.',
 '/etc/haproxy/haproxy.cfg - TLS ended on HAProxy, the enrolment pages only':
  '/etc/haproxy/haproxy.cfg – TLS končí na HAProxy, jen stránky registrace',
 "/etc/haproxy/haproxy.cfg - TLS passed through to the nodes, the client's address in the PROXY protocol":
  '/etc/haproxy/haproxy.cfg – TLS projde až na uzly, adresa klienta v protokolu PROXY',
 '/etc/haproxy/haproxy.cfg - TLS passed through to the nodes, no client address':
  '/etc/haproxy/haproxy.cfg – TLS projde až na uzly, bez adresy klienta',
 '/etc/nginx/conf.d/otp-lb.conf - TLS ended on nginx, the enrolment pages only (open-source nginx checks passively)':
  '/etc/nginx/conf.d/otp-lb.conf – TLS končí na nginx, jen stránky registrace (open-source nginx kontroluje pasivně)',
 '/etc/nginx/nginx.conf - RADIUS (stream, outside http { })': '/etc/nginx/nginx.conf – RADIUS (stream, mimo http { })',
 "/etc/nginx/nginx.conf - TLS passed through (stream, outside http { }), the client's address in the PROXY protocol (v1)":
  '/etc/nginx/nginx.conf – TLS projde (stream, mimo http { }), adresa klienta v protokolu PROXY (v1)',
 '/etc/nginx/nginx.conf - TLS passed through (stream, outside http { }), no client address':
  '/etc/nginx/nginx.conf – TLS projde (stream, mimo http { }), bez adresy klienta',
 "/etc/nginx/conf.d/otp-lb.conf - port 80: HTTPS, and the ACME CA's question only":
  '/etc/nginx/conf.d/otp-lb.conf – port 80: HTTPS a jen dotaz certifikační autority ACME',
 '/etc/httpd/conf.d/otp-lb.conf - mod_proxy_balancer with mod_proxy_hcheck asking /healthz, the enrolment pages only':
  '/etc/httpd/conf.d/otp-lb.conf – mod_proxy_balancer s mod_proxy_hcheck, který se ptá /healthz, jen stránky registrace',
 "tmsh - the monitors (asked on 443 whatever the pool's port), the pool, TLS 1.2 and 1.3, an iRule that lets the enrolment pages alone through":
  'tmsh – monitory (ptají se na 443, ať je port poolu jakýkoli), pool, TLS 1.2 a 1.3, iRule, který propustí jen stránky registrace',
 "The nodes see the self IPs with automap: those are the balancer's addresses for the nodes (floating and each unit's). With route domains, take %N off IP::client_addr. RADIUS without address translation keeps the concentrators' addresses (their route back must go through the F5).":
  'S automap vidí uzly self IP: to jsou adresy balanceru pro uzly (plovoucí i každé jednotky). Se směrovacími doménami odstraňte z IP::client_addr %N. RADIUS bez překladu adres zachová adresy koncentrátorů (jejich cesta zpět musí vést přes F5).',
 "tmsh - TLS passed through, the client's address in the PROXY protocol (v1, an iRule)":
  'tmsh – TLS projde, adresa klienta v protokolu PROXY (v1, iRule)',
 'tmsh - TLS passed through, no client address': 'tmsh – TLS projde, bez adresy klienta',
 'A standard TCP profile, not FastL4: the iRule needs it. The monitor asks 443 without the PROXY protocol.':
  'Standardní profil TCP, ne FastL4: iRule ho potřebuje. Monitor se ptá na 443 bez protokolu PROXY.',
 "NetScaler CLI - TLS ended on the ADC, the enrolment pages only, the client's address put in (never added to)":
  'NetScaler CLI – TLS končí na ADC, jen stránky registrace, adresa klienta vložená (nikdy přidaná)',
 "The nodes see the ADC's SNIP: that is the balancer's address for the nodes.":
  'Uzly vidí SNIP ADC: to je adresa balanceru pro uzly.',
 "NetScaler CLI - TLS passed through (SSL_BRIDGE), the client's address in the PROXY protocol v2":
  'NetScaler CLI – TLS projde (SSL_BRIDGE), adresa klienta v protokolu PROXY v2',
 'NetScaler CLI - TLS passed through (SSL_BRIDGE), no client address':
  'NetScaler CLI – TLS projde (SSL_BRIDGE), bez adresy klienta',
 'The monitor asks 443 without the PROXY protocol; the nodes see the SNIP.':
  'Monitor se ptá na 443 bez protokolu PROXY; uzly vidí SNIP.',
 'From any machine: each node, then through the balancer - the enrolment pages answer, nothing else; maintenance must take a node out':
  'Z libovolného stroje: každý uzel, pak přes balancer – odpovídají stránky registrace, nic jiného; údržba musí uzel vyřadit',
 'RADIUS: the open-source HAProxy does not balance UDP - give the VPN both nodes (Cisco ASA, FortiGate below) or use LVS.':
  'RADIUS: open-source HAProxy nevyvažuje UDP – dejte VPN oba uzly (Cisco ASA, FortiGate níže) nebo použijte LVS.',
 'Check it': 'Vyzkoušejte to',
 # ---- the sign-in by the balancer (its guides)
 '4. The enrolment pages alone through here - an exact list of paths, so neither /admin nor //admin, /metrics or /healthz':
  '4. Tudy jen stránky registrace – přesný seznam cest, takže ani /admin, ani //admin, /metrics nebo /healthz',
 '2. The iRule - the enrolment pages alone (an exact list of paths), what the client sent taken away, then who signed in and the key':
  '2. iRule – jen stránky registrace (přesný seznam cest), odstraněno, co poslal klient, pak kdo se přihlásil a klíč',
 # ---- the settings
 "The balancer's own port on the nodes": 'Vlastní port balanceru na uzlech',
 'A port of each node for the balancer alone (8443, say): it serves the enrolment pages and nothing else - not the administration, /metrics or /healthz - whatever the balancer passes on, and only to the addresses above (the firewall opens it to them alone, where otp looks after it). The header above is believed on it; proxy_protocol as the header: the balancer passes TLS through and says who the client is in the PROXY protocol (L4), on this port only. 443 stays as it is, for everybody else. SELinux lets nginx use 8443; another port needs semanage port -a -t http_port_t -p tcp PORT. 0: none, as before.':
  'Port každého uzlu jen pro balancer (třeba 8443): obsluhuje stránky registrace a nic jiného – ne administraci, /metrics ani /healthz – ať balancer předá cokoli, a jen adresám výše (firewall ho otevře jen jim, pokud ho otp spravuje). Věří se na něm hlavičce výše; proxy_protocol jako hlavička: balancer nechá TLS projít a kdo je klient, řekne v protokolu PROXY (L4), jen na tomto portu. 443 zůstává, jak je, pro všechny ostatní. SELinux dovolí nginx port 8443; jiný port potřebuje semanage port -a -t http_port_t -p tcp PORT. 0: žádný, jako dosud.',
 'web_proxy_header: the name of a header, as X-Forwarded-For or X-Real-IP, or proxy_protocol':
  'web_proxy_header: název hlavičky, třeba X-Forwarded-For nebo X-Real-IP, nebo proxy_protocol',
 "web_proxy_port: 0, or a free TCP port from 1024 up (not the API's own, not the SSH gate's) - 8443, say":
  'web_proxy_port: 0, nebo volný port TCP od 1024 výš (ne port API, ne port brány SSH) – třeba 8443',
 "the PROXY protocol (proxy_protocol as the header) only on the balancer's own port: give it first (The balancer's own port on the nodes, 8443 say)":
  'protokol PROXY (proxy_protocol jako hlavička) jen na vlastním portu balanceru: nejdřív ho zadejte (Vlastní port balanceru na uzlech, třeba 8443)',
 "nginx: the balancer's own port taken away": 'nginx: vlastní port balanceru odebrán',
 "the balancer's own port": 'vlastní port balanceru',
 # ---- the administration's second step by mail or SMS
 'Sign in again': 'Přihlásit se znovu',
 'Only the last one sent is good.': 'Platí jen ten poslední poslaný.',
 '1 more can be sent for this sign-in.': 'Pro toto přihlášení lze poslat ještě 1.',
}
P267 = {
 "The nodes take the client's own address from {0} sent by {1}, on their port {2} that serves the enrolment pages only.":
  'Uzly berou vlastní adresu klienta z {0}, kterou posílá {1}, na svém portu {2}, který obsluhuje jen stránky registrace.',
 "Tell the nodes the balancer: the client's own address from {0} when it comes from {1}, and their port {2} for it, with the enrolment pages only - Settings → Firewall and access → Behind a load balancer or WAF, or as root on one node:":
  'Řekněte uzlům, kdo je balancer: vlastní adresa klienta z {0}, když přichází od {1}, a jejich port {2} pro něj, jen se stránkami registrace – Nastavení → Firewall a přístup → Za load balancerem nebo WAF, nebo jako root na jednom uzlu:',
 "The nodes take the client's own address from the PROXY protocol sent by {0}, on their port {1} that serves the enrolment pages only.":
  'Uzly berou vlastní adresu klienta z protokolu PROXY, který posílá {0}, na svém portu {1}, který obsluhuje jen stránky registrace.',
 'Tell the nodes the balancer: the PROXY protocol from {0} on their port {1}, with the enrolment pages only - Settings → Firewall and access → Behind a load balancer or WAF, or as root on one node:':
  'Řekněte uzlům, kdo je balancer: protokol PROXY od {0} na jejich portu {1}, jen se stránkami registrace – Nastavení → Firewall a přístup → Za load balancerem nebo WAF, nebo jako root na jednom uzlu:',
 'Passed through, the balancer cannot see the paths: what keeps the administration from the internet is the nodes themselves - their port {0} serves the enrolment pages only, and Settings → Firewall and access → who may reach the administration pages must be your own networks only.':
  'Když TLS projde, balancer cesty nevidí: administraci před internetem chrání samy uzly – jejich port {0} obsluhuje jen stránky registrace a v Nastavení → Firewall a přístup → kdo smí na stránky administrace musí být jen vaše vlastní sítě.',
 "No client address: every client is {0} to the nodes. The administration must not be reachable from {1}, the sign-in pause and the limit of sign-ins a minute are everybody's together, and the logs say the balancer. The PROXY protocol (the layer beside) is better.":
  'Bez adresy klienta: pro uzly je každý klient {0}. Administrace nesmí být dosažitelná z {1}, pauza po přihlášení i limit přihlášení za minutu jsou společné pro všechny a v záznamech je balancer. Lepší je protokol PROXY (vrstva vedle).',
 'Who may reach the administration pages takes {0} - the balancer: everybody through it is let in.':
  'Kdo smí na stránky administrace, zahrnuje {0} – balancer: pustí se každý, kdo přijde přes něj.',
 'Who may reach the administration pages takes {0} - the balancer: take it out of the list.':
  'Kdo smí na stránky administrace, zahrnuje {0} – balancer: odeberte ho ze seznamu.',
 'The administration pages: {0} only.': 'Stránky administrace: jen {0}.',
 'Who may ask /healthz does not take {0}: the balancer would take both nodes out.':
  'Kdo se smí ptát /healthz, nezahrnuje {0}: balancer by vyřadil oba uzly.',
 'Who may reach the enrolment pages does not take {0}.': 'Kdo smí na stránky registrace, nezahrnuje {0}.',
 "otp does not look after this machine's firewall: open TCP {0} from {1} on both nodes yourself (it opens it from the balancers alone where it does).":
  'otp nespravuje firewall tohoto stroje: otevřete TCP {0} od {1} na obou uzlech sami (kde ho spravuje, otevře ho jen balancerům).',
 '{0} balances HTTP only: pick L7 above, or HAProxy, nginx, the F5 or the NetScaler for L4.':
  '{0} vyvažuje jen HTTP: zvolte výše L7, nebo pro L4 HAProxy, nginx, F5 či NetScaler.',
 "Pick yours: the configuration is filled in with what is set here, marked in colour, and follows what you type below. Whatever the balancer: it takes the client's own {0} and X-Otp-Sso-Key away first, puts in its own only after it signed the person in, and passes on the enrolment pages alone - an exact list of paths, never the administration, /metrics or /healthz.":
  'Vyberte svůj: konfigurace je vyplněná tím, co je tu nastaveno, barevně vyznačená, a řídí se tím, co napíšete níže. Ať je balancer jakýkoli: nejdřív odstraní {0} a X-Otp-Sso-Key, které poslal klient, vlastní vloží až poté, co člověka přihlásil, a dál pustí jen stránky registrace – přesný seznam cest, nikdy administraci, /metrics ani /healthz.',
 "nginx: the balancer's own port {0} - the enrolment pages only, for {1}":
  'nginx: vlastní port balanceru {0} – jen stránky registrace, pro {1}',
 "nginx: the balancer's own port {0} - the enrolment pages only, for {1} (the PROXY protocol)":
  'nginx: vlastní port balanceru {0} – jen stránky registrace, pro {1} (protokol PROXY)',
 # ---- the second step by mail or SMS
 'Send another ({0})': 'Poslat další ({0})',
 '{0} more can be sent for this sign-in.': 'Pro toto přihlášení lze poslat ještě {0}.',
 'That was the last code for this sign-in ({0}) - sign in again for more.':
  'To byl poslední kód pro toto přihlášení ({0}) – pro další se přihlaste znovu.',
 'It is good for {0} more.': 'Platí ještě {0}.',
 'a code went a moment ago - another in {0} s': 'kód odešel před chvílí – další za {0} s',
}
