## 1.0.339 — 24 November 2026

**Fixed (texts)**: with the words "Waiting to be confirmed" of a token's mail left empty, a token to be confirmed was mailed without the link to the enrolment page - the person had a QR code that never started working and nothing saying where to confirm it. The link is there now with no words before it.

**Fixed (isemon)**: lines not sent while a TCP or TLS target of isemon was down were not counted as dropped - the metrics (`otp_isemon_dropped_total`), SNMP and the alert said 0 through a whole outage. Counted as the SIEM counts them (1.0.206).

**Fixed (import)**: a realm of a totpcgi import that could not be made stopped the import - the clients, the settings and the tokens never came. It is said, and the rest imported, as a client is.

