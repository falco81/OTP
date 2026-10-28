# Load balancers in front of a cluster

Two otp nodes both answer everything - the pages, the administration and
RADIUS - so any load balancer can spread the traffic over both, round robin,
**without sticky sessions** (a sign-in and everything half done is in the
database). Instead of a load balancer of your own, the pages can also use the
built-in web address (VIP, active/standby): [tls-and-vip.md](tls-and-vip.md).
Use one or the other for the pages; with the web address off, a load
balancer works exactly as described here.

In the examples: the nodes `otp1` 192.0.2.11 and `otp2` 192.0.2.12, the
balancer 192.0.2.5, the name `otp.example.cz`.

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

## The client's own address

Every sign-in limit, allow list and log in otp is per client address. Behind
a balancer that hides it, everybody shares the balancer's address - five
wrong passwords from anybody would then lock out everybody. Either:

- **end TLS on the balancer** and send `X-Forwarded-For`, and tell both nodes
  the balancer's address (they trust the header only from there):

  ```bash
  otp --trusted-proxy 192.0.2.5/32        # on each node; again for each balancer address
  ```

- or **pass TLS through** with the **PROXY protocol**, and on both nodes in
  `/etc/nginx/conf.d/otp.conf`: `listen 443 ssl proxy_protocol;` (in place of
  `listen 443 ssl;`), `set_real_ip_from 192.0.2.5;`,
  `real_ip_header proxy_protocol;`, then `nginx -t && systemctl reload nginx`.

Plain TCP passthrough without the PROXY protocol carries no address at all -
do not use it.

---

## HAProxy

### Ending TLS on HAProxy (recommended)

```
frontend otp_https
    bind :443 ssl crt /etc/haproxy/otp.example.cz.pem alpn h2,http/1.1
    bind :80
    mode http
    http-request redirect scheme https unless { ssl_fc }
    option forwardfor
    default_backend otp_nodes

backend otp_nodes
    mode http
    balance roundrobin
    option httpchk
    http-check send meth GET uri /healthz ver HTTP/1.1 hdr Host otp.example.cz
    http-check expect status 200
    default-server inter 3s fall 2 rise 2 check ssl verify none
    server otp1 192.0.2.11:443
    server otp2 192.0.2.12:443
```

(`verify required ca-file ...` instead of `verify none` when the nodes have
certificates from your CA.) On both nodes: `otp --trusted-proxy 192.0.2.5/32`.

### Passing TLS through (PROXY protocol)

```
frontend otp_https
    bind :443
    mode tcp
    default_backend otp_nodes

backend otp_nodes
    mode tcp
    balance roundrobin
    option httpchk
    http-check send meth GET uri /healthz ver HTTP/1.1 hdr Host otp.example.cz
    http-check expect status 200
    default-server inter 3s fall 2 rise 2 check check-ssl verify none check-send-proxy send-proxy-v2
    server otp1 192.0.2.11:443
    server otp2 192.0.2.12:443
```

and the PROXY-protocol lines in nginx on both nodes (above). The health
check must send the PROXY header too (`check-send-proxy`), or nginx refuses it.

### RADIUS through HAProxy

The open-source HAProxy does not balance UDP. Give the VPN both nodes
instead ([Cisco ASA](#cisco-asa--radius-without-a-balancer)), or use
keepalived/LVS, nginx `stream`, F5 or NetScaler below.

---

## nginx as the balancer

```nginx
upstream otp_nodes {
    server 192.0.2.11:443 max_fails=2 fail_timeout=10s;
    server 192.0.2.12:443 max_fails=2 fail_timeout=10s;
    keepalive 16;
}
server {
    listen 443 ssl;
    http2 on;
    server_name otp.example.cz;
    ssl_certificate     /etc/nginx/certs/otp.example.cz.pem;
    ssl_certificate_key /etc/nginx/certs/otp.example.cz.key;
    client_max_body_size 4g;              # a database copy put back from the pages
    location / {
        proxy_pass https://otp_nodes;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_read_timeout 900s;
        proxy_next_upstream error timeout http_502 http_503 http_504;
        proxy_ssl_server_name on;
    }
}
```

- **Open-source nginx checks passively only**: a node is skipped after
  `max_fails` failed requests, and a 503 from a node in maintenance is
  retried on the other (`proxy_next_upstream ... http_503`). It does not ask
  `/healthz` by itself.
- **nginx Plus** checks actively:

  ```nginx
  match otp_ok { status 200; body ~ "^ok "; }
  location / { proxy_pass https://otp_nodes; health_check uri=/healthz interval=3 fails=2 passes=2 match=otp_ok; ... }
  ```

- RADIUS with nginx `stream` (UDP, passive checks only in open source):

  ```nginx
  stream {
      upstream otp_radius      { server 192.0.2.11:1812 max_fails=2 fail_timeout=10s; server 192.0.2.12:1812 max_fails=2 fail_timeout=10s; }
      upstream otp_accounting  { server 192.0.2.11:1813; server 192.0.2.12:1813; }
      server { listen 1812 udp; proxy_pass otp_radius;     proxy_responses 1; proxy_timeout 10s; }
      server { listen 1813 udp; proxy_pass otp_accounting; proxy_responses 1; proxy_timeout 10s; }
  }
  ```

  The nodes then see the balancer's address as the RADIUS client: add the
  balancer as the client in otp (its address and the shared secret), or use
  `proxy_bind $remote_addr transparent;` (needs routing set up for it).
  Giving the VPN both nodes directly is simpler.

On both nodes: `otp --trusted-proxy 192.0.2.5/32`.

---

## Apache httpd (mod_proxy_balancer + mod_proxy_hcheck)

```apache
LoadModule proxy_module          modules/mod_proxy.so
LoadModule proxy_http_module     modules/mod_proxy_http.so
LoadModule proxy_balancer_module modules/mod_proxy_balancer.so
LoadModule lbmethod_byrequests_module modules/mod_lbmethod_byrequests.so
LoadModule proxy_hcheck_module   modules/mod_proxy_hcheck.so
LoadModule watchdog_module       modules/mod_watchdog.so

ProxyHCExpr otp_ok {%{REQUEST_STATUS} == 200 && hc('body') =~ /^ok /}

<VirtualHost *:443>
    ServerName otp.example.cz
    SSLEngine on
    SSLCertificateFile    /etc/pki/tls/certs/otp.example.cz.crt
    SSLCertificateKeyFile /etc/pki/tls/private/otp.example.cz.key
    SSLProxyEngine on
    SSLProxyVerify none
    SSLProxyCheckPeerName off

    <Proxy "balancer://otp">
        BalancerMember https://192.0.2.11 hcmethod=GET hcuri=/healthz hcexpr=otp_ok hcinterval=3 hcpasses=2 hcfails=2
        BalancerMember https://192.0.2.12 hcmethod=GET hcuri=/healthz hcexpr=otp_ok hcinterval=3 hcpasses=2 hcfails=2
        ProxySet lbmethod=byrequests
    </Proxy>
    ProxyPreserveHost On
    ProxyPass        "/" "balancer://otp/" timeout=900
    ProxyPassReverse "/" "balancer://otp/"
    LimitRequestBody 0
</VirtualHost>
```

Apache sends `X-Forwarded-For` by itself. On both nodes:
`otp --trusted-proxy <Apache's address>/32`.

---

## F5 BIG-IP

**Monitor** (Local Traffic → Monitors → HTTPS):

```
ltm monitor https otp_healthz {
    defaults-from https
    interval 3
    timeout 10
    send "GET /healthz HTTP/1.1\r\nHost: otp.example.cz\r\nConnection: close\r\n\r\n"
    recv "^ok "
    recv-disable "maintenance"
}
```

`recv-disable "maintenance"` lets a node in maintenance finish its
connections instead of cutting them.

**Pool and virtual server** for the pages: members 192.0.2.11:443 and
192.0.2.12:443 with `otp_healthz`, load balancing round robin, no
persistence. Either SSL offload (client SSL profile with your certificate,
server SSL profile towards the nodes, HTTP profile with *Insert
X-Forwarded-For* enabled; then `otp --trusted-proxy <self IPs>`), or
performance L4 with the PROXY protocol (iRule) as above.

**RADIUS**: a UDP virtual server on 1812 and 1813, members on both nodes,
monitored with an HTTPS monitor like the one above but
`GET /healthz?check=radius` - it says whether RADIUS is listening, without
needing a test account. (F5's own RADIUS monitor works as well, with a test
account and its code - impractical with one-time codes.) Use
`source-address-translation none` so the nodes see the concentrators'
addresses, or add the F5's self IPs as RADIUS clients in otp.

---

## Citrix ADC / NetScaler

```
add lb monitor otp_healthz HTTP-ECV -send "GET /healthz" -recv "ok " -secure YES -interval 3 -resptimeout 2 -downTime 5
add server otp1 192.0.2.11
add server otp2 192.0.2.12
add serviceGroup otp_https SSL -cip ENABLED X-Forwarded-For
bind serviceGroup otp_https otp1 443
bind serviceGroup otp_https otp2 443
bind serviceGroup otp_https -monitorName otp_healthz
add lb vserver otp_vs SSL 192.0.2.5 443 -lbMethod ROUNDROBIN -persistenceType NONE
bind lb vserver otp_vs otp_https
bind ssl vserver otp_vs -certkeyName otp.example.cz

add lb monitor otp_radius_health HTTP-ECV -send "GET /healthz?check=radius" -recv "ok " -secure YES -destPort 443 -interval 3
add serviceGroup otp_radius RADIUS -usip YES
bind serviceGroup otp_radius otp1 1812
bind serviceGroup otp_radius otp2 1812
bind serviceGroup otp_radius -monitorName otp_radius_health
add lb vserver otp_radius_vs RADIUS 192.0.2.5 1812 -lbMethod ROUNDROBIN
bind lb vserver otp_radius_vs otp_radius
```

`-usip YES` keeps the concentrators' addresses (otherwise add the SNIP as a
RADIUS client in otp). On both nodes: `otp --trusted-proxy <SNIP>/32`.

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
 reactivation-mode timed
 dead-time 1
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
otp --maintenance on --why "balancer test"        # on otp1: the balancer must take it out
curl -sk https://192.0.2.11/healthz                # 503 maintenance otp1
otp --maintenance off
```

Sign in through the balancer and look at *Settings → Accounts → signed in*:
the address shown must be your own, not the balancer's.
