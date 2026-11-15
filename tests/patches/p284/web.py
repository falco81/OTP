# 1.0.284 pages: the account of a certificate request picked as the token's "For" box picks a person - python3 web.py OUTDIR
import sys
O = sys.argv[1].rstrip('/') + '/'


def edit(f, pairs):
    s = open(O + f).read()
    for a, b in pairs:
        assert s.count(a) == 1, (f, s.count(a), a[:80])
        s = s.replace(a, b)
    open(O + f, 'w').write(s)


edit('web/assets/admin.js', [(
"""    inp.id = 'creq-name';
    inp.onkeydown = function (ev) { if (ev.key === 'Enter') { ev.preventDefault(); find(); } };""",
"""    inp.id = 'creq-name';""")])
edit('web/assets/admin.js', [(
"""    body.appendChild(row);
    out = el('div', 'creq-out');""",
"""    body.appendChild(row);
    /* The people of the directory offered while a name is typed (1.0.284) - the box of a token's "For":
       one picked is looked up at once. Put in once the box is in the page (its list goes beside it). */
    personSuggest(inp, {directory: (CERTL.d && CERTL.d.directory) || '', picked: function () { setTimeout(find, 0); }});
    inp.addEventListener('keydown', function (ev) {
      /* Enter takes what the list offers first, when an item of it is chosen; else it looks the name up. */
      if (ev.key === 'Enter' && !ev.defaultPrevented) { ev.preventDefault(); find(); }
    });
    out = el('div', 'creq-out');""")])
s = open(O + 'web/assets/otp.css').read()
if '.creq-find > .qs-wrap' not in s:
    s += """
/* The box of the account with the people offered (1.0.284): its wrapper takes the row's width. */
.creq-find > .qs-wrap{flex:1 1 auto;min-width:0}
.creq-find > .qs-wrap input{width:100%}
"""
    open(O + 'web/assets/otp.css', 'w').write(s)
print('1.0.284 web patched')
