## 1.0.336 — 24 November 2026

**Fixed (HA pane)**: a node's own setting it has from its `config.json` could not be set back to the cluster's value on the pages - the save dropped a row that was not there, said "1 setting(s) saved.", and the node went on with its file's value. It is now saved as the node's own.

**Fixed (HA pane)**: after a node's own setting was saved, the table of each node's settings was drawn again from the heartbeat read before - a switch flipped back as if not saved, until the pane was opened again. What was just saved is shown until the node says otherwise.

**Fixed (Settings)**: a number setting left empty was refused with "a number is needed, and nothing was given", naming no setting - with several changed, which one was not marked. The setting is named, and marked on the page.

**Fixed (Czech)**: "1 setting(s) saved." after every save, and the refusals of a token's test sent too often, are in Czech.

