import socket, ssl, time, threading, subprocess
ctx=ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
socks=[]
for i in range(20):
    s=ctx.wrap_socket(socket.create_connection(('127.0.0.1',443)), server_hostname='x')
    s.send(b"POST /admin/?api=settings HTTP/1.1\r\nHost: x\r\nContent-Type: application/json\r\nContent-Length: 1000\r\n\r\n{")
    socks.append(s)
time.sleep(2)
t=time.time()
r=subprocess.run(['curl','-sk','-m','8','-o','/dev/null','-w','%{http_code}','https://127.0.0.1/healthz'],capture_output=True,text=True)
print('healthz with 20 slow bodies:', r.stdout, '%.2fs'%(time.time()-t))
for s in socks: s.close()
