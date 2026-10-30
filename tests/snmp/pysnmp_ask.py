# pysnmp_ask.py JSON - an SNMPv3 manager that is not otp's (pysnmp 7), for t_snmp.py:
# {"port", "user", "auth", "ap", "priv", "pp", "do": "get"|"walk"|"bulk", "oids": [...]}
# Prints JSON: {"error": ..., "vars": [[oid, type, value], ...]}
import asyncio, json, sys
from pysnmp.hlapi.v3arch.asyncio import *

A = {'SHA-1': usmHMACSHAAuthProtocol, 'SHA-256': usmHMAC192SHA256AuthProtocol,
     'SHA-512': usmHMAC384SHA512AuthProtocol}
P = {'AES-128': usmAesCfb128Protocol, 'AES-256': usmAesBlumenthalCfb256Protocol, 'none': usmNoPrivProtocol}
q = json.loads(sys.argv[1])


async def main():
    eng = SnmpEngine()
    ua = UsmUserData(q['user'], authKey=q['ap'], privKey=q.get('pp') if q['priv'] != 'none' else None,
                     authProtocol=A[q['auth']], privProtocol=P[q['priv']])
    t = await UdpTransportTarget.create(('127.0.0.1', q['port']), timeout=2, retries=0)
    out = []
    err = None
    if q['do'] == 'get':
        e, st, ix, vbs = await get_cmd(eng, ua, t, ContextData(), *[ObjectType(ObjectIdentity(o)) for o in q['oids']])
        err = str(e) if e else (st.prettyPrint() if st else None)
        out = [[str(v[0]), v[1].__class__.__name__, v[1].prettyPrint()] for v in vbs]
    elif q['do'] == 'walk':
        async for e, st, ix, vbs in walk_cmd(eng, ua, t, ContextData(), ObjectType(ObjectIdentity(q['oids'][0])),
                                             lexicographicMode=False):
            if e or st:
                err = str(e) if e else st.prettyPrint()
                break
            out += [[str(v[0]), v[1].__class__.__name__, v[1].prettyPrint()] for v in vbs]
    else:
        async for e, st, ix, vbs in bulk_walk_cmd(eng, ua, t, ContextData(), 0, 25, ObjectType(ObjectIdentity(q['oids'][0])),
                                                  lexicographicMode=False):
            if e or st:
                err = str(e) if e else st.prettyPrint()
                break
            out += [[str(v[0]), v[1].__class__.__name__, v[1].prettyPrint()] for v in vbs]
    eng.close_dispatcher()
    print(json.dumps({'error': err, 'vars': out}))

asyncio.run(main())
