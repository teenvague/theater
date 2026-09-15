"""Resolve production booking links while retaining source URLs for ingestion."""
from urllib.parse import urljoin, urlparse, parse_qsl, urlencode, urlunparse
from bs4 import BeautifulSoup
from net import fetch

def clean_booking_url(url):
    # Use the production overview linked by TDF, not Playbill's expired first performance.
    if url=='https://tfana.org/events/america-who-hurt-you-2026-09-10-730-pm':
        return 'https://tfana.org/events/america-who-hurt-you'
    parts=urlparse(url)
    query=[(k,v) for k,v in parse_qsl(parts.query,keep_blank_values=True)
           if not k.lower().startswith('utm_') and k.lower()!='aid']
    return urlunparse(parts._replace(query=urlencode(query)))

def booking_link(markup, page):
    for link in BeautifulSoup(markup, 'html.parser').find_all('a', href=True):
        if link.get_text(' ', strip=True).casefold() != 'buy tickets':
            continue
        url=urljoin(page, link['href'])
        host=urlparse(url).hostname or ''
        if urlparse(url).scheme=='https' and host and host not in ('playbill.com','www.playbill.com'):
            return clean_booking_url(url)
    return ''

def attach(productions, get=fetch):
    report={'resolved':0,'missing':[]}
    for production in productions:
        for engagement in production['engagements']:
            page=engagement['url']
            if (urlparse(page).hostname or '').removeprefix('www.')!='playbill.com':
                engagement['ticketUrl']=page
            else:
                try:
                    url=booking_link(get(page),page)
                    if url:engagement['ticketUrl']=url
                except Exception:
                    pass  # Preserve a previously verified booking link on failure.
            if engagement.get('ticketUrl'):report['resolved']+=1
            else:report['missing'].append(production['title'])
    return report
