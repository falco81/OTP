import pexpect, time
env={'OTP_CONFIG':'/etc/otp/config.json','PATH':'/home/claude/shim:/usr/local/bin:/usr/bin:/bin','TERM':'xterm','HOME':'/root','SHELL':'/bin/bash','LANG':'C.UTF-8'}
c=pexpect.spawn('python3 /usr/local/lib/otp/otp.py --console', env=env, encoding='utf-8', timeout=30, dimensions=(40,120))
c.logfile_read=open('/home/claude/work/tui2.log','w')
c.expect('Up/Down move'); time.sleep(1)
c.send('4'); c.expect('Delete one'); print('tokens menu')
c.send('\r'); c.expect('Search'); c.send('\x1b'); c.expect(r'\(back\)'); c.expect('Up/Down'); print('esc in ask -> menu')
c.send('\r'); c.expect('Search'); c.send('\r'); c.expect('Esc, q or Enter back'); 
out=c.before; print('tokens coloured:', '\x1b[' in out.split('otp --tokens')[-1])
c.send('\x1b'); c.expect('Up/Down'); print('esc in pause')
c.send('\x1b'); time.sleep(0.5); c.send('2'); c.expect('Only lines'); c.send('\r'); c.expect('Esc: back'); time.sleep(1.5); c.send('\x1b'); c.expect('Up/Down'); print('esc live log')
c.send('3'); c.expect('Only requests'); c.send('\r'); c.expect('Esc: back'); time.sleep(3); c.send('\x1b'); c.expect('Up/Down', timeout=10); print('esc live radius')
c.send('1'); c.send('1'); c.expect('Its journal'); c.send('4'); c.expect('journalctl -u otp -f'); time.sleep(1.5); c.send('\x1b'); c.expect('Up/Down'); print('esc journal')
c.send('\x1b'); time.sleep(0.4); c.send('5'); c.expect('Make one'); c.send('3'); c.expect('The account'); c.send('ab'); c.send('\x7f'); c.send('\x1b'); c.expect('Up/Down'); print('esc account prompt')
c.send('q'); c.expect('console is closed'); print('quit ok')
