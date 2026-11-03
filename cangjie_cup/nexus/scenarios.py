"""Owned, registered sample projects; no client-selected source roots."""
from copy import deepcopy
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def scenarios():
    values=json.loads((ROOT/'fixtures/repair-cases/catalog.json').read_text())
    if len({v['id'] for v in values})!=len(values):raise ValueError('Duplicate scenario')
    for value in values:
        path=Path(value['source'])
        if path.is_absolute() or '..' in path.parts or path.parts[0]!='fixtures':
            raise ValueError('Invalid registered source')
    return values


def get_scenario(case_id):
    for entry in scenarios():
        if entry['id']==case_id:return deepcopy(entry)
    raise ValueError('Unknown registered scenario')


def get_profile(project_id):
    for entry in scenarios():
        if entry['kind']=='repair' and entry['project_id']==project_id:
            result=deepcopy(entry)
            result['context_visibility']={p.relative_to(ROOT/entry['source']).as_posix():
                'PUBLIC_TEST' if p.name.endswith('_test.cj') else 'PRODUCTION'
                for p in (ROOT/entry['source']/'src').glob('*.cj')}
            return result
    raise ValueError('Unknown registered requirement profile')


def registered_projects():
    return {v['project_id']:ROOT/v['source'] for v in scenarios() if v['kind']=='repair'}
