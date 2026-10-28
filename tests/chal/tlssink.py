import socketserver, ssl
CTX=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); CTX.load_cert_chain('/tmp/claude-0/zigtls/leaf.pem','/tmp/claude-0/zigtls/lk.pem')
class H(socketserver.BaseRequestHandler):
    def handle(self):
        s=self.request; f=s.makefile('rb'); w=lambda t: s.sendall((t+'\r\n').encode())
        w('220 tlssink'); data=False; tls=False; buf=[]
        while True:
            l=f.readline()
            if not l: break
            t=l.decode('utf-8','replace').rstrip('\r\n')
            if data:
                if t=='.':
                    data=False; open('/tmp/claude-0/chal/tls.eml','w').write(('TLS' if tls else 'PLAIN')+'\n'+'\n'.join(buf)); w('250 queued as TLSTEST'); buf=[]
                else: buf.append(t)
                continue
            c=t[:8].upper()
            if c.startswith(('EHLO','HELO')): w('250-tlssink'); w('250 STARTTLS') if not tls else w('250 ok')
            elif c.startswith('STARTTLS'):
                w('220 go'); s=CTX.wrap_socket(s, server_side=True); f=s.makefile('rb'); tls=True
                w=(lambda ss: (lambda t: ss.sendall((t+'\r\n').encode())))(s)
            elif c.startswith('DATA'): data=True; w('354 go')
            elif c.startswith('QUIT'): w('221 bye'); break
            else: w('250 ok')
socketserver.ThreadingTCPServer.allow_reuse_address=True
socketserver.ThreadingTCPServer(('127.0.0.1',2526),H).serve_forever()
