"""Trusted object public tests: bound target, one invocation, explicit fields."""
from nexus.repair.object_values import registry
from nexus.repair.string_trace import _fresh
from nexus.uploads.language import literal


def render(package,function,signature,examples,types,functions,original_tests):
    from nexus.repair.object_trace import constructors,input_literal
    types=registry(types);reserved=set(types)|{f['name'] for f in functions}
    reserved.update(p['name'] for f in functions for p in f['params'])
    reserved.update(case['id'].split('.')[0] for case in original_tests)
    for definition in types.values():
        reserved.update(field['name'] for field in definition['fields'])
        reserved.update(method['name'] for method in definition['methods'])
    cls=_fresh('UploadedTests',reserved);target=_fresh('__nexusObjectTarget',reserved);locals_={}
    factory_source,factories=constructors(types,reserved)
    params=', '.join(p['type'] for p in signature['params']);returned=signature['return_type']
    text=('package '+package+'\n\nimport std.unittest.*\nimport std.unittest.testmacro.*\n\n'
        'private let '+target+': ('+params+') -> '+returned+' = '+function+'\n'+factory_source+'\n@Test\nclass '+cls+' {\n')
    for index,example in enumerate(examples):
        args=', '.join(input_literal(v,types,factories) for v in example['args'])
        text+='    @TestCase\n    func case'+str(index)+'() {\n'
        call=target+'('+args+')';expected=example['expected']
        if returned not in types:text+='        @Expect('+call+', '+literal(expected,types)+')\n'
        else:
            local=_fresh('__nexusObjectActual'+str(index),reserved);locals_[str(index)]=local
            text+='        let '+local+': '+returned+' = '+call+'\n'
            for field in types[returned]['fields']:
                expression=local+'.'+field['name'];value=expected['fields'][field['name']]
                if field['type']!='Array<Int64>':text+='        @Expect('+expression+', '+literal(value,types)+')\n'
                else:
                    size=str(len(value));text+='        @Expect('+expression+'.size, '+size+')\n'
                    if value:
                        text+='        if ('+expression+'.size == '+size+') {\n'
                        for position,item in enumerate(value):text+='            @Expect('+expression+'['+str(position)+'], '+str(item)+')\n'
                        text+='        }\n'
        text+='    }\n'
    return text+'}\n',dict(public_test_class=cls,public_test_target=target,public_test_locals=locals_,public_test_constructors=factories)
