"""Package selected self-check fields, never runtime data or model configuration."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from nexus.deployment.artifacts import diagnostic


def main():
    parser=argparse.ArgumentParser(description='Create a diagnostic ZIP from local selfcheck.json; does not reprobe')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    try:result=diagnostic(ROOT,args.output)
    except (OSError,ValueError):
        print(json.dumps(dict(state='ERROR',code='DIAGNOSTIC_NOT_CREATED')))
        return 1
    print(json.dumps(dict(state='CREATED',**result)))
    return 0


if __name__=='__main__':raise SystemExit(main())
