## 1.0.332 — 24 November 2026

**Fixed**: the alert "The certificate of ... runs out soon" was raised - as bad - all the time with ACME's short-lived certificates (6 days): it compared the days left with the alert's 21 days alone. A certificate living fewer than four times those days is now warned of at a quarter of its life, past where ACME renews it (a third); a 90-day one as before.

**Fixed**: the second (ECDSA) certificate beside the RSA one - ACME's "both", or two uploaded - was never watched: one that ran out before the RSA one went on being offered by nginx to every client that takes ECDSA (most browsers), with nothing said. It is now in the alert of certificates running out, and once run out it is no longer given to nginx (the RSA one alone is offered).

