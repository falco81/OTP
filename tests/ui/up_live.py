p='admin.js'; s=open(p).read()
s=s.replace("""function loadUpgrade() {""","""function loadUpgrade(live) {""",1)
s=s.replace("""    if (!VERSION_LOADED) VERSION_LOADED = d.version;
    drawUpgrade(d);""","""    if (!VERSION_LOADED) VERSION_LOADED = d.version;
    if (live) liveRun(function () { drawUpgrade(d); }); else drawUpgrade(d);""",1)
s=s.replace("""    if (document.hidden) { UP.sleeping = true; return; }
    loadUpgrade();""","""    if (document.hidden) { UP.sleeping = true; return; }
    loadUpgrade(true);""",1)
i=s.index("function drawUpgrade(d) {"); j=s.index("\n}\n",i)+3; b=s[i:j]
def rep(b, old, new):
    assert old in b, old; return b.replace(old,new,1)
b=rep(b,"""  var host = $('up-nodes');
  clear(host);
""","""  liveFill($('up-nodes'), function (host) {
""")
b=rep(b,"""    return tr;
  }, 'plain'));
  /* The package. */
  var pk = $('up-pkg');
  clear(pk);
  var plan = d.plan;
  var running = !!(plan && plan.state === 'running');
  if (d.package) {""","""    return tr;
  }, 'plain'));
  });
  /* The package. */
  var plan = d.plan;
  var running = !!(plan && plan.state === 'running');
  liveFill($('up-pkg'), function (pk) {
  if (d.package) {""")
b=rep(b,"""      pk.appendChild(det);
    }
  }
""","""      pk.appendChild(det);
    }
  }
  });
""")
b=rep(b,"""  var ph = $('up-plan');
  clear(ph);
  if (plan) {""","""  liveFill($('up-plan'), function (ph) {
  if (plan) {""")
b=rep(b,"""      ph.appendChild(r);
    }
  }
  $('up-cancel')""","""      ph.appendChild(r);
    }
  }
  });
  $('up-cancel')""")
s=s[:i]+b+s[j:]
open(p,'w').write(s)
