"""Qualify registered samples with real group tools; no model or candidate execution."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import sys
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from nexus.analysis.samples import ROOT,SAMPLES,sample
from nexus.analysis.service import AnalysisService


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--record-snapshots',action='store_true')
    parser.add_argument('--ids',nargs='+',choices=[s['id'] for s in SAMPLES],default=[s['id'] for s in SAMPLES])
    args=parser.parse_args()
    root=ROOT.parents[1]/'.runtime'/('analysis-qualification-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    service=AnalysisService(root);summary=[]
    for identity in args.ids:
        entry=sample(identity);destination=ROOT/'snapshots'/identity
        if args.record_snapshots and destination.exists():raise SystemExit('Refusing to overwrite an existing sample snapshot')
        job=service.create(entry['source'],actor_id='SAMPLE_QUALIFICATION',request_key=identity,origin='SAMPLE')
        service.run(job['id']);result=service.get(job['id'],actor_id='SAMPLE_QUALIFICATION')
        row=dict(sample_id=identity,analysis_id=job['id'],status=result['status'],source_sha256=result['source']['source_sha256'],
            observations=[dict(tool=o['tool'],status=o['status']) for o in result['observations']])
        summary.append(row);print(json.dumps(row,ensure_ascii=False),flush=True)
        if args.record_snapshots:
            destination.mkdir(parents=True)
            with zipfile.ZipFile(service.export(job['id'],actor_id='SAMPLE_QUALIFICATION')) as package:
                for info in package.infolist():
                    path=destination/info.filename;path.parent.mkdir(exist_ok=True);path.write_bytes(package.read(info))
    (root/'qualification-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
    print('Qualification evidence:',root,flush=True)

if __name__=='__main__':main()
