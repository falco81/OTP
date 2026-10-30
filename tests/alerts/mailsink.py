# Every mail taken, kept as a file of its own in the folder given. Usage: mailsink.py PORT DIR
import socketserver, sys, os, time
PORT, DIR = int(sys.argv[1]), sys.argv[2]
os.makedirs(DIR, exist_ok=True)
class H(socketserver.StreamRequestHandler):
    def handle(self):
        w = lambda t: self.wfile.write((t + '\r\n').encode())
        w('220 sink'); data = False; buf = []
        while True:
            l = self.rfile.readline()
            if not l: break
            s = l.decode('utf-8', 'replace').rstrip('\r\n')
            if data:
                if s == '.':
                    data = False
                    open(os.path.join(DIR, '%.6f.eml' % time.time()), 'w').write('\n'.join(buf))
                    w('250 queued as TEST'); buf = []
                else:
                    buf.append(s[1:] if s.startswith('..') else s)
                continue
            c = s[:4].upper()
            if c in ('EHLO', 'HELO'): w('250 sink')
            elif c == 'DATA': data = True; w('354 go')
            elif c == 'QUIT': w('221 bye'); break
            else: w('250 ok')
socketserver.TCPServer.allow_reuse_address = True
class T(socketserver.ThreadingMixIn, socketserver.TCPServer): daemon_threads = True
T(('127.0.0.1', PORT), H).serve_forever()
