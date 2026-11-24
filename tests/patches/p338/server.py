"""1.0.338 (parts): an SMS of a code without {code} refused; a prompt measured with an address as
long as real ones are; the SSH prompt cut on a letter, its ": " kept."""
import sys, pathlib
P = pathlib.Path(sys.argv[1])


def edit(name, pairs):
    p = P / name
    s = p.read_text()
    for a, b in pairs:
        n = s.count(a)
        assert n == 1, (name, n, a[:90])
        s = s.replace(a, b)
    p.write_text(s)


edit('86t_texts.py', [
("""    if field[4] == 'prompt' and len(value.format(**text_samples()).encode('utf-8')) > 253:
        raise ValueError('%s: longer than RADIUS carries (253 bytes)' % label)
    if field[4] in ('subject', 'sms', 'prompt') and not value.strip():
        raise ValueError('%s cannot be empty' % label)
""",
 """    # With an address as long as a real one is (1.0.338): the sample's short one passed a prompt
    # that was cut at run time - and on the SSH gate in the middle of a letter.
    if field[4] == 'prompt' and len(value.format(**dict(
            text_samples(), dest='j******@' + 'x' * 52)).encode('utf-8')) > 251:
        raise ValueError('%s: longer than RADIUS carries (253 bytes, with an address as long as '
                         'a real one)' % label)
    if field[4] in ('subject', 'sms', 'prompt') and not value.strip():
        raise ValueError('%s cannot be empty' % label)
    # The code in an SMS that is there for it (1.0.338): left out, every SMS of a sign-in went
    # with no code in it.
    if field[4] == 'sms' and 'code' in allowed and \\
            not any(name == 'code' for _lit, name, _s, _c in parts):
        raise ValueError('%s: the code is what this SMS is for - put it in' % label)
"""),
])

edit('87s_sshotp.py', [
("""    raw = ssh_prompt(words).encode('utf-8')[:253]
""",
 """    raw = ssh_prompt(words).encode('utf-8')
    if len(raw) > 253:
        # The words cut, on a letter, before ": " is added (1.0.338): cut after, the ": " went and
        # half a letter could be left - not UTF-8, for pam_radius to show.
        w = str(words or '').rstrip().encode('utf-8')[:251].decode('utf-8', 'ignore').rstrip()
        raw = ssh_prompt(w).encode('utf-8')[:253]
"""),
])
