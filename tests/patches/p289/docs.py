# 1.0.289: docs - the database on a server of its own.   python3 docs.py OUT
import os, shutil, sys
O = sys.argv[1].rstrip('/') + '/'
HERE = os.path.dirname(os.path.abspath(__file__))
shutil.copy(os.path.join(HERE, 'external-database.md'), O + 'docs/external-database.md')


def edit(f, pairs):
    s = open(O + f).read()
    for a, b in pairs:
        assert s.count(a) == 1, (f, s.count(a), a[:80])
        s = s.replace(a, b)
    open(O + f, 'w').write(s)


edit('docs/the-database.md', [(
"""| PostgreSQL | the same | `python3-psycopg2` (`--with-db postgres`) |
""",
"""| PostgreSQL | the same | `python3-psycopg2` (`--with-db postgres`) |

A PostgreSQL or MariaDB on a server of its own can be looked after by otp as one on its own
machine - its certificate, its settings and their restart, its firewall - through a small
agent installed there (`install.sh --db-server`, 1.0.289): [external-database.md](external-database.md).
""")])
print('1.0.289 docs done')
