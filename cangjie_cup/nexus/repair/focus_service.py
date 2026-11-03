"""Rebuild repair focus from immutable source, native checks and copied MCP bytes."""
import hashlib
import json
from pathlib import Path

from nexus.adapters.cangjie.report_parser import parse_test_report,project_suites
from nexus.adapters.cangjie.verifier import CangjieVerifier
from nexus.analysis.point import attach_point_graph
from nexus.analysis.repair import verify_evidence
from nexus.contracts import CheckResult,digest,source_manifest,tree_hash
from nexus.execution.workspace import WorkspaceStore
from nexus.projects.index import TestParser
from nexus.repair import localization
from nexus.repair.counterexamples import failure_cases
from nexus.requirements.service import RequirementService


def sha(raw):return hashlib.sha256(raw).hexdigest()


class FocusService:
    def __init__(self,store):self.store=store;self.ws=WorkspaceStore(store.root)

    def raw(self,ref):
        p=Path(ref)
        if p.is_absolute() or len(p.parts)!=2 or p.parts[0]!='records' or '..' in p.parts:raise ValueError('定位证据引用无效')
        path=self.store.root/p
        if path.is_symlink() or path.stat().st_size>8*1024*1024:raise ValueError('定位证据为链接或过大')
        return path.read_bytes()

    def analysis(self,task,source_files):
        event=next((e for e in self.store.records(task.id,'event') if e['type']=='ANALYSIS_CONTEXT'),None)
        if event is None:return {},None
        report=verify_evidence(self.store,event);results={}
        for entry in report['files']:
            path=entry['path']
            if path not in source_files:continue
            prefix='records/'+entry['analysis_id']+'.analysis.'
            raw=self.raw(prefix+'result.json')
            if sha(raw)!=entry['result_sha256']:raise ValueError('定位分析结果原件摘要变化')
            value=json.loads(raw)
            if value['source']['code']!=source_files[path]['content'] or value['source']['source_sha256']!=entry['source_sha256']:
                raise ValueError('定位分析输入与基线不符')
            observed=next((o for o in value['observations'] if o['tool']=='sympas_dep_graph'),None)
            if observed is not None:
                graph_ref=prefix+'observations.sympas_dep_graph.json'
                value=attach_point_graph(value,raw_bytes=self.raw(graph_ref))
                if value.get('point_graph',{}).get('raw_ref'):
                    value['point_graph']['raw_ref']=graph_ref
            results[path]=value
        return results,event['context_hash']

    def public_check(self,task,subject,tree,check_plan,plan):
        values=[c for c in self.store.records(task.id,'check') if c['subject_id']==subject and c['kind']=='test' and c['tree_hash']==tree and c['plan_hash']==check_plan]
        if not values:return None,None
        value=values[-1];check=CheckResult.model_validate(value)
        if json.loads(self.raw(check.report_ref))!=value:raise ValueError('定位测试报告与原记录不符')
        raw=self.raw(check.log_ref);text=raw.decode()
        if check.package_evidence is not None:
            from nexus.repair.package_evidence import subject_context,checked_record
            rebuilt=checked_record(self.store,value,context=subject_context(self.store,task,subject),plan=plan)
            if rebuilt['state']!=check.state or rebuilt['state'] not in ('PASS','FAIL'):raise ValueError('定位XML检查原件不完整或变化')
            return check,sha(raw)
        if check.state in ('PASS','FAIL'):
            parsed=parse_test_report(text)
            if (parsed.state!=check.state or parsed.counts!=check.counts or parsed.case_results!=check.case_results or
                    project_suites(parsed,plan.suite_tests)!=check.suite_results or check.diagnostics!=text[-16000:] or
                    check.state=='PASS' and check.exit_code!=0 or check.state=='FAIL' and not check.exit_code):
                raise ValueError('定位测试日志与报告不一致')
        return check,sha(raw)

    def confirmed_cases(self,task,spec,plan,baseline,sources):
        if spec.project_id.startswith('upload_'):
            from nexus.uploads.service import UploadService
            uploads=UploadService(self.store);value=uploads._read(spec.project_id);uploads.profile(spec.project_id)
            result=[dict(test_id=value.get('public_test_class','UploadedTests')+'.case'+str(i),function=value['function'],args=e['args'],expected=e['expected'],requirement_refs=['REQ-UPLOAD'])
                for i,e in enumerate(value['examples'])]
            if value.get('source_project_index_hash'):
                for item in result:item['test_id']=value['public_test_package']+'.'+item['test_id']
                return result  # Original tests remain verification-only.
            result.extend(dict(test_id=e['id'],function=e['function'],args=e['args'],expected=e['expected'],requirement_refs=['REQ-UPLOAD']) for e in value.get('original_tests',[]))
            return result
        functions,_=localization.source_index(sources);result=[]
        if not functions:return []
        # Use a successfully indexed production file, not an arbitrary source.
        from nexus.uploads.language import Parser
        package=Parser(sources[next(iter(functions.values()))['path']]['content']).program(headers_only=True)['package']
        for path,visibility in plan.context_visibility.items():
            if visibility!='PUBLIC_TEST' or not path.endswith('_test.cj'):continue
            try:items=TestParser((baseline/path).read_text(),functions,package,path).cases()
            except ValueError:continue  # Unsupported test helpers remain unmapped.
            for item in items:
                suites=[name for name,ids in plan.suite_tests.items() if item['id'] in ids]
                refs=[ref for ref,names in plan.requirement_test_map.items() if set(suites)&set(names)]
                result.append(dict(test_id=item['id'],function=item['function'],args=item['args'],expected=item['expected'],requirement_refs=refs))
        return result

    def prepare(self,task_id,subject_id):
        task=self.store.get_task(task_id)
        if task.schema_version!=2:return None
        spec,plan=RequirementService(self.store).task_context(task)
        baseline=self.ws.verify_baseline(task.baseline_id)
        _,tree,check_plan=CangjieVerifier(self.store.root,task.id).identity(subject_id)
        sources={p:dict(content=(baseline/p).read_bytes().decode(),file_hash=h) for p,h in source_manifest(baseline).items()
            if p.endswith('.cj') and not p.endswith('_test.cj') and plan.context_visibility.get(p)=='PRODUCTION'}
        analysis,analysis_hash=self.analysis(task,sources)
        check,log_hash=self.public_check(task,subject_id,tree,check_plan,plan)
        cases=self.confirmed_cases(task,spec,plan,baseline,sources)
        public=not any(v=='VERIFICATION_ONLY' and not(spec.project_id.startswith('upload_') and p in ('verification/oracle.json','verification/properties.json','verification/relations.json','verification/sequences.json')) for p,v in plan.context_visibility.items())
        scoped_index=None
        if spec.project_id.startswith('upload_'):
            from nexus.uploads.service import UploadService
            value=UploadService(self.store)._read(spec.project_id)
            if value.get('source_project_index_hash'):
                from nexus.projects.index import inspect_project
                scoped_index=inspect_project({p:(baseline/p).read_bytes() for p in value['project_index']['manifest']})
                public=True  # Only separately bound PUBLIC facts enter scoped focus below.
        failures=[];independent=None;properties=None
        if public and check is not None and check.state=='FAIL':
            from nexus.repair.public_fields import for_task
            fields=for_task(self.store,task,check,spec=spec)
            if fields is not None:
                cases,failures=fields['cases'],fields['failures']
                if scoped_index is not None:
                    cases=[c for c in cases if c.get('visibility')=='PUBLIC']
                    failures=[f for f in failures if f.get('visibility')=='PUBLIC']
            else:
                failures=failure_cases(check,suite_tests=plan.suite_tests,requirement_test_map=plan.requirement_test_map)
                complete={f['test_id'] for f in failures if f['actual'] is not None and f['expected'] is not None}
                cases=[c for c in cases if c['test_id'] in complete]
        elif public and check is not None and check.state=='PASS' and subject_id!=task.baseline_id and (baseline/'verification/oracle.json').exists():
            from nexus.repair.exploration import ExplorationService
            from nexus.repair.oracle import expected
            independent=ExplorationService(self.store).verify(subject_id)
            if independent and independent['state']=='FAIL':
                failures=independent['failures'];rule=json.loads((baseline/'verification/oracle.json').read_bytes())
                cases=[dict(test_id=f['test_id'],log_ref=f['source']['log_ref'],function=rule['function'],args=f['args'],expected=expected(rule,f['args']),requirement_refs=['REQ-UPLOAD']) for f in failures]
        if (public and check is not None and check.state=='PASS' and subject_id!=task.baseline_id and
                (baseline/'verification/properties.json').exists() and (independent is None or independent['state']=='PASS')):
            from nexus.repair.property_service import PropertyService
            properties=PropertyService(self.store).verify(subject_id)
            if properties and properties['state']=='FAIL':
                independent=properties;failures=properties['failures'];rule=json.loads((baseline/'verification/properties.json').read_bytes())
                cases=[dict(test_id=f['test_id'],log_ref=f['source']['log_ref'],function=rule['function'],args=f['args'],
                    requirement_refs=['REQ-UPLOAD']) for f in failures]
        if (public and check is not None and check.state=='PASS' and subject_id!=task.baseline_id and
                (baseline/'verification/relations.json').exists() and (independent is None or independent['state']=='PASS') and
                (properties is None or properties['state']=='PASS')):
            from nexus.repair.relation_service import RelationService
            relation_report=RelationService(self.store).verify(subject_id)
            if relation_report is not None:
                independent=relation_report
                if relation_report['state']=='FAIL':
                    rule=json.loads((baseline/'verification/relations.json').read_bytes())
                    cases,failures=localization.relation_calls(relation_report['failures'],rule['function'])
        if (public and check is not None and check.state=='PASS' and subject_id!=task.baseline_id and
                (baseline/'verification/sequences.json').exists() and (independent is None or independent['state']=='PASS') and
                (properties is None or properties['state']=='PASS')):
            from nexus.repair.sequence_service import SequenceService
            sequence_report=SequenceService(self.store).verify(subject_id)
            if sequence_report is not None:
                independent=sequence_report
                if sequence_report['state']=='FAIL':
                    rule=json.loads((baseline/'verification/sequences.json').read_bytes())
                    cases,failures=localization.sequence_calls(sequence_report['failures'],rule['function'])
        from nexus.repair import public_fields,object_values,object_expressions,object_trace,values
        from nexus.uploads import object_types,language,public_tests
        from nexus.projects import index
        dependencies=(public_fields,object_values,object_expressions,object_trace,values,object_types,language,public_tests,index)
        binding=dict(task_id=task_id,baseline_id=task.baseline_id,baseline_hash=tree_hash(baseline),spec_hash=spec.spec_hash,
            verification_plan_hash=plan.plan_hash,subject_id=subject_id,subject_tree_hash=tree,check_plan_hash=check_plan,
            check_hash=digest(check.model_dump()) if check else None,log_sha256=log_hash,analysis_context_hash=analysis_hash,
            independent_hash=digest(independent) if independent else None,
            for_round=1 if subject_id==task.baseline_id else self.ws.candidate(subject_id).attempt+1,
            engine_hash=digest({p.name:sha(p.read_bytes()) for p in (Path(__file__),Path(localization.__file__),*[Path(m.__file__) for m in dependencies])}))
        if scoped_index is not None:
            binding.update(scoped_graph_hash=scoped_index['graph_hash'],scoped_index_hash=digest(scoped_index))
        report=localization.build_focus(sources,cases,failures,analysis,binding,**({'scoped_index':scoped_index} if scoped_index is not None else {}))
        if scoped_index is not None and check is not None and check.state=='FAIL' and not failures:
            report.update(status='UNAVAILABLE',limitations=report['limitations']+['原测试失败保留在原件；模型定位仅使用公开示例和已验证反例'])
        if not public:report.update(status='UNAVAILABLE',limitations=report['limitations']+['独立验证测试诊断未公开，不生成用例定位'])
        return report

    async def enrich(self,task,context):
        native=[e['repair_feedback'] for e in self.store.records(task.id,'event') if 'repair_feedback' in e]
        supplied=context.get('feedback',[])
        if len(native)!=len(supplied) or native and native[-1]!=supplied[-1]:raise ValueError('定位反馈与原生任务记录不符')
        subject=native[-1]['previous_candidate_id'] if native else task.baseline_id
        event=self.create(task.id,subject)
        if event is not None:context['repair_focus']=localization.model_view(event['localization'])

    def create(self,task_id,subject_id):
        for event in self.store.records(task_id,'event'):
            if event['type']=='LOCALIZATION_CONTEXT' and event['localization']['binding']['subject_id']==subject_id:
                self.verify(task_id,event);return event
        report=self.prepare(task_id,subject_id)
        if report is None:return None
        identity=digest(report)
        self.store.append_record(task_id,'event',dict(type='LOCALIZATION_CONTEXT',localization=report,context_hash=identity))
        return next(e for e in self.store.records(task_id,'event') if e['type']=='LOCALIZATION_CONTEXT' and e['context_hash']==identity)

    def verify(self,task_id,event):
        report=event['localization']
        if event['task_id']!=task_id or report['binding']['task_id']!=task_id or digest(report)!=event['context_hash']:
            raise ValueError('定位事件或任务摘要变化')
        actual=self.prepare(task_id,report['binding']['subject_id'])
        if actual!=report:raise ValueError('定位原件或版本绑定变化')
        return report
