## 1.0.319 — 23 November 2026

**Security (SSH with a code)**: the gate pam_radius asks on this machine took a request without a Message-Authenticator from anybody on the host - no secret needed. A local account could send another person's name over and over: wrong codes counted against them until their SSH token was held for up to a day, and with codes by SMS each one sent a message. Without a Message-Authenticator (an older pam_radius), a request is now taken only when the secret undid its password into text, which nobody without the secret can make.

**Security (database on a server of an agent)**: the rescue that moves a database connection whose TLS stopped back to no TLS - meant for a PostgreSQL on the same machine - also did it for a database server looked after by an agent, across the network: anybody between could have the TLS fail, and the node then sent everything unencrypted. It no longer does there.

**Bug fix (Kerberos)**: a browser on Windows names Kerberos by Microsoft's OID (1.2.840.48018.1.2.2) and its ticket was refused as *not Kerberos 5*. It is taken.

**Bug fix (SSH with a code)**: an SSH token removed or made again while somebody signed in with it came back as it was.

**Bug fix (local users)**: two changes to local users at once, or one at the moment a finished one's password was cleared away, lost one of them - said done, never made.

**Bug fix (two nodes)**: alerts of a database server looked after by an agent (down, its certificate, its clients) were not said by a node without an agent of its own leading the alerts - no mail, no trap.

**Bug fix**: *connect without TLS* refused by high security, or failing, still wrote the cluster's wish as no TLS - a node set up again later no longer followed the others back to TLS.

**Bug fix (SNMP)**: an answer and a trap at the same moment could be encrypted with the same IV.

