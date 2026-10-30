# 1.0.173: Prometheus metrics.
S205 = {
 "Monitoring": "Monitoring",
 "Prometheus asks each node for its metrics.": "Prometheus se ptá každého uzlu na jeho metriky.",
 "Prometheus metrics (/metrics)": "Metriky pro Prometheus (/metrics)",
 "Its token (Bearer)": "Jeho token (Bearer)",
 "Only from": "Jen z",
 "Prometheus": "Prometheus",
 "Each node answers for itself - Prometheus asks every node, by its own address (not the VIP address, which is one node at a time). The token is the same for every node.": "Každý uzel odpovídá sám za sebe – Prometheus se ptá každého uzlu na jeho vlastní adrese (ne na VIP adrese, která je vždy jen na jednom uzlu). Token je pro všechny uzly stejný.",
 "Make a token…": "Vytvořit token…",
 "A new token for Prometheus, shown once - the one before stops opening /metrics at once.": "Nový token pro Prometheus, ukáže se jen jednou – předchozí přestane /metrics otevírat okamžitě.",
 "Make a new token for Prometheus?": "Vytvořit nový token pro Prometheus?",
 "The token used now stops opening /metrics at once - put the new one into Prometheus.": "Token, který se teď používá, přestane /metrics otevírat okamžitě – nový vložte do Promethea.",
 "The token for Prometheus": "Token pro Prometheus",
 "Shown only now. Put it into a file Prometheus reads (bearer_token_file below), readable by it alone.": "Ukazuje se jen teď. Vložte ho do souboru, který čte Prometheus (bearer_token_file níže), čitelného jen pro něj.",
 "Copy": "Kopírovat",
 "What this node answers now": "Co tento uzel teď odpovídá",
 "/metrics of this node, now": "/metrics tohoto uzlu, teď",
}
P205 = {}
R205 = {
 "Prometheus asks each node for its metrics at <span class=\"mono\">https://NODE/metrics</span>: RADIUS, the tokens, the database, the cluster and its replication, the certificates, the mail, isemon and syslog, the alerts open now.": "Prometheus se ptá každého uzlu na jeho metriky na <span class=\"mono\">https://UZEL/metrics</span>: RADIUS, tokeny, databáze, cluster a jeho replikace, certifikáty, pošta, isemon a syslog, právě otevřená upozornění.",
 "Each node answers <code>https://NODE/metrics</code> in Prometheus’ format - RADIUS, the tokens, the database, the cluster, the certificates, the mail, the alerts. Asked with the token below.": "Každý uzel odpovídá na <code>https://UZEL/metrics</code> ve formátu Promethea – RADIUS, tokeny, databáze, cluster, certifikáty, pošta, upozornění. S tokenem níže.",
 "What Prometheus sends as <code>Authorization: Bearer ...</code>. Kept sealed; <i>Make a token</i> below makes one and shows it once.": "Co Prometheus posílá jako <code>Authorization: Bearer ...</code>. Uložen zapečetěný; <i>Vytvořit token</i> níže ho vytvoří a jednou ukáže.",
 "The addresses or networks Prometheus asks from, <code>10.0.5.0/24, 2001:db8::/64</code>. Empty: from anywhere that reaches the pages, with the token.": "Adresy nebo sítě, ze kterých se Prometheus ptá, <code>10.0.5.0/24, 2001:db8::/64</code>. Prázdné: odkudkoli, kde jsou dostupné stránky, s tokenem.",
}
