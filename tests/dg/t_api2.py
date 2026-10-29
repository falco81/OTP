exec(open('/tmp/claude-0/dg/t_api.py').read().split("x = call(")[0])
print('off list:', call('/api/upgrade', {'action': 'downgrade_list'}))
print('off view:', call('/api/upgrade').get('downgrade_on'))
print('switch on:', call('/api/settings', {'settings': {'upgrade_downgrade': 1}}).get('message'))
print('on view:', call('/api/upgrade').get('downgrade_on'))
d = call('/api/upgrade', {'action': 'downgrade_list'})['downgrade']
print('on list:', [(v['version'], 'ok' if not v['why'] else 'no') for v in d['versions']])
c = call('/api/upgrade', {'action': 'downgrade_changelog', 'version': '1.0.142'})['changelog']
print('changelog 1.0.142:', c['from'], c['entry'].splitlines()[0], '| gives up', [x['version'] for x in c['lost']])
c = call('/api/upgrade', {'action': 'downgrade_changelog', 'version': '1.0.143'})['changelog']
print('changelog 1.0.143:', c['from'], c['entry'].splitlines()[0], '| gives up', [x['version'] for x in c['lost']])
print('bad:', call('/api/upgrade', {'action': 'downgrade_changelog', 'version': 'x'}))
print('switch off:', call('/api/settings', {'settings': {'upgrade_downgrade': 0}}).get('message'), call('/api/upgrade').get('downgrade_on'))
