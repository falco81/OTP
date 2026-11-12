# ui_chain_pki.py OUTDIR - a root, an intermediate (its CA Issuers address dead), a certificate - as JSON PEMs.
import os, sys, json, subprocess
P = sys.argv[1]
os.makedirs(P, exist_ok=True)
sh = lambda *a: subprocess.run(list(a), capture_output=True, text=True, cwd=P)
open(P + '/ca.ext', 'w').write('basicConstraints=critical,CA:TRUE\nkeyUsage=critical,keyCertSign,cRLSign\n')
open(P + '/leaf.ext', 'w').write('basicConstraints=CA:FALSE\nsubjectAltName=DNS:portal.example.test\n'
                                 'authorityInfoAccess=caIssuers;URI:http://127.0.0.1:9/int.cer\n')
sh('openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-keyout', 'root.key', '-out', 'root.pem', '-days', '3650',
   '-subj', '/CN=T269UI Root CA', '-addext', 'basicConstraints=critical,CA:TRUE', '-addext', 'keyUsage=critical,keyCertSign,cRLSign')
sh('openssl', 'req', '-newkey', 'rsa:2048', '-nodes', '-keyout', 'int.key', '-out', 'int.csr', '-subj', '/CN=T269UI Issuing CA')
sh('openssl', 'x509', '-req', '-in', 'int.csr', '-CA', 'root.pem', '-CAkey', 'root.key', '-CAcreateserial', '-out', 'int.pem', '-days', '1825', '-extfile', 'ca.ext')
sh('openssl', 'req', '-newkey', 'rsa:2048', '-nodes', '-keyout', 'leaf.key', '-out', 'leaf.csr', '-subj', '/CN=portal.example.test')
sh('openssl', 'x509', '-req', '-in', 'leaf.csr', '-CA', 'int.pem', '-CAkey', 'int.key', '-CAcreateserial', '-out', 'leaf.pem', '-days', '200', '-extfile', 'leaf.ext')
out = {k: open(P + '/' + f).read() for k, f in (('root', 'root.pem'), ('int', 'int.pem'), ('leaf', 'leaf.pem'), ('key', 'leaf.key'))}
for f in os.listdir(P):
    if f.endswith('.key') and f != 'leaf.key':
        os.unlink(os.path.join(P, f))
json.dump(out, open(P + '/pki.json', 'w'))
print('ok')
