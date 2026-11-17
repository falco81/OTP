# 1.0.293: docs/external-database.md - the meter's rows, the intro brought up to date.
import sys
p = sys.argv[1].rstrip('/') + '/docs/external-database.md'
s = open(p).read()
a = """(1.0.291, *Moving* below). This machine's database shown as a database server
(`db_local_card`) and the database servers' rows in the header's meter come in a later
release.
"""
b = """(1.0.291, *Moving* below). This machine's database shown as a database server (1.0.292,
*This machine's database* below). The database servers' rows in the header's meter (1.0.293,
*Monitoring* below).
"""
assert s.count(a) == 1
s = s.replace(a, b)
a = """All of them are said in Czech too. Prometheus gets `otp_db_agent_up` and `otp_db_server_up`.
"""
b = a + """
**The meter in the header** (Settings → About → the performance meter, 1.0.293): with an agent,
a row for each database server after the nodes, in the look chosen, named with a small cylinder -
the server's own short name (`db1`), or `db·NODE` where that is not one. Its numbers are the
agent's (`load`), read through it every 2 s while a page looks; the other node's server from
the row its node writes. Pointed at, its panel: the graph of what was pointed at, **The
database** (the version, running for how long, the connections, *Waiting to go over
(replication)*, the size of otp's database, its data's disk, TLS) and **The machine** in numbers.
An agent that does not answer: the row dimmed and its name red, its panel says so, and the meter
does not wait for it - it is asked again 10 s later. Without an agent the meter is as before.
"""
assert s.count(a) == 1
s = s.replace(a, b)
open(p, 'w').write(s)
print('ok')
