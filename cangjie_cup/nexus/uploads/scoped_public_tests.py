"""Controller-generated public examples in the selected entry package.

Private entry functions remain private; only independent verification copies
need bridges. The caller must rederive this material from frozen originals.
"""
from pathlib import PurePosixPath

from nexus.contracts import digest
from nexus.projects.names import fresh_name,suite_name
from nexus.repair.scoped_signature import validate
from nexus.repair.scoped_imports import references
from nexus.repair.object_trace import input_literal
from nexus.uploads.language import literal,validate_examples


def render(index,function,examples):
    if type(index) is not dict or index.get('version')!=2:raise ValueError('Scoped public examples require index2')
    selected=next((f for f in index['functions'] if f['name']==function),None)
    if selected is None:raise ValueError('Selected scoped function missing')
    signature=validate(selected);scope=signature['scope'];package=scope['package']
    if scope['graph_hash']!=index['graph_hash']:raise ValueError('Public examples graph changed')
    examples=validate_examples(index,function,examples);types=signature.get('types',{})
    reserved={f['name'].rsplit('.',1)[-1] for f in index['functions']}
    reserved.update(name.rsplit('.',1)[-1] for name in types)
    reserved.update(c['id'].split('.')[-2] for c in index['test_cases'])
    reserved.update(p['name'] for f in index['functions'] for p in f['params'])
    for definition in types.values():
        reserved.update(f['name'] for f in definition['fields'])
        reserved.update(m['name'] for m in definition['methods'])
    cls=fresh_name('UploadedTests',reserved);suite=suite_name(package+'.'+cls)
    target=fresh_name('__nexusPublicTarget',reserved);locals_={}
    needed={p['type'] for p in signature['params']}|{signature['return_type']}
    needed=sorted(needed&set(types));local_types={k:k.rsplit('.',1)[-1] for k in needed if k.rsplit('.',1)[0]==package}
    external=[(kind,'__nexusPublicType'+str(i)) for i,kind in enumerate(needed) if kind not in local_types]
    aliases,imports=references(external,reserved);names={**local_types,**aliases}
    cj_type=lambda kind:names.get(kind,kind)
    source='\n'.join(['package '+package,*imports,'import std.unittest.*','import std.unittest.testmacro.*',
        'private let '+target+': ('+', '.join(cj_type(p['type']) for p in signature['params'])+') -> '+
        cj_type(signature['return_type'])+' = '+scope['local_name'],''])
    constructors={}
    for i,kind in enumerate(needed):
        factory=fresh_name('__nexusPublicCtor'+str(i),reserved);constructors[kind]=factory
        fields=types[kind]['fields'];args=[fresh_name('__nexusPublicField'+str(j),reserved) for j in range(len(fields))]
        source+='private func '+factory+'('+', '.join(a+': '+f['type'] for a,f in zip(args,fields))+'): '+cj_type(kind)+' { '+cj_type(kind)+'('+', '.join(args)+') }\n'
    source+='@Test\nclass '+cls+' {\n';case_ids={name:[] for name in ('target','regression')}
    for i,example in enumerate(examples):
        case_ids[example['suite']].append(suite+'.case'+str(i))
        args=', '.join(input_literal(value,types,constructors) for value in example['args'])
        call=target+'('+args+')';returned=signature['return_type'];expected=example['expected']
        source+='    @TestCase\n    func case'+str(i)+'() {\n'
        if returned not in types:source+='        @Expect('+call+', '+literal(expected,types)+')\n'
        else:
            local=fresh_name('__nexusPublicActual'+str(i),reserved);locals_[str(i)]=local
            source+='        let '+local+': '+cj_type(returned)+' = '+call+'\n'
            for field in types[returned]['fields']:
                expression=local+'.'+field['name'];value=expected['fields'][field['name']]
                if field['type']!='Array<Int64>':source+='        @Expect('+expression+', '+literal(value,types)+')\n'
                else:
                    size=str(len(value));source+='        @Expect('+expression+'.size, '+size+')\n'
                    if value:
                        source+='        if ('+expression+'.size == '+size+') {\n'
                        for position,item in enumerate(value):source+='            @Expect('+expression+'['+str(position)+'], '+str(item)+')\n'
                        source+='        }\n'
        source+='    }\n'
    directory=str(PurePosixPath(scope['path']).parent);paths={p.casefold() for p in index['manifest']}
    for i in range(len(paths)+1):
        path=directory+'/nexus_uploaded'+('_'+format(i,'x') if i else '')+'_test.cj'
        if path.casefold() not in paths:break
    else:raise ValueError('No fresh public test path')
    return source+'}\n',dict(public_test_path=path,public_test_package=package,public_test_class=cls,
        public_test_case_ids=case_ids,public_test_target=target,public_test_locals=locals_,public_test_constructors=constructors,
        public_test_type_names=names,public_test_imports=imports,public_test_scope_hash=digest(scope),public_test_signature_hash=digest(signature))
