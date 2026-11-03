"""Build an explicitly inventoried source application ZIP, without runtime data."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from nexus.deployment.artifacts import application,verify


def main():
    parser=argparse.ArgumentParser(description='Create or verify a source application artifact')
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--output',type=Path)
    group.add_argument('--verify',type=Path)
    args=parser.parse_args()
    try:
        result=verify(args.verify) if args.verify else application(ROOT,args.output)
    except (OSError,ValueError):
        print(json.dumps(dict(state='ERROR',code='APPLICATION_ARTIFACT_INVALID')))
        return 1
    print(json.dumps(dict(state='VERIFIED' if args.verify else 'CREATED',**result)))
    return 0


if __name__=='__main__':raise SystemExit(main())
