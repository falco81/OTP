# 1.0.289: the pages' relay lets /api/db-agent through (GET readonly, POST fulladmin - the daemon checks).
import sys
O = sys.argv[1].rstrip('/') + '/'
f = O + 'web/admin/index.php'
s = open(f).read()
pairs = [
("""        'certlogin' => '/api/certlogin',
    ];
    $writes = [""",
"""        'certlogin' => '/api/certlogin',
        'db-agent' => '/api/db-agent',
    ];
    $writes = ["""),
("""        'card-gone' => '/api/auth/cardgone',
    ];""",
"""        'card-gone' => '/api/auth/cardgone',
        'db-agent' => '/api/db-agent',
    ];"""),
("""        otp_relay($writes[$what], 'POST', sent_json(), 90.0);""",
"""        // the database server's agent (1.0.289): a restart through it waits up to 240 s
        otp_relay($writes[$what], 'POST', sent_json(), $what === 'db-agent' ? 300.0 : 90.0);"""),
]
for a, b in pairs:
    assert s.count(a) == 1, a[:60]
    s = s.replace(a, b)
open(f, 'w').write(s)
print('1.0.289 php done')
