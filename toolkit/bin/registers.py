#!/usr/bin/env python3
"""Queues this phase's Skills Catalog and Access Register rows (toolkit/registers/*.csv) for Airtable, next to the
Changes rows, in grok-bridge/status/airtable-pending.jsonl. Idempotent: a row already queued is not queued again.
Usage: registers.py <phase>"""
import csv, json, os, sys, time

phase = sys.argv[1]
here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
queue = os.path.expanduser('~/Developer/grok-bridge/status/airtable-pending.jsonl')
if not os.path.isdir(os.path.dirname(queue)):
    print('    no grok-bridge here; register rows stay in toolkit/registers/')
    sys.exit(0)
have = open(queue).read() if os.path.exists(queue) else ''
added = 0
with open(queue, 'a') as out:
    for table, name, key in (('Access Register', 'access-register.csv', 'tool'), ('Skills Catalog', 'skills-catalog.csv', 'part_id')):
        for row in csv.DictReader(open(os.path.join(here, 'registers', name))):
            if row.pop('phase') != phase:
                continue
            tag = f'"table": "{table}", "{key}": {json.dumps(row[key])}'
            if tag in have:
                continue
            out.write(json.dumps({'table': table, key: row.pop(key), 'date_et': time.strftime('%Y-%m-%d %H:%M ET'), **row}) + '\n')
            added += 1
print(f'    {added} register row(s) queued for Airtable (Access Register / Skills Catalog)')
