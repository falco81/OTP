## 1.0.326 — 23 November 2026

**Security (database agent)**: an otp node asking the agent to prepare its account on PostgreSQL could name an account already there that is a member of other roles (*pg_execute_server_program*, reading the server's files or every database) - its password was set to the node's, and the node could run programs as postgres on the database server. Such an account is not taken over.

**Bug fix (SELinux)**: taking out otp's last local rule while the policy's store was held (dnf updating selinux-policy) emptied the list and left the rule in the policy - the card said it was gone, and nothing could take it out. It is refused then, to be tried again.

**Bug fix (network)**: a host name of more than 64 characters was taken by the page and refused by the system only after NetworkManager's profile was changed - the new address came at the next restart, whatever it was for. It is refused before anything is touched.

**Bug fix (system updates)**: on a dnf system without dnf-plugins-core, every check said a restart was needed - and a plan restarting when needed restarted every node after every update. A restart is needed only when dnf says so.

