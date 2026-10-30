# pysnmp_traps.py PORT USER AUTH AP PRIV PP ENGINE_HEX SECONDS - receive SNMPv3 traps for a
# while (pysnmp 7), print each as JSON on a line.
import asyncio, json, os, sys, threading
from pysnmp.entity import engine, config
from pysnmp.carrier.asyncio.dgram import udp
from pysnmp.entity.rfc3413 import ntfrcv
from pysnmp.proto.api import v2c

port, user, auth, ap, priv, pp, eng_hex, secs = sys.argv[1:9]
A = {'SHA-1': config.USM_AUTH_HMAC96_SHA, 'SHA-256': config.USM_AUTH_HMAC192_SHA256,
     'SHA-512': config.USM_AUTH_HMAC384_SHA512}
P = {'AES-128': config.USM_PRIV_CFB128_AES, 'AES-256': config.USM_PRIV_CFB256_AES_BLUMENTHAL}
e = engine.SnmpEngine()
config.add_transport(e, udp.DOMAIN_NAME, udp.UdpTransport().open_server_mode(('127.0.0.1', int(port))))
config.add_v3_user(e, user, A[auth], ap, P[priv], pp, securityEngineId=v2c.OctetString(hexValue=eng_hex))


def cb(eng, ref, ctx_engine, ctx_name, vbs, cbctx):
    print(json.dumps([[str(o), v.prettyPrint()] for o, v in vbs]), flush=True)


ntfrcv.NotificationReceiver(e, cb)
print('ready', flush=True)
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
threading.Timer(float(secs), lambda: os._exit(0)).start()
e.transport_dispatcher.job_started(1)
try:
    e.open_dispatcher()
    loop.run_forever()
except Exception as x:
    print('error', x, flush=True)
