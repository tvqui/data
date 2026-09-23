from __future__ import annotations
import argparse,json,subprocess,sys
from pathlib import Path
if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--config',default='config/online.yaml'); p.add_argument('--gold',required=True); p.add_argument('--out',default='artifacts/online_evaluation/retrieval_benchmark.json'); a=p.parse_args()
    raise SystemExit(subprocess.call([sys.executable,'scripts/benchmark_retrieval.py','--config',a.config,'--gold',a.gold,'--out',a.out]))
