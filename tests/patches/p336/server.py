"""1.0.336 (parts): a node's value from its config.json can be set back to the cluster's from the
pages; a number setting left empty said by its name."""
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


edit('00_head.py', [
("""    got = _coerce(DEFAULTS[key], value)
""",
 """    try:
        got = _coerce(DEFAULTS[key], value)
    except BadSetting as e:
        # By its name (1.0.336): "a number is needed, and nothing was given" named no setting,
        # and the page could not show which of the changed ones it was.
        if str(e).startswith(key + ':'):
            raise
        raise BadSetting('%s: %s' % (key, e))
"""),
])

edit('80_daemon.py', [
("""                shared = saved_now.get(k, FILE_CONFIG.get(k, DEFAULTS[k]))
                if v == shared:
""",
 """                shared = saved_now.get(k, FILE_CONFIG.get(k, DEFAULTS[k]))
                # Not dropped where the node has it from its own config.json (1.0.336): the
                # cluster's value asked for there dropped nothing, "saved" was said, and the node
                # went on with its file's.
                if v == shared and not node_file_has(self.store, node, k):
"""),
])

edit('80_daemon.py', [
("""CLI_EVENTS_FILE = RUN_DIR / 'cli-events.jsonl'
""",
 """def node_file_has(store, node, k):
    \"\"\"Whether node `node` has setting `k` from its own config.json (1.0.336): this one's own
    file, another's as its heartbeat says.\"\"\"
    if node == node_name():
        return k in (FILE_KEYS or ())
    try:
        beat = json.loads(store.get_meta('node:' + node) or '{}')
    except ValueError:
        return False
    return isinstance(beat, dict) and k in (beat.get('own_file') or [])


CLI_EVENTS_FILE = RUN_DIR / 'cli-events.jsonl'
"""),
])
