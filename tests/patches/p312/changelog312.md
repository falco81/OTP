## 1.0.312 — 18 November 2026

**Bug fix**: Settings → Sign-in protection, the cap of wrong directory passwords.

- **The cap of wrong directory passwords is counted as the directory counts them**: the directory's counter goes back to 0 only once its time ("Reset account lockout counter after") has gone by since the LAST wrong password; here each wrong password stopped counting that long after itself. Wrong passwords 10 min apart got past a cap of 3 in 30 min without end - 5 in 40 min, and an account with a lockout threshold of 5 was locked in the directory (e-mail, the VPN and the PC with it), which is what the cap is there to prevent, the recommended cap too. The cap now counts the run with no gap of its time in it, on every node together; Locked out says when it is free again (that time after the last one). Other counts (codes sent, the guard of places) are as before.
- A domain that never locks an account: the time it counts over and the time it would lock for are greyed - they were shown as if in force.

