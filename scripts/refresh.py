"""Validate, merge and atomically publish normalized production feeds."""
import argparse
import copy
import importlib
import json
import os
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
ROOT = Path(__file__).resolve().parents[1]

def validate(productions):
    if not isinstance(productions, list):
        raise ValueError('productions must be an array')
    for p in productions:
        for field in ('id', 'title'):
            if not isinstance(p.get(field), str) or not p[field].strip():
                raise ValueError('Missing production ' + field)
        for field in ('credits', 'image'):
            if not isinstance(p.get(field), str):
                raise ValueError('Production ' + field + ' must be a string')
        if not isinstance(p.get('types'), list) or not all(isinstance(t,str) for t in p['types']):
            raise ValueError('types must be strings')
        # Images are either a remote URL or a path into the cache this pipeline
        # writes; a cached path is what every run after the first reads back.
        if p['image'] and not p['image'].startswith('images/'):
            if urlparse(p['image']).scheme not in ('http','https'):
                raise ValueError('Invalid image URL: '+p['image'][:80])
        if p['image'].startswith('/') or '..' in p['image']:
            raise ValueError('Unsafe image path: '+p['image'][:80])
        if not isinstance(p.get('engagements'),list) or not p['engagements']:
            raise ValueError('Missing engagements')
        for e in p['engagements']:
            for field in ('id','venue','neighborhood','sourceId','sourceUrl','url','startDate'):
                if not isinstance(e.get(field),str) or not e[field].strip():
                    raise ValueError('Missing engagement '+field)
            start=date.fromisoformat(e['startDate'])
            for field in ('openingDate','closingDate'):
                if e.get(field):
                    value=date.fromisoformat(e[field])
                    if value < start: raise ValueError(field+' precedes first performance')
            if e.get('status') not in ('scheduled','closed'):
                raise ValueError('Invalid status')
            for field in ('sourceUrl','url'):
                if urlparse(e[field]).scheme not in ('http','https'):
                    raise ValueError('Invalid outbound URL')
    return productions

def merge(productions):
    # Stable IDs are editorially mapped across adapters. Never fuzzy-merge titles:
    # two distinct revivals can share the same title.
    aliases_path = ROOT / 'data/aliases.json'
    aliases = json.loads(aliases_path.read_text()) if aliases_path.exists() else {}
    result={}
    for original in productions:
        p = copy.deepcopy(original)
        mapping = aliases.get(p['id'], {})
        p['id'] = mapping.get('productionId', p['id'])
        for e in p['engagements']:
            e['id'] = mapping.get('engagements', {}).get(e['id'], e['id'])
        key=p['id']
        if key not in result:
            result[key]=copy.deepcopy(p)
            result[key]['engagements']=[]
        else:
            # New source values enrich or correct previous metadata; blanks do
            # not erase credits/images learned from another source.
            for field, value in p.items():
                if field not in ('id', 'engagements') and value:
                    result[key][field] = copy.deepcopy(value)
        for e in p['engagements']:
            entries=result[key]['engagements']
            identity=e['id']
            previous=next((i for i,x in enumerate(entries) if x['id']==identity),None)
            if previous is None: entries.append(copy.deepcopy(e))
            elif e.get('lastSeen','')>=entries[previous].get('lastSeen',''):
                old = entries[previous]
                replacement = {**old, **copy.deepcopy(e)}
                # A remaining-ticket calendar is not the first performance.
                if e.get('startDatePrecision') == 'month' and old.get('startDatePrecision', 'day') == 'day':
                    replacement['startDate'] = old['startDate']
                    replacement['startDatePrecision'] = 'day'
                if not replacement.get('openingDate'):
                    replacement['openingDate'] = old.get('openingDate')
                entries[previous] = replacement
    return list(result.values())

def atomic(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.tmp')
    temp.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n')
    os.replace(temp,path)

def refresh(config_path,output):
    config=json.loads(config_path.read_text())
    enabled=[s for s in config['sources'] if s.get('enabled')]
    if not enabled:
        print('No live sources enabled; existing demo or live data preserved.')
        return 0
    old=json.loads(output.read_text()) if output.exists() else {'productions':[]}
    retained=[] if old.get('demo') else old['productions']
    now=datetime.now(timezone.utc).isoformat()
    incoming=[]; health=[]; success=0
    for source in enabled:
        try:
            if source['adapter'] not in ('json_feed', 'playbill', 'armory', 'cherry_lane', 'manual'):
                raise ValueError('Adapter is not registered')
            module=importlib.import_module('adapters.'+source['adapter'])
            rows=validate(module.fetch(source))
            if not rows and not source.get('allowEmpty',False):
                raise ValueError('Unexpected empty source; preserving previous records')
            for p in rows:
                for e in p['engagements']:
                    if e['sourceId']!=source['id']: raise ValueError('sourceId mismatch')
                    e['lastSeen']=now
            incoming.extend(rows);success+=1
            health.append({'sourceId':source['id'],'status':'ok','checkedAt':now,'productions':len(rows)})
            print(f"{source['id']}: ok, {len(rows)} productions",flush=True)
        except Exception as exc:
            health.append({'sourceId':source['id'],'status':'error','checkedAt':now,'error':str(exc)})
            print(f"{source['id']}: ERROR {type(exc).__name__}: {exc}",flush=True)
    for entry in health:
        if entry['sourceId']!='cherry-lane-theatre':continue
        entry['incompleteProductions']=[{'id':p['id'],'title':p['title'],
            'missingFields':[key for key in ('credits','description') if not p.get(key)]}
            for p in incoming if any(e['sourceId']==entry['sourceId'] for e in p['engagements'])
            and any(not p.get(key) for key in ('credits','description'))]
    atomic(ROOT/'data/source-health.json',{'checkedAt':now,'sources':health})
    if success:
        combined=validate(merge(retained+incoming))
        from net import fetch as fetch_page
        page_cache = {}
        def get_page(url):
            if url not in page_cache:
                page_cache[url] = fetch_page(url)
            return page_cache[url]
        try:
            import summaries
            print('summaries:', json.dumps(summaries.attach(combined, config['sources'], get=get_page))[:400], flush=True)
        except Exception as exc:
            print('summary pass skipped:', exc, flush=True)
        import tickets
        print('tickets:', json.dumps(tickets.attach(combined,get=get_page)),flush=True)
        try:
            import images
            picture_report=images.attach(combined,config['sources'],get=get_page)
            picture_report.update(images.prune(combined))
            print('images:',json.dumps(picture_report)[:400],flush=True)
        except Exception as exc:
            print('image pass skipped:',exc,flush=True)
        atomic(output,{'schemaVersion':1,'demo':False,'generatedAt':now,'productions':combined})
    # Missing records are retained: adapters must emit status=closed for explicit
    # closures. Closing dates automatically hide expired engagements in the UI.
    failed=[h['sourceId'] for h in health if h['status']=='error']
    if failed:
        print('sources failing:',', '.join(failed),flush=True)
    # Partial failure still publishes; only a total failure is worth stopping for,
    # because then there is nothing new to publish anyway.
    return 0 if success else 1

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--config',type=Path,default=ROOT/'data/sources.json')
    parser.add_argument('--output',type=Path,default=ROOT/'dist/data/shows.json')
    args=parser.parse_args()
    raise SystemExit(refresh(args.config,args.output))
