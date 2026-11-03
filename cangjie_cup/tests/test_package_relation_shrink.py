"""Scoped nominal pairs may need coordinated domain choices to retain a guard."""
from nexus.projects.index import inspect_project
from nexus.repair.scoped_signature import validate
from nexus.repair import relations
from tests.sdk.test_package_services_sdk import material,rule,state


def contract():
    index=inspect_project(material());sig=validate(next(f for f in index['functions'] if f['name']=='bench.step'))
    return relations.validate_contract(rule('relation'),sig,[])


def test_scoped_distinct_objects_shrink_together_while_guard_remains_true():
    c=contract();pair=dict(left=[state(1,[]),1],right=[state(2,[]),1])
    smaller=relations.shrink_pairs(c,pair,'REL-INC')
    assert dict(left=[state(0,[]),1],right=[state(1,[]),1]) in smaller
    assert len(smaller)<=16
    assert all(relations.pair_score(p)<relations.pair_score(pair) and 'REL-INC' in relations.applicable(c,p) for p in smaller)


def test_scoped_coordinated_shrink_never_reintroduces_reserved_domain_inputs():
    c=contract();c['excluded_inputs']=[[state(0,[]),1]]
    pair=dict(left=[state(1,[]),1],right=[state(2,[]),1])
    assert all(side!=[state(0,[]),1] for p in relations.shrink_pairs(c,pair,'REL-INC') for side in p.values())
