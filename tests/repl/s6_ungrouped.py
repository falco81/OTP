# Columns outside the trigger's groups (window_steps, note, display, lang, mail_fmt, last_*):
# an administrator's change on A crossing a sign-in on B is lost on A and kept on B, for good.
from fakeh import *
reset()
node('A'); o = otp.Tokens(store('A')).enroll('fred', 'admin'); s = o['secret']; settle(); pause()
node('B'); print('B sign-in:', otp.Tokens(store('B')).check('fred', code(s))[:2])
print('A window 5:', act('A', 'window', 'fred', window=5), act('A', 'note', 'fred', note='phone clock drifts'))
resume()
for n in 'AB': print(n, dict(tok(n, 'fred', 'window_steps, note, last_how')[0]))
print([r['apply_error_count'] for n in 'AB' for r in health()[n]])
