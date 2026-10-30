# Automatic certificates - ACME (1.0.169)

*Settings → Automatic certificates*, for a full administrator, off until switched
on. The certificate of the web address - and, where asked, each node's own - is
ordered from an ACME CA and renewed by itself when fewer than `acme_days` (30)
days are left. A failed try is tried again after 6 hours; the alerts tell of a
certificate running out as always.

| Setting | |
|---|---|
| `acme_ca` | Let's Encrypt, its staging (to try - browsers do not trust it), or another (`acme_url`, `acme_ca_pem` for its root): step-ca, an internal CA |
| `acme_for` | the web address (or this node where there is none), each node's own name, or both |
| `acme_node_name` | a node's DNS name; empty: its full host name |
| `acme_challenge` | HTTP-01 or DNS-01 |
| `acme_key` | ECDSA P-256 or RSA 2048 |

The account key (ECDSA P-256) is made once and kept sealed in the database; every
request is signed with it (ES256, with openssl). The certificate and its key go
where an uploaded one goes, and every node serving it puts it in.

## In a cluster

The web address's certificate is ordered by one node - the first by name of the
nodes heard from; a node's own by that node. Both nodes serve it.

## HTTP-01 - the CA asks port 80

nginx sends `http://NAME/.well-known/acme-challenge/TOKEN` to `acme.php`, which
asks the daemon; the answer is kept in the database, so **whichever node has the
web address answers it**. Every node's port-80 server has the names in its
`server_name` and the location - put in by the root helper when ACME is switched
on. *Try port 80* asks it from the node as the CA will (a firewall in front of
the servers may still stop the CA from outside). The name must point at the web
address (or the node), and port 80 must be open to the CA.

## DNS-01 - nothing open to the internet

For servers the CA cannot see: the CA reads `_acme-challenge.NAME TXT`. Who puts
it there (`acme_dns`):

- **RFC 2136** (BIND, PowerDNS, Knot, ...): `nsupdate` (`dnf install bind-utils`)
  with a TSIG key - `acme_dns_server`, `acme_dns_zone`, `acme_dns_tsig_name`,
  `acme_dns_tsig_alg`, `acme_dns_tsig_secret` (sealed). The key is written to a
  file only otp reads (0600) for the moment nsupdate runs - never on its command
  line. On BIND, a key allowed to change only those records:

  ```
  tsig-keygen -a hmac-sha256 otp-acme. > /etc/named/otp-acme.key
  zone "example.cz" {
      ...
      update-policy { grant otp-acme. name _acme-challenge.otp.example.cz. TXT; };
  };
  ```
- **Cloudflare**: `acme_dns_token` (sealed), a token with *Zone - DNS - Edit*.
- **acme-dns**: `acme_dns_url`, `acme_dns_user`, `acme_dns_key` (sealed),
  `acme_dns_subdomain` from its registration; `_acme-challenge.NAME` a CNAME to
  `SUBDOMAIN.auth.example.cz` once.
- **By hand**: the record is shown on the page; the order waits up to an hour
  for *It is in DNS*. Renewals wait for you the same way.

After the record is put in, `acme_dns_wait` seconds (30) are waited for DNS to
carry it; it is taken away again once the CA has looked (RFC 2136, Cloudflare).
