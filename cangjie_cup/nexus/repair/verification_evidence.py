"""Read-only integrity of the original public SDK result and frozen plan."""
import json
from pathlib import Path

from nexus.adapters.cangjie import report_parser
from nexus.contracts import CheckResult,digest
from nexus.repair.exploration import sha


def public_evidence(store,check,task,plan):
    """Read-only prerequisite check; never reruns the public SDK tests."""
    proof=dict(state='UNKNOWN',record_hash=digest(check) if check else None,log_sha256=None,report_sha256=None)
    if check is None:return proof
    def original(ref):
        relative=Path(ref)
        if relative.is_absolute() or len(relative.parts)!=2 or relative.parts[0]!='records' or '..' in relative.parts:
            raise ValueError('公开测试原件引用无效')
        path=store.root/relative
        if path.parent.is_symlink() or path.is_symlink() or not path.is_file() or path.stat().st_size>2*1024*1024:
            raise ValueError('公开测试原件不可用')
        with path.open('rb') as stream:raw=stream.read(2*1024*1024+1)
        if len(raw)>2*1024*1024:raise ValueError('公开测试原件超限')
        return raw
    try:
        log_raw=original(check['log_ref']);proof['log_sha256']=sha(log_raw)
        report_raw=original(check['report_ref']);proof['report_sha256']=sha(report_raw)
        # SQLite record encoding sorts nested dictionaries; compare strict
        # JSON meaning, then bind original digests against later byte edits.
        def unique(pairs):
            value={}
            for key,child in pairs:
                if key in value:raise ValueError('公开测试报告重复字段')
                value[key]=child
            return value
        def invalid_constant(value):raise ValueError('公开测试报告包含非有限值')
        saved=json.loads(report_raw,object_pairs_hook=unique,parse_constant=invalid_constant)
        if digest(saved)!=digest(check) or digest(CheckResult.model_validate(check).model_dump())!=digest(check):
            raise ValueError('公开测试报告原件与记录不符')
        if (check['schema_version']!=2 or check['spec_hash']!=task.spec_hash or check['verification_plan_hash']!=task.verification_plan_hash or
                check['toolchain_hash']!=plan.toolchain_id or check['argv']!=['cjpm','test'] or check['working_root']!='.'):
            raise ValueError('公开测试需求或工具链绑定不符')
        if check.get('package_evidence') is not None or getattr(task,'schema_version',None)==2:
            from nexus.repair.package_evidence import subject_context,checked_record
            context=subject_context(store,task,check['subject_id'])
            if context is not None or check.get('package_evidence') is not None:
                rebuilt=checked_record(store,check,context=context,plan=plan)
                proof['state']=rebuilt['state']
                return proof
        if check['state']!='PASS':
            proof['state']='FAIL' if check['state']=='FAIL' else 'UNKNOWN';return proof
        text=log_raw.decode();parsed=report_parser.parse_test_report(text);suites=report_parser.project_suites(parsed,plan.suite_tests)
        if (check['exit_code']!=0 or parsed.state!='PASS' or parsed.counts!=check['counts'] or parsed.case_results!=check['case_results'] or
                suites!=check['suite_results'] or check['diagnostics']!=text[-16000:] or
                any(suites.get(name,{}).get('state')!='PASS' for name in plan.required_suites)):
            raise ValueError('公开测试日志、用例或冻结套件不符')
        proof['state']='PASS'
    except (ValueError,OSError,KeyError,TypeError):pass
    return proof

