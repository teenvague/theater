"""Short, attributed production descriptions, refreshed independently of images."""
from __future__ import annotations
import html
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from bs4 import BeautifulSoup
from net import fetch
from images import title_matches, boilerplate
from artwork_sources import TicketArtwork
ROOT = Path(__file__).resolve().parents[1]


def one_line(value):
    if not isinstance(value, str):
        return ''
    text = BeautifulSoup(html.unescape(value), 'html.parser').get_text(' ', strip=True)
    text = re.sub(r'[*_]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    # Ignore common ticket-selling and review blurbs in favour of plot copy.
    # Protect common abbreviations from being mistaken for sentence endings.
    text = re.sub(r'\b(Dr|Mr|Mrs|Ms|St)\.', r'\1<dot>', text)
    sentences = [s.replace('<dot>', '.') for s in re.split(r'(?<=[.!?])\s+(?=[A-Z“"\'])', text)]
    for sentence in sentences:
        if len(sentence.split()) < 6:
            continue
        if re.search(r'^(presented|produced|directed|cast includes|a co-production|buy|book|get|check|save|sign up|tickets|click|learn more)\b', sentence, re.I):
            continue
        if sentence.startswith(('“', '"')) or re.search(r'\b(stars? out of|critics? (rave|agree)|tickets start|official website)\b', sentence, re.I):
            continue
        # Preserve the complete sentence; only the browser knows the space available.
        result = sentence
        return result if result.endswith(('!', '?', '.')) else result + '.'
    return ''


def from_page(markup, title, venue):
    soup=BeautifulSoup(markup,'html.parser')
    titles=[n.get('content','') for n in soup.select('meta[property="og:title"],meta[name="twitter:title"]')]
    titles += [n.get_text(' ',strip=True) for n in soup.select('h1,title')]
    if not any(title_matches(t,title) for t in titles):
        return ''
    # Playbill labels the plot explicitly; billing often occupies its metadata.
    for label in soup.find_all(['b', 'strong', 'h2', 'h3']):
        if label.get_text(' ', strip=True).strip(':').casefold() in ('synopsis', 'about the show', 'about the play'):
            paragraph = label.find_next('p')
            if paragraph:
                result = one_line(paragraph.get_text(' ', strip=True))
                if result:return result
    for tag in soup.select('meta[property="og:description"],meta[name="twitter:description"],meta[name="description"]'):
        raw=tag.get('content','')
        if not boilerplate(raw,title,venue):
            result=one_line(raw)
            if result:return result
    return ''


def attach(productions, registry, get=fetch, now=None):
    now=now or datetime.now(timezone.utc)
    ticket=TicketArtwork(get,registry)
    report={'total':len(productions),'updated':0,'missing':[],'errors':[]}
    for production in productions:
        current=production.get('description','')
        try:
            checked=datetime.fromisoformat(production.get('descriptionUpdatedAt',''))
            if checked.tzinfo is None:checked=checked.replace(tzinfo=timezone.utc)
            if current and production.get('descriptionSourceUrl') and now-checked < timedelta(days=7):
                continue
        except (ValueError,TypeError):pass
        pages=list(dict.fromkeys([e['url'] for e in production['engagements']] + [production.get('imageSourceUrl','')]))
        text=source=''
        for page in pages:
            if not page.startswith('https://'):continue
            try:
                text=from_page(get(page),production['title'],production['engagements'][0]['venue'])
            except Exception as exc:
                report['errors'].append({'id':production['id'],'source':page,'error':str(exc)})
                continue
            if text:source=page;break
        if not text:
            found=ticket.find(production)
            if found:
                text=one_line(found.get('description',''))
                if text:source=found['page']
        if text:
            production.update(description=text,descriptionSourceUrl=source,
                              descriptionUpdatedAt=now.isoformat(),descriptionMethod='source-excerpt')
            report['updated']+=1
        elif current:
            # Keep last-good copy when the source is unavailable. Do not stamp
            # a success date: the next refresh should retry the missing source.
            production['description']=one_line(current)
        if not production.get('description'):report['missing'].append(production['title'])
    report['withDescription']=sum(bool(p.get('description')) for p in productions)
    report['errors']+=ticket.errors
    (ROOT/'data').mkdir(parents=True,exist_ok=True)
    (ROOT/'data/summary-health.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    return report
