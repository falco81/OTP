## 1.0.300 — 17 November 2026

**SELinux: what is refused, sorted by what puts it right - and put right from the card** (*Settings → High security → SELinux*). Each node on its own, standalone and in a cluster; nothing changes unless asked.

- **A whole analysis at every look**: every refusal since the start (`AVC`, `USER_AVC`, `SELINUX_ERR`) read with the records of its event - the program, the whole path, the port -, grouped, each group put to `audit2why` and sorted into one kind: **a boolean**, **a label**, **a port**, **a rule of otp's**, **not for a button** (with why: a security-sensitive target, running or changing far more, writes to types of many files...), **not otp's**. A finding's id is the same at every look.
- **Put in what is selected (N)**: what may be put right comes ticked; a confirm lists exactly what root will do. The page sends **only the ids** - that node's root helper finds each in its audit log again and works out every fix itself (`setsebool -P`, `restorecon -R -v`, `semanage port -a`, a rule). **Under enforcing too**. Each step in Events; looked at again at once. What was put right counts no more; refused again after it, it comes back.
- **otp's own local module `otp_local`**: each rule exactly what was refused, in an optional block of its own, listed on the card with **Take it away** (the last one takes the module out of the policy). A module that does not load keeps none of its new rules. An uninstall takes it away.
- *Switch to enforcing* says how many things are left to put right and how many are not for a button; the count before enforcing is as before (otp's and the services' otp works with), less what was put right here.
- **`otp_server`** lets the daemon start `hostname`, `ip`, `ssh-keygen`, `ssh`/`scp`/`sftp`, `ping` and `chronyc` in their own domains under `NoNewPrivileges` (`nnp_transition`) - under enforcing they would not have run at all.
- **The report** has `findings.json` and `os/`: every process with its domain, every boolean, port type and module, the machine's local changes (`semanage ... -l -C`, `semanage export`), every listening socket.
- **Command line**: `otp --selinux-check` lists the ids and fixes; `otp --selinux-fix ID...|all`, `otp --selinux-rules`, `otp --selinux-take-away ID` (as root, asked first unless `--yes`).
- Docs: *SELinux → What SELinux refuses, sorted by what puts it right*.

