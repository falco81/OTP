"""1.0.325 (parts): an uploaded backup kept when putting it back failed; a mail taken out while it
was sent stays out; a missing column added beside a constraint of its table."""
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


edit('90b_rbackup_api.py', [
("""    store, daemon = h.store, h.d

    def work(progress):
        tmp = None
""",
 """    store, daemon = h.store, h.d
    went = [False]

    def work(progress):
        tmp = None
"""),
("""            BIND_STRICT['tokens'] = False
            bind_tokens(store, trusted=True)
            names_nfc_kept(store)       # an old copy's names, in one form (1.0.226)
            return got
        finally:
            if tmp:
                shutil.rmtree(str(tmp), ignore_errors=True)
            if src is not None:
""",
 """            BIND_STRICT['tokens'] = False
            bind_tokens(store, trusted=True)
            names_nfc_kept(store)       # an old copy's names, in one form (1.0.226)
            went[0] = True
            return got
        finally:
            if tmp:
                shutil.rmtree(str(tmp), ignore_errors=True)
            # Kept for another try when it did not go (1.0.325): a passphrase mistyped, and the
            # upload of up to 4 GB was gone - sent again. The hour's clean-up takes it otherwise.
            if src is not None and went[0]:
"""),
])

edit('86_mail.py', [
("""        rec.update(state='sent', sent_at=now, said=rec['history'][-1]['said'], next_at=0)
        store.set_meta(MAILQ_PREFIX + qid, json.dumps(rec))
        mailq_body_drop(store, qid)
""",
 """        rec.update(state='sent', sent_at=now, said=rec['history'][-1]['said'], next_at=0)
        # Over what it read only (1.0.325): a mail taken out of the queue meanwhile came back.
        mailq_cas(store, qid, raw, rec)
        mailq_body_drop(store, qid)
"""),
("""    store.set_meta(MAILQ_PREFIX + qid, json.dumps(rec))
    if rec['state'] in ('expired',):
        mailq_body_drop(store, qid)
""",
 """    if not mailq_cas(store, qid, raw, rec) or rec['state'] in ('expired',):
        mailq_body_drop(store, qid)     # taken out meanwhile (1.0.325): stays out
"""),
])

edit('20_db.py', [
("""            for piece in re.split(r',\\s*(?=[a-z_]+ )', body):
                piece = piece.strip()
                col = piece.split(' ', 1)[0].lower()
                if not col or col in have or col == 'id':
                    continue
""",
 """            # A constraint of the table a piece of its own (1.0.325): "ts REAL, UNIQUE (k, node)"
            # was one, and its ALTER failed every ten minutes for good.
            for piece in re.split(r',\\s*(?=[a-z_]+ |UNIQUE\\b|PRIMARY\\b|CHECK\\b|FOREIGN\\b|CONSTRAINT\\b)', body):
                piece = piece.strip()
                col = piece.split(' ', 1)[0].lower()
                if not col or col in have or col == 'id' or \\
                        col.split('(')[0] in ('unique', 'primary', 'check', 'foreign', 'constraint'):
                    continue
"""),
])
