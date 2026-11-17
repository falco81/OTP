## 1.0.294 — 17 November 2026

**Bug fixes** (a hunt through the code and the pages).

- **The RADIUS test** (the Test tab, and `otp --radtest`): a server whose name does not resolve, an address with no route, or a port out of 1-65535 is said as the answer ("cannot reach …") - it was "it broke, see the log" (HTTP 500). The link to the row of the Log is only given for a test of this machine: for another server it was the newest row of that name here, some other request.
- **A search by address with /32** (`ip:10.0.0.5/32`, in the Log, the tokens, the sign-ins) finds that address, with or without its port - it found nothing.
- **The Tokens quick view** (the Tokens card on Overview): *never used* is the count of all the tokens - it counted only the newest used 1000; *Locked out now* is asked for on its own and lists a token locked before it was ever used too.
- **The Let in quick view**: *People* is the number of people let in over the whole day - it counted the 200 newest rows; a name in it opens the Log on that day, not on the window the Log was last left at.
- **At phone width**: the NTP servers' rows (Settings → Time), the remote backup's destinations and the token window's sections fit their card - they stuck out past it and the page scrolled sideways.
- **The header meter with a database agent that does not answer**: asked once with a short wait, and the 10 s pause counts from the failure - every `/api/load` of the page waited about 9.5 s for it for a minute or two.
- **Joining a database agent at a bare IPv6 address** (`fd00::1`): the whole address is the host - its last group was taken for the port (`[fd00::1]:9443` as before).

