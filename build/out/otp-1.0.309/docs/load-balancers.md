# Load balancers in front of a cluster

Two otp nodes both answer everything - the pages, the administration and
RADIUS - so any load balancer can spread the traffic over both, round robin,
**without sticky sessions** (a sign-in and everything half done is in the
database). Instead of a load balancer of your own, the pages can also use the
built-in VIP address (VIP, active/standby): [tls-and-vip.md](tls-and-vip.md).
Use one or the other for the pages; with the VIP address off, a load
balancer works exactly as described here.

*Settings → High availability → The load balancer* writes every configuration
below filled in with the cluster's own names, addresses and ports, for the
layer chosen (1.0.259).

In the examples: the nodes `otp1` 192.0.2.11 and `otp2` 192.0.2.12, the
balancer's virtual address 192.0.2.5, the address it comes to the nodes from
192.0.2.6, the name `otp.example.cz`, the nodes' port for the balancer 8443.

## What goes through the balancer: the enrolment pages, nothing else

Through a balancer (usually published to the internet) only the enrolment
pages pass - and RADIUS where the balancer carries it. **Never the
administration (`/admin/`), `/metrics`, `/healthz` or anything else.** The
enrolment pages need exactly these paths (with any query string - their API
is `/?api=...`):

```
/   /index.php   /favicon.ico   /apple-touch-icon*.png
/assets/core.js  /assets/portal.js  /assets/i18n.js  /assets/otp.css
/assets/favicon.svg  /assets/apple-touch-icon.png
```

as one regular expression, used by every configuration below:

```
^/((index\.php|favicon\.ico)|assets/(core\.js|portal\.js|i18n\.js|otp\.css|favicon\.svg|apple-touch-icon\.png)|apple-touch-icon(-precomposed)?(-[0-9]+x[0-9]+)?\.png)?$
```

An exact list, never a prefix to refuse: `//admin/` and `/assets/../admin/`
are the administration once the node's nginx has tidied the path. `/healthz`
is the balancer's own question, asked of the nodes directly. The balancer
also takes away what a client could send to fool the nodes - its own
`X-Forwarded-For` (the balancer **puts** the client's address in, never adds
to what came), `X-Otp-Sso-Key`, `X-Otp-Restore` - limits TLS to 1.2 and 1.3,
sends HSTS, and keeps the portal's own limits: 8 MB a request, 130 s.

---

## The health check: what it really looks at

Every node answers `GET /healthz` over HTTPS (and HTTP). It is public, short,
never cached, and checks the whole path a real request takes:

| URL | 200 means | 503 when |
|---|---|---|
| `/healthz` | nginx → PHP-FPM → the otp daemon → the database all answer; the node is not in maintenance | anything on that path is down; the database does not open; the node is in maintenance or being upgraded |
| `/healthz?check=radius` | the same, **and RADIUS is listening** | the above, or the RADIUS server is not bound |
| `/healthz?check=all` | the same, and replication runs both ways | the above, or `degraded: replication not running / lost` - for **monitoring** only, not for a balancer (a node cannot fix its peer's replication, and both would be taken out) |

The body says why, on one line: `ok otp1`, `maintenance otp1`,
`down: the daemon is not answering`, `down: the database does not open`,
`down: RADIUS is not listening on otp1`. Match on the status code, or on the
body starting with `ok `.

Recommended: check every 2-5 s, take a node out after 2-3 failures, back in
after 2 successes, timeout 3-5 s.

**Maintenance and upgrades take the node out by themselves**: from the
moment a node goes into maintenance its `/healthz` says 503, and an upgrade
(from the pages or `install.sh --upgrade`) waits 20 s after that before it
touches anything - set the balancer to notice within that time.

---

## The layer: L7 or L4

| | L7 - TLS ended on the balancer | L4 - TLS passed through, PROXY protocol | L4 - no client address |
|---|---|---|---|
| the certificate for `otp.example.cz` | on the balancer | on the nodes | on the nodes |
| the client's address | `X-Forwarded-For`, put in by the balancer | the PROXY protocol | none: everybody is the balancer |
| the paths filtered | **on the balancer** and on the nodes' own port | on the nodes' own port only | nowhere |
| otp on the nodes | `web_proxy_header=X-Forwarded-For` | `web_proxy_header=proxy_protocol` | `web_proxy=0` |

```bash
# L7 (as root on one node - the setting is the cluster's):
otp --set web_proxy_from='192.0.2.6/32' --set web_proxy_header=X-Forwarded-For --set web_proxy_recursive=1 --set web_proxy_port=8443 --set web_proxy=1
# L4 with the PROXY protocol:
otp --set web_proxy_from='192.0.2.6/32' --set web_proxy_header=proxy_protocol --set web_proxy_recursive=0 --set web_proxy_port=8443 --set web_proxy=1
```

`web_proxy_from` is the address the balancer **comes to the nodes from** -
HAProxy's or nginx's own address, the NetScaler's SNIP, the F5's self IPs -
not its virtual address. Keep it to the balancers alone (/32): with
`web_proxy_recursive` on, a client inside a network named there could name
any address it liked.

**At L4 the balancer cannot see the paths** (it is TLS). What keeps the
administration from the internet is then the nodes themselves: their own port
for the balancer serves the enrolment pages only (below), and *Settings →
Firewall and access → who may reach the administration pages* must be your
own networks only. With the PROXY protocol the nodes see the real client, so
those lists work as they should.

**L4 without the PROXY protocol** carries no address at all - not advised:
the administration list must not contain the balancer's address (everybody
through it would be let in), the sign-in pause and nginx's limit of 20
sign-ins a minute are everybody's together, and the logs say the balancer.

In every case the balancer's address must be among *who may ask the health
check* (`/healthz`), or the balancer takes both nodes out.

## The nodes' own port for the balancer (1.0.259)

*Settings → Firewall and access → Behind a load balancer or WAF → The
balancer's own port on the nodes* (`web_proxy_port`, 0 = none, as before):
each node's root helper writes `/etc/nginx/conf.d/otp_lbport.conf` - a server
of its own on that port with this node's certificate and TLS, the enrolment
page exactly as on 443 (who may reach it, the sign-in limits, the sign-in by
the balancer), the files it loads, and **404 for everything else**. It is
made again whenever otp.conf changes, checked with `nginx -t` and put back
when refused. Where otp looks after the firewall, the port is opened to the
addresses in `web_proxy_from` alone. 443 stays exactly as it is - for the
administrators, the VIP address, the other node and the health checks, which
ask 443 (no PROXY protocol there). With `web_proxy_header=proxy_protocol`
the port takes the PROXY protocol (v1 or v2) and believes it from the
balancers alone; 443 then believes no header at all. SELinux lets nginx use
8443; another port needs `semanage port -a -t http_port_t -p tcp PORT`.

---

## HAProxy

The `global`/`defaults` part, for every variant:

```
global
    ssl-default-bind-options ssl-min-ver TLSv1.2 no-tls-tickets
    ssl-default-bind-ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305
    ssl-default-bind-ciphersuites TLS_AES_128_GCM_SHA256:TLS_AES_256_GCM_SHA384:TLS_CHACHA20_POLY1305_SHA256

defaults
    log global
    timeout connect 5s
    timeout client 130s
    timeout server 130s
    timeout http-request 10s
```

### L7 - TLS ended on HAProxy

```
frontend otp_portal
    mode http
    option httplog
    bind 192.0.2.5:80
    bind 192.0.2.5:443 ssl crt /etc/haproxy/otp.example.cz.pem alpn h2,http/1.1
    acl otp_portal path_reg '^/((index\.php|favicon\.ico)|assets/(core\.js|portal\.js|i18n\.js|otp\.css|favicon\.svg|apple-touch-icon\.png)|apple-touch-icon(-precomposed)?(-[0-9]+x[0-9]+)?\.png)?$'
    http-request redirect scheme https code 301 unless { ssl_fc }
    http-request deny deny_status 405 if !METH_GET !METH_POST
    http-request deny deny_status 404 unless otp_portal
    http-request del-header X-Otp-Sso-Key
    http-request del-header X-Otp-Restore
    http-request set-header X-Forwarded-For %[src]
    http-request set-header X-Forwarded-Proto https
    http-after-response set-header Strict-Transport-Security "max-age=63072000"
    default_backend otp_nodes

backend otp_nodes
    mode http
    balance roundrobin
    option httpchk
    http-check send meth GET uri /healthz ver HTTP/1.1 hdr Host otp.example.cz
    http-check expect status 200
    default-server inter 3s fall 2 rise 2 check port 443 ssl verify none
    server otp1 192.0.2.11:8443
    server otp2 192.0.2.12:8443
```

(`verify required ca-file ...` instead of `verify none` when the nodes have
certificates from your CA.)

### L4 - TLS passed through, the PROXY protocol

```
frontend otp_tls
    mode tcp
    option tcplog
    bind 192.0.2.5:443
    tcp-request inspect-delay 5s
    tcp-request content accept if { req.ssl_hello_type 1 }
    default_backend otp_nodes_tls

backend otp_nodes_tls
    mode tcp
    balance roundrobin
    option httpchk
    http-check send meth GET uri /healthz ver HTTP/1.1 hdr Host otp.example.cz
    http-check expect status 200
    default-server inter 3s fall 2 rise 2 check port 443 check-ssl verify none send-proxy-v2
    server otp1 192.0.2.11:8443
    server otp2 192.0.2.12:8443

frontend otp_http
    mode http
    bind 192.0.2.5:80
    acl otp_acme path_beg /.well-known/acme-challenge/
    http-request redirect scheme https code 301 unless otp_acme
    default_backend otp_acme

backend otp_acme
    mode http
    balance roundrobin
    server otp1 192.0.2.11:80 check
    server otp2 192.0.2.12:80 check
```

The health check asks 443 without the PROXY protocol; the traffic goes to
8443 with it. Port 80 passes the ACME CA's question on (when the nodes take
their certificate for the name by HTTP-01) and sends everything else to
HTTPS. Without `send-proxy-v2` (and to port 443) it is L4 without a client
address.

### RADIUS through HAProxy

The open-source HAProxy does not balance UDP. Give the VPN both nodes
instead ([Cisco ASA](#cisco-asa-radius-without-a-balancer)), or use
keepalived/LVS, nginx `stream`, F5 or NetScaler below.

---

## nginx as the balancer

### L7

```nginx
upstream otp_nodes {
    server 192.0.2.11:8443 max_fails=2 fail_timeout=10s;
    server 192.0.2.12:8443 max_fails=2 fail_timeout=10s;
    keepalive 16;
}
server {
    listen 192.0.2.5:80;
    server_name otp.example.cz;
    return 301 https://$host$request_uri;
}
server {
    listen 192.0.2.5:443 ssl;
    http2 on;                 # nginx older than 1.25.1: listen 192.0.2.5:443 ssl http2;
    server_name otp.example.cz;
    server_tokens off;
    ssl_certificate     /etc/nginx/certs/otp.example.cz.pem;
    ssl_certificate_key /etc/nginx/certs/otp.example.cz.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305;
    ssl_session_tickets off;
    add_header Strict-Transport-Security "max-age=63072000" always;
    proxy_hide_header Strict-Transport-Security;
    client_max_body_size 8m;
    if ($request_method !~ ^(GET|HEAD|POST)$) { return 405; }
    proxy_http_version 1.1;
    proxy_set_header Connection "";
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $remote_addr;      # put in, not added to
    proxy_set_header X-Forwarded-Proto https;
    proxy_set_header X-Otp-Sso-Key "";
    proxy_set_header X-Otp-Restore "";
    proxy_read_timeout 130s;
    proxy_next_upstream error timeout http_502 http_503 http_504;
    location ~ ^/((index\.php|favicon\.ico)|assets/(core\.js|portal\.js|i18n\.js|otp\.css|favicon\.svg|apple-touch-icon\.png)|apple-touch-icon(-precomposed)?(-[0-9]+x[0-9]+)?\.png)?$ {
        proxy_pass https://otp_nodes;
    }
    location / { return 404; }
}
```

nginx matches its locations on the tidied path, so `//admin/` and
`/assets/../admin/` end in `location /` too.

- **Open-source nginx checks passively only**: a node is skipped after
  `max_fails` failed requests, and a 503 from a node in maintenance is
  retried on the other. **nginx Plus** asks `/healthz` itself:
  `health_check uri=/healthz interval=3 fails=2 passes=2 match=otp_ok;` with
  `match otp_ok { status 200; body ~ "^ok "; }`.

### L4

```nginx
stream {
    upstream otp_tls {
        server 192.0.2.11:8443 max_fails=2 fail_timeout=10s;
        server 192.0.2.12:8443 max_fails=2 fail_timeout=10s;
    }
    server {
        listen 192.0.2.5:443;
        proxy_pass otp_tls;
        proxy_protocol on;            # PROXY protocol v1 - otp's nginx takes v1 and v2
        proxy_connect_timeout 5s;
        proxy_timeout 130s;
    }
}
```

and a plain `server { listen 192.0.2.5:80; ... }` in `http { }` that passes
`/.well-known/acme-challenge/` to the nodes' port 80 and sends the rest to
HTTPS.

### RADIUS with nginx `stream`

```nginx
stream {
    upstream otp_radius     { hash $remote_addr consistent; server 192.0.2.11:1812 max_fails=2 fail_timeout=10s; server 192.0.2.12:1812 max_fails=2 fail_timeout=10s; }
    upstream otp_accounting { hash $remote_addr consistent; server 192.0.2.11:1813; server 192.0.2.12:1813; }
    server { listen 192.0.2.5:1812 udp; proxy_pass otp_radius;     proxy_responses 1; proxy_timeout 10s; }
    server { listen 192.0.2.5:1813 udp; proxy_pass otp_accounting; proxy_responses 1; proxy_timeout 10s; }
}
```

`hash` sends a concentrator's repeated request to the node that has it. The
nodes then see **this machine's own address** as the RADIUS client - add it
in otp (its address and the shared secret), or use
`proxy_bind $remote_addr transparent;` (needs routing set up for it). Giving
the VPN both nodes directly is simpler.

---

## Apache httpd (L7 only)

Apache balances HTTP only; for L4 use HAProxy, nginx, the F5 or the
NetScaler.

```apache
ProxyHCExpr otp_ok {%{REQUEST_STATUS} == 200 && hc('body') =~ /^ok /}

<VirtualHost 192.0.2.5:80>
    ServerName otp.example.cz
    Redirect permanent / https://otp.example.cz/
</VirtualHost>

<VirtualHost 192.0.2.5:443>
    ServerName otp.example.cz
    SSLEngine on
    SSLProtocol -all +TLSv1.2 +TLSv1.3
    SSLCipherSuite ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305
    SSLHonorCipherOrder off
    SSLSessionTickets off
    SSLCertificateFile    /etc/pki/tls/certs/otp.example.cz.crt
    SSLCertificateKeyFile /etc/pki/tls/private/otp.example.cz.key
    SSLProxyEngine on
    SSLProxyVerify none
    SSLProxyCheckPeerName off
    Header always set Strict-Transport-Security "max-age=63072000"
    RequestHeader unset X-Forwarded-For early
    RequestHeader unset X-Otp-Sso-Key early
    RequestHeader unset X-Otp-Restore early
    RequestHeader set X-Forwarded-Proto https
    <If "%{REQUEST_URI} !~ m#^/((index\.php|favicon\.ico)|assets/(core\.js|portal\.js|i18n\.js|otp\.css|favicon\.svg|apple-touch-icon\.png)|apple-touch-icon(-precomposed)?(-[0-9]+x[0-9]+)?\.png)?$#">
        Require all denied
    </If>
    LimitRequestBody 8388608
    ProxyTimeout 130

    <Proxy "balancer://otp">
        BalancerMember https://192.0.2.11:8443 hcmethod=GET hcuri=/healthz hcexpr=otp_ok hcinterval=3 hcpasses=2 hcfails=2
        BalancerMember https://192.0.2.12:8443 hcmethod=GET hcuri=/healthz hcexpr=otp_ok hcinterval=3 hcpasses=2 hcfails=2
        ProxySet lbmethod=byrequests
    </Proxy>
    ProxyPreserveHost On
    ProxyAddHeaders On
    ProxyPass        "/" "balancer://otp/"
    ProxyPassReverse "/" "balancer://otp/"
</VirtualHost>
```

The client's `X-Forwarded-For` is taken away first, so the one mod_proxy
adds holds the client's address alone.

---

## F5 BIG-IP

**Monitors** - asked on 443 whatever the pool member's port (`destination
*:443`; without it the RADIUS monitor asked TCP 1812, and a pool on 8443 the
PROXY port). F5's receive string is matched against the whole answer, its
headers first, so it is `ok `, not `^ok `:

```
create ltm monitor https otp_healthz defaults-from https destination *:443 interval 3 timeout 10 send "GET /healthz HTTP/1.1\r\nHost: otp.example.cz\r\nConnection: close\r\n\r\n" recv "ok " recv-disable "maintenance"
create ltm monitor https otp_radius_health defaults-from https destination *:443 interval 3 timeout 10 send "GET /healthz?check=radius HTTP/1.1\r\nHost: otp.example.cz\r\nConnection: close\r\n\r\n" recv "ok "
```

`recv-disable "maintenance"` lets a node in maintenance finish its
connections instead of cutting them.

**L7** - SSL offload with TLS 1.2 and 1.3 only, and an iRule that lets the
enrolment pages alone through and puts the client's address in:

```
create ltm pool otp_https monitor otp_healthz load-balancing-mode round-robin members add { 192.0.2.11:8443 192.0.2.12:8443 }
create ltm profile client-ssl otp_clientssl defaults-from clientssl cert-key-chain replace-all-with { otp { cert otp.example.cz.crt key otp.example.cz.key } } options { no-ssl no-tlsv1 no-tlsv1.1 }
create ltm rule otp_portal_only {
when HTTP_REQUEST {
    if { !([HTTP::method] eq "GET" || [HTTP::method] eq "HEAD" || [HTTP::method] eq "POST") } { HTTP::respond 405 noserver ; return }
    if { ![regexp {^/((index\.php|favicon\.ico)|assets/(core\.js|portal\.js|i18n\.js|otp\.css|favicon\.svg|apple-touch-icon\.png)|apple-touch-icon(-precomposed)?(-[0-9]+x[0-9]+)?\.png)?$} [HTTP::path]] } { HTTP::respond 404 noserver ; return }
    HTTP::header remove "X-Forwarded-For"
    HTTP::header remove "X-Otp-Sso-Key"
    HTTP::header remove "X-Otp-Restore"
    HTTP::header insert "X-Forwarded-For" [IP::client_addr]
    HTTP::header replace "X-Forwarded-Proto" "https"
}
when HTTP_RESPONSE { HTTP::header replace "Strict-Transport-Security" "max-age=63072000" }
}
create ltm virtual otp_vs destination 192.0.2.5:443 ip-protocol tcp pool otp_https profiles add { http otp_clientssl serverssl } rules { otp_portal_only } source-address-translation { type automap }
create ltm virtual otp_vs80 destination 192.0.2.5:80 ip-protocol tcp profiles add { tcp http } rules { _sys_https_redirect }
```

With automap the nodes see the self IPs: those are `web_proxy_from`.

**L4** - a standard TCP profile (not FastL4) and the PROXY protocol v1 from
an iRule:

```
create ltm rule otp_proxy {
when SERVER_CONNECTED {
    TCP::respond "PROXY TCP[IP::version] [IP::client_addr] [IP::local_addr clientside] [TCP::client_port] [TCP::local_port clientside]\r\n"
}
}
create ltm pool otp_tls monitor otp_healthz members add { 192.0.2.11:8443 192.0.2.12:8443 }
create ltm virtual otp_vs destination 192.0.2.5:443 ip-protocol tcp pool otp_tls profiles add { tcp } rules { otp_proxy } source-address-translation { type automap }
```

**RADIUS**: a UDP virtual server, members on both nodes, monitored with
`otp_radius_health` - it says whether RADIUS is listening, without a test
account:

```
create ltm pool otp_radius monitor otp_radius_health members add { 192.0.2.11:1812 192.0.2.12:1812 }
create ltm virtual otp_radius_vs destination 192.0.2.5:1812 ip-protocol udp pool otp_radius profiles add { udp } source-address-translation { type none }
```

Without address translation the nodes see the concentrators' addresses
(their route back must go through the F5); with automap add the self IPs as
RADIUS clients in otp.

---

## Citrix ADC / NetScaler

```
add lb monitor otp_healthz HTTP-ECV -send "GET /healthz" -customHeaders "Host: otp.example.cz\r\n" -recv "ok " -secure YES -destPort 443 -interval 3 -resptimeout 2 -downTime 5
add server otp1 192.0.2.11
add server otp2 192.0.2.12
```

**L7** - TLS 1.2 and 1.3, HSTS, the enrolment pages alone, the client's
address put in (`-cip` would add to what the client sent):

```
add serviceGroup otp_https SSL -cip DISABLED
bind serviceGroup otp_https otp1 8443
bind serviceGroup otp_https otp2 8443
bind serviceGroup otp_https -monitorName otp_healthz
add lb vserver otp_vs SSL 192.0.2.5 443 -lbMethod ROUNDROBIN -persistenceType NONE -cltTimeout 130
bind lb vserver otp_vs otp_https
bind ssl vserver otp_vs -certkeyName otp.example.cz
set ssl vserver otp_vs -ssl3 DISABLED -tls1 DISABLED -tls11 DISABLED -tls12 ENABLED -tls13 ENABLED -HSTS ENABLED -maxage 63072000
add responder action otp_404 respondwith "\"HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\nConnection: close\r\n\r\n\""
add responder policy otp_portal_only "!HTTP.REQ.URL.PATH.REGEX_MATCH(re#^/((index\.php|favicon\.ico)|assets/(core\.js|portal\.js|i18n\.js|otp\.css|favicon\.svg|apple-touch-icon\.png)|apple-touch-icon(-precomposed)?(-[0-9]+x[0-9]+)?\.png)?$#)" otp_404
bind lb vserver otp_vs -policyName otp_portal_only -priority 10 -gotoPriorityExpression END -type REQUEST
add rewrite action otp_drop_xff delete_http_header X-Forwarded-For
add rewrite action otp_drop_key delete_http_header X-Otp-Sso-Key
add rewrite action otp_drop_rst delete_http_header X-Otp-Restore
add rewrite action otp_put_xff insert_http_header X-Forwarded-For CLIENT.IP.SRC
add rewrite action otp_put_proto insert_http_header X-Forwarded-Proto "\"https\""
(a rewrite policy "true" for each, bound to otp_vs at 100-140 in that order, NEXT, END on the last)
```

**L4** - SSL_BRIDGE with the PROXY protocol v2 from a net profile:

```
add netProfile otp_pp -proxyProtocol ENABLED -proxyProtocolVersion V2
add serviceGroup otp_tls SSL_BRIDGE -netProfile otp_pp
bind serviceGroup otp_tls otp1 8443
bind serviceGroup otp_tls otp2 8443
bind serviceGroup otp_tls -monitorName otp_healthz
add lb vserver otp_vs SSL_BRIDGE 192.0.2.5 443 -lbMethod ROUNDROBIN -persistenceType NONE -cltTimeout 130
bind lb vserver otp_vs otp_tls
```

**RADIUS**:

```
add lb monitor otp_radius_health HTTP-ECV -send "GET /healthz?check=radius" -customHeaders "Host: otp.example.cz\r\n" -recv "ok " -secure YES -destPort 443 -interval 3
add serviceGroup otp_radius RADIUS -usip YES
bind serviceGroup otp_radius otp1 1812
bind serviceGroup otp_radius otp2 1812
bind serviceGroup otp_radius -monitorName otp_radius_health
add lb vserver otp_radius_vs RADIUS 192.0.2.5 1812 -lbMethod ROUNDROBIN
bind lb vserver otp_radius_vs otp_radius
```

`-usip YES` keeps the concentrators' addresses (otherwise add the SNIP as a
RADIUS client in otp). The nodes see the SNIP for the pages: that is
`web_proxy_from`.

---

## keepalived + LVS (IPVS) - balancing RADIUS on Linux

A pair of Linux machines (not the otp nodes) can balance UDP RADIUS with the
kernel's IPVS, checked by asking each node's `/healthz?check=radius`:

```
virtual_server 192.0.2.5 1812 {
    delay_loop 3
    lb_algo rr
    lb_kind NAT
    protocol UDP
    real_server 192.0.2.11 1812 {
        HTTP_GET {
            url { path /healthz?check=radius status_code 200 }
            connect_port 443
            connect_timeout 3
            retry 2
        }
    }
    real_server 192.0.2.12 1812 { HTTP_GET { url { path /healthz?check=radius status_code 200 } connect_port 443 connect_timeout 3 retry 2 } }
}
```

(Use `SSL_GET` instead of `HTTP_GET` for HTTPS; the same for 1813.) With
`lb_kind NAT` the nodes see the concentrators' addresses; their default
route must go back through the balancer.

---

## Cisco ASA: RADIUS without a balancer

The simplest for RADIUS is no balancer at all: both nodes in one server
group. The ASA asks the first; when it does not answer, the next.

```
aaa-server OTP protocol radius
 max-failed-attempts 2
 reactivation-mode depletion deadtime 1
aaa-server OTP (inside) host 192.0.2.11
 key <the shared secret>
 authentication-port 1812
 accounting-port 1813
 timeout 5
aaa-server OTP (inside) host 192.0.2.12
 key <the shared secret>
 authentication-port 1812
 accounting-port 1813
 timeout 5
```

A node in maintenance does not answer RADIUS at all, so the ASA goes to the
other one after `timeout`. Add the ASA once as a client in otp - both nodes
use it. Other VPNs (FortiGate, Palo Alto, strongSwan, Windows NPS as a
proxy) have the same: two RADIUS servers, the second used when the first
does not answer.

---

## After setting one up

```bash
for n in 192.0.2.11 192.0.2.12; do curl -sk https://$n/healthz; done   # ok otp1 / ok otp2
curl -sk -o /dev/null -w '%{http_code}\n' https://otp.example.cz/          # 200 - the enrolment pages
curl -sk -o /dev/null -w '%{http_code}\n' https://otp.example.cz/admin/    # 404 - not published
curl -sk -o /dev/null -w '%{http_code}\n' https://otp.example.cz//admin/   # 404
curl -sk -o /dev/null -w '%{http_code}\n' https://otp.example.cz/metrics   # 404
curl -sk -o /dev/null -w '%{http_code}\n' https://otp.example.cz/healthz   # 404
otp --maintenance on --why "balancer test"        # on otp1: the balancer must take it out
curl -sk https://192.0.2.11/healthz                # 503 maintenance otp1
otp --maintenance off
```

Sign in through the balancer and look at *Settings → Accounts → signed in*:
the address shown must be your own, not the balancer's.

## The client's address behind a balancer or WAF (1.0.237)

*Settings → Firewall and access → Behind a load balancer or WAF*: switched on, nginx takes the
client's own address from the header the balancer sends (`X-Forwarded-For` unless another is
named - `X-Real-IP`, `True-Client-IP`, `CF-Connecting-IP`...) - **only** for requests that come
from the addresses or networks named; anybody else's header is never believed. Then the sign-in
pause, the caps of wrong passwords, who may reach which page, nginx's limits and every log see
the client. It goes into this node's HTTPS server and the VIP address's alike, on every node,
put in by each node's root helper (checked with `nginx -t`, put back when refused), and into the
balancer's own port when one is set (1.0.259). *Through more than one of them* (on): in a chain -
a WAF before a balancer - the last address that is not one of them is taken. RADIUS is not
concerned. A header other than `X-Forwarded-For` must be **put in** by the balancer: nginx takes
the first of such headers, which would be the client's own if the balancer added one.

`proxy_protocol` as the header (1.0.259) is taken only with *The balancer's own port on the
nodes*, and believed there alone: 443 then believes no header.

Off (the default) nginx is left as it was - what `otp --trusted-proxy` once wrote stays. Switched
on, the setting takes its place; switched off again, only its own lines go. While it is set on
the pages, `otp --trusted-proxy` refuses and says to change it there.


## Signed in by the balancer (1.0.239)

A NetScaler or an F5 APM that signs people in against the directory before the enrolment pages
can hand who it signed in to otp, so that the pages ask no password again - only from the
balancers named, only with a key of otp's own, the one-time code before the first token still
asked. *Settings → The enrolment pages → Signed in by a load balancer or WAF*; the whole of it in
docs/portal-sso.md.
