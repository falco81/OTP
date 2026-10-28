import pexpect, time, subprocess, os
env={'OTP_CONFIG':'/etc/otp/config.json','PATH':'/usr/local/bin:/usr/bin:/bin','TERM':'xterm','HOME':'/root','SHELL':'/bin/bash','LANG':'C.UTF-8'}
cons=[pexpect.spawn('python3 /usr/local/lib/otp/otp.py --console', env=env, timeout=30, dimensions=(30,100)) for _ in range(3)]
time.sleep(4)
cons[0].send('\x1b'); cons[1].send('\x1b')     # two on the menu, one in the live log
lp=subprocess.Popen(['python3','/tmp/claude-0/load/load3.py','10','180','api'],cwd='/tmp/claude-0/load',stdout=open('/tmp/claude-0/load/soak.out','w'),stderr=subprocess.STDOUT,env=dict(os.environ,OTP_CONFIG='/etc/otp/config.json'))
pid=subprocess.run("pgrep -f 'otp.py --daemon' | head -1",shell=True,capture_output=True,text=True).stdout.split()[0]
for i in range(19):
    st=open('/proc/%s/status'%pid).read()
    rss=[l for l in st.splitlines() if l.startswith('VmRSS')][0].split()[1]; th=[l for l in st.splitlines() if l.startswith('Threads')][0].split()[1]
    print('t=%3ds rss=%s kB threads=%s'%(i*10,rss,th), flush=True)
    for c in cons:
        try: c.read_nonblocking(1<<20, timeout=0.1)
        except Exception: pass
    time.sleep(10)
lp.wait()
for c in cons: c.send('q')
print(open('/tmp/claude-0/load/soak.out').read())
