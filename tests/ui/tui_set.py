import pexpect, time, pyte, subprocess
env={'OTP_CONFIG':'/etc/otp/config.json','PATH':'/home/claude/shim:/usr/local/bin:/usr/bin:/bin','TERM':'xterm','HOME':'/root','SHELL':'/bin/bash','LANG':'C.UTF-8'}
scr=pyte.Screen(110,32); st=pyte.ByteStream(scr)
c=pexpect.spawn('python3 /usr/local/lib/otp/otp.py --console', env=env, timeout=30, dimensions=(32,110))
def pump(t):
    end=time.time()+t
    while time.time()<end:
        try: st.feed(c.read_nonblocking(65536, timeout=0.2))
        except (pexpect.TIMEOUT, pexpect.EOF): pass
def show(n=32): print('\n'.join(l.rstrip() for l in scr.display[:n])); print('-----')
pump(3); c.send('6'); pump(1); c.send('\r'); pump(3); show(10)
c.send('/'); pump(0.5); c.send('lockout_after\r'); pump(1)
c.send('\r'); pump(1); show()
c.send('\x15'); c.send('99999\r'); pump(1.5); print('ERR:', [l.strip() for l in scr.display if 'between' in l])
c.send('\x15'); c.send('12\r'); pump(4); print('OK:', [l.strip() for l in scr.display if 'saved' in l])
c.send('/'); pump(0.5); c.send('mail_mode\r'); pump(1); c.send('\r'); pump(1); show()
c.send('\x1b'); pump(1)
c.send('\x1b[6~'); pump(0.5); c.send('\x1b[F'); pump(0.5); show(6)
c.send('\x1b'); pump(1); c.send('q'); pump(1)
print(subprocess.run(['python3','/usr/local/lib/otp/otp.py','--set','lockout_after=10'],env=env,capture_output=True,text=True).stdout)
