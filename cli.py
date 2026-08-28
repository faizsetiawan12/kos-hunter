#!/usr/bin/env python3
import argparse, json, os, sys, tempfile
from pathlib import Path
from search.mamikos import MamikosAdapter, AREAS
from kos_hunter.domain import Gender, TenantProfile, SearchCriteria
SHORTLIST_FILE=Path(os.environ.get('KOS_HUNTER_SHORTLIST',Path(__file__).parent/'shortlist.json'))
def cmd_search(args):
 try: adapter=MamikosAdapter()
 except Exception as e: print(f'✗ {e}'); return 1
 try: listings=adapter.search(SearchCriteria(args.price_max,TenantProfile(Gender.PUTRA)),area=args.area)
 except Exception as e: print(f'✗ Search failed: {e}'); return 1
 seen={};
 for l in listings:
  if l.gender != Gender.PUTRI and l.price <= args.price_max: seen.setdefault(l.id,l)
 data=[{'rank':i,'id':l.id,'title':l.name,'price':l.price,'area':l.location,'facilities':sorted(l.amenities),'available':l.available,'source':l.source,'link':l.url,'ranking_reasons':[]} for i,l in enumerate(seen.values(),1)]
 parent=SHORTLIST_FILE.parent; parent.mkdir(parents=True,exist_ok=True)
 fd,tmp=tempfile.mkstemp(dir=parent,prefix='.shortlist-',text=True)
 try:
  with os.fdopen(fd,'w') as f: json.dump(data,f,ensure_ascii=False,indent=2); f.flush(); os.fsync(f.fileno())
  os.replace(tmp,SHORTLIST_FILE)
 except Exception:
  try: os.unlink(tmp)
  except OSError: pass
  raise
 for x in data: print(f"{x['rank']}. {x['title']} Rp{x['price']:,}/bulan — {x['area']} — {x['link']}")
 return 0
def main():
 p=argparse.ArgumentParser(); s=p.add_subparsers(dest='cmd',required=True); q=s.add_parser('search'); q.add_argument('--area',choices=AREAS,default='kukel'); q.add_argument('--price-max',type=int,default=2000000); q.set_defaults(fn=cmd_search); a=p.parse_args(); return a.fn(a)
if __name__=='__main__': sys.exit(main())
