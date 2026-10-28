import pexpect, sys, time, re
env={'OTP_CONFIG':'/etc/otp/config.json','PATH':'/home/claude/shim:/usr/local/bin:/usr/bin:/bin','TERM':'xterm-256color','HOME':'/root','SHELL':'/bin/bash'}
c=pexpect.spawn('python3 /usr/local/lib/otp/otp.py --console', env=env, encoding='utf-8', timeout=40, dimensions=(50,120))
log=open('/home/claude/work/console.log','w'); c.logfile_read=log
c.expect('›'); print('menu ok')
c.sendline('1'); c.expect('›'); c.sendline('1'); c.expect('Enter - back'); print('status shown'); c.sendline(''); c.expect('›'); c.sendline('b'); c.expect('Main menu')
c.sendline('2'); c.expect('Only lines with'); c.sendline(''); c.expect('live'); time.sleep(2); c.sendintr(); c.expect('Main menu'); print('live log ok')
c.sendline('3'); c.expect('Only requests'); c.sendline(''); c.expect('as they come'); time.sleep(5); c.sendintr(); c.expect('Main menu'); print('live radius ok')
c.sendline('5'); c.expect('›'); c.sendline('8'); c.expect('Enter - back'); c.sendline(''); c.expect('›'); c.sendline('b'); c.expect('Main menu'); print('2fa status ok')
c.sendline('6'); c.expect('›'); c.sendline('1'); c.expect('Only those'); c.sendline('lockout'); c.expect('Enter - back'); print('settings search ok'); c.sendline(''); c.expect('›'); c.sendline('b'); c.expect('Main menu')
c.sendline('!'); c.expect('exit'); c.sendline('echo INSHELL$((1+1))'); c.expect('INSHELL2'); c.sendline('exit'); c.expect('Main menu'); print('shell ok')
c.sendline('q'); c.expect('console is closed'); c.expect(pexpect.EOF); print('quit ok')
