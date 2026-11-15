# a little RADIUS traffic to the test agent: Access-Requests (rejected - no realm), Status-Server, junk
import os, sys, json, time, random, socket, hashlib, struct, urllib.request
D = '/home/claude/p281/agentstate'
TOK = open(D + '/run/api-token').read().strip()
SECRET = b'radius-test-secret-281'
def call(path, body=None, sess=None):
    h = {'X-Otp-Token': TOK, 'Content-Type': 'application/json', 'X-Otp-Client': '127.0.0.1'}
    if sess: h['X-Otp-Session'] = sess
    return json.loads(urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:30977' + path,
        data=json.dumps(body).encode() if body is not None else None, headers=h, method='POST' if body is not None else 'GET'), timeout=60).read())
S = call('/api/auth/login', {'name': 'local', 'password': 'Local-Admin-Pass-281!'})['token']
try:
    call('/api/clients', {'action': 'save', 'client': {'name': 'vpn-test', 'address': '127.0.0.1', 'secret': SECRET.decode(), 'enabled': 1}}, S)
except Exception as e:
    print('client:', e)
def attr(t, v):
    return bytes([t, len(v) + 2]) + v
def pw(p, auth):
    p = p + b'\0' * (16 - len(p) % 16 if len(p) % 16 else 0)
    out, last = b'', auth
    for i in range(0, len(p), 16):
        x = hashlib.md5(SECRET + last).digest()
        c = bytes(a ^ b for a, b in zip(p[i:i+16], x)); out += c; last = c
    return out
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.settimeout(2)
end = time.time() + float(sys.argv[1] if len(sys.argv) > 1 else 900)
i = 0
while time.time() < end:
    i += 1
    auth = os.urandom(16)
    kind = random.random()
    if kind < 0.85:
        body = attr(1, ('user%d' % random.randint(1, 40)).encode()) + attr(2, pw(b'secret123456', auth)) + attr(4, socket.inet_aton('127.0.0.1'))
        code = 1
    else:
        code, body = 12, attr(80, b'\0' * 16)
    pkt = struct.pack('!BBH', code, i % 256, 20 + len(body)) + auth + body
    if code == 12:
        mac = __import__('hmac').new(SECRET, pkt, 'md5').digest()
        pkt = pkt[:-16] + mac
    s.sendto(pkt, ('127.0.0.1', 36930))
    try:
        s.recvfrom(4096)
    except socket.timeout:
        pass
    if random.random() < 0.03:
        s.sendto(os.urandom(30), ('127.0.0.1', 36930))
    time.sleep(random.uniform(0.05, 0.6) * (1.5 + __import__('math').sin(time.time() / 60)))
