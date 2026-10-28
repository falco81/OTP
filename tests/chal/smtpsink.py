import socketserver, sys
class H(socketserver.StreamRequestHandler):
    def handle(self):
        w=lambda t: self.wfile.write((t+'\r\n').encode())
        w('220 sink'); data=False; buf=[]
        while True:
            l=self.rfile.readline()
            if not l: break
            s=l.decode('utf-8','replace').rstrip('\r\n')
            if data:
                if s=='.':
                    data=False; open('/tmp/claude-0/chal/sink.eml','w').write('\n'.join(buf)); w('250 queued as TEST'); buf=[]
                else: buf.append(s)
                continue
            c=s[:4].upper()
            if c in('EHLO','HELO'): w('250 sink')
            elif c=='DATA': data=True; w('354 go')
            elif c=='QUIT': w('221 bye'); break
            elif c=='RCPT':
                import os
                addr=s.split(':',1)[1].strip().strip('<>').lower()
                seen='/tmp/claude-0/chal/grey-seen'
                if os.path.exists('/tmp/claude-0/chal/reject'): w('550 5.1.1 no such user'); continue
                if os.path.exists('/tmp/claude-0/chal/greylist'):
                    have=open(seen).read().split() if os.path.exists(seen) else []
                    if addr not in have:
                        open(seen,'a').write(addr+'\n'); w('451 4.7.1 greylisted, try again later'); continue
                w('250 ok')
            else: w('250 ok')
socketserver.TCPServer.allow_reuse_address=True
socketserver.ThreadingTCPServer(('127.0.0.1',2525),H).serve_forever()
