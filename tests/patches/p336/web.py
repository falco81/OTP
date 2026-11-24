"""1.0.336 (web, OUTDIR): the pane of each node's own settings drawn from what was just saved,
not from the heartbeat read before."""
import sys, pathlib
OUT = pathlib.Path(sys.argv[1])


def edit(path, pairs):
    p = pathlib.Path(path)
    s = p.read_text()
    for a, b in pairs:
        n = s.count(a)
        assert n == 1, (str(p), n, a[:90])
        s = s.replace(a, b)
    p.write_text(s)


edit(OUT / 'web/assets/admin.js', [
("""function nodeSave(s, node, value, then) {
""",
 """/* When each node's setting was last saved here (1.0.336): the heartbeat read before it says the
   value it had then - the switch flipped back after a save, until the pane was opened again. */
var NODE_SAVED = {};
function nodeSave(s, node, value, then) {
"""),
("""  return api('settings', {settings: want, node: node}).then(function (r) { toast(r.message, 'good'); then(); })
""",
 """  return api('settings', {settings: want, node: node}).then(function (r) {
    NODE_SAVED[s.key] = Date.now() / 1000; toast(r.message, 'good'); then(); })
"""),
("""          var said = nd.own && Object.prototype.hasOwnProperty.call(nd.own, k);
""",
 """          var said = nd.own && Object.prototype.hasOwnProperty.call(nd.own, k) &&
                     !(NODE_SAVED[k] && Number(nd.at || 0) < NODE_SAVED[k]);
"""),
])
