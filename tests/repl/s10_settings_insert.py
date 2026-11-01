# A setting new to both databases, saved twice on A and once on B while the link is down.
# The INSERT conflict is settled by byte order (otp_same_key), not by `at`; A ends on B's
# older value, B on A's newest.
from fakeh import *
reset(); pause()
store('A').save_setting('totp_window', 3, 'adminA')        # inserted on A
time.sleep(0.2)
store('B').save_setting('totp_window', 2, 'adminB')        # inserted on B, later
time.sleep(0.2)
store('A').save_setting('totp_window', 1, 'adminA')        # A changes it again, latest of all
resume()
for n in 'AB': print(n, [dict(r) for r in q(n, "select v, at, by_who from settings where k='totp_window'")])
print([r['apply_error_count'] for n in 'AB' for r in health()[n]])
