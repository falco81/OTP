## 1.0.330 — 24 November 2026

**Fixed (Active Directory)**: an account's primary group was not among its groups. AD keeps it in the account's `primaryGroupID` alone - not in `memberOf`, nor in the group's `member` - so a realm, an administrator's role or anything else given to "Domain Users", or to a group made the users' primary one, refused every account with "does not pass LDAP group filter(s)"; a group with "Domain Users" in it was not found either. The primary group is now looked up by its SID, and the groups it is in are found with it. Directories other than AD (no `primaryGroupID`) are asked as before.

