# 1.0.292: the words of db_local_card as the pages say them (after server.py).   python3 words.py PARTS
import sys
P = sys.argv[1].rstrip('/') + '/'
f = P + '00_head.py'
s = open(f).read()
a = """    'db_local_card': 'Show this machine\\'s database as a database server',
"""
b = """    'db_local_card': 'Show this machine’s database as a database server',
"""
assert s.count(a) == 1
s = s.replace(a, b)
i = s.index("    'db_local_card': 'PostgreSQL or MariaDB on the same machine as otp drawn as a database '")
j = s.index("    'perf_meter': 'How busy the server is", i)
s = s[:i] + """    'db_local_card': 'PostgreSQL or MariaDB on the same machine as otp drawn as a database '
                     'server, in a card above Encryption to the database server: a tile for each '
                     'node’s own - its version, running for how long, TLS and its certificate, '
                     'the connections, its data’s disk, the memory, the processors and the load. '
                     'Each node looks at its own every 30 s with its own connection and tells the '
                     'other node in its row of the database, as it does everything else - no '
                     'agent, nothing more opened or allowed. Off: nothing of it is read, written '
                     'or shown. Not for SQLite, nor with otp-db-agent (which has a card of its '
                     'own).',
""" + s[j:]
open(f, 'w').write(s)
print('ok')
