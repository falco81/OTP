## 1.0.318 — 23 November 2026

**Bug fix (remote backups)**:
- To a Windows share (SMB), an upload cut off by a full share went on to be renamed to the backup's name: a broken copy kept and offered to put back, the good one before it deleted. The upload is made alone first, the old copy replaced only after it went through.
- By FTP, SFTP or SCP, an upload cut off on the way left its half file (*.name.part*) in the folder for good. It is taken away.
- Over SSH or to a Windows share, a folder holding a file whose name is not UTF-8 failed every backup and every listing. Such names are read as they come.

**Bug fix (two nodes)**: the other node's old address could not be taken out of the database's pg_hba.conf at the moment it moved (a root helper away): it was written down as done all the same and stayed let in for good. It is asked again until it goes.

**Bug fix (firewall trial)**: a trial put back once and then kept open again was never put back when it ran out the second time. Each end is put back.

**Bug fix**: the list of locked-out names showed a locked token's limit as set, not the one in force - with *halve the limits while apart* on, a node apart from the other locks out at half of it.

**Bug fix**: the load balancer's real-address header or its sign-in to the other node, switched on alone on a node that had never had anything else changed for nginx, never reached nginx.

**Bug fix**: a VIP interface name such as *-x* or *.* was taken by the page but refused by root - and held back all the rest of the node's network settings. The page refuses it now.

