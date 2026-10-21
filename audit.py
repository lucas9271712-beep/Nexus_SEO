#!/usr/bin/env python3
"""NEXUS SEO Stage 1: bounded, same-origin technical SEO crawler."""
import json, os, re, sys, time
from collections import deque
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse, urldefrag
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

SITE = os.getenv('TARGET_URL', 'https://bravo-dispatch.lucasonfire77.workers.dev/').rstrip('/') + '/'
LIMIT = max(1, min(int(os.getenv('MAX_PAGES', '30')), 100))
TIMEOUT = 12
USER_AGENT = 'NexusSEOAudit/1.0 (+technical site audit; respectful crawl)'
ROOT = urlparse(SITE)

def normalized(url):
    url = urldefrag(url)[0]
    p = urlparse(url)
    if p.scheme not in ('http', 'https') or p.netloc.lower() != ROOT.netloc.lower():
        return None
    if p.path.lower().endswith(('.jpg','.jpeg','.png','.gif','.webp','.svg','.pdf','.zip','.mp4','.css','.js','.ico','.woff','.woff2','.xml')):
        return None
    return p._replace(query='', fragment='').geturl()

def fetch(url):
    req = Request(url, headers={'User-Agent': USER_AGENT, 'Accept': 'text/html,application/xhtml+xml,*/*;q=0.5'})
    try:
        with urlopen(req, timeout=TIMEOUT) as resp:
            content_type = resp.headers.get('Content-Type','')
            raw = resp.read(1_000_001)
            return {'status': resp.status, 'final_url': resp.url, 'type': content_type, 'body': raw[:1_000_000].decode('utf-8', 'replace') if ('html' in content_type or 'text/plain' in content_type or 'xml' in content_type) else ''}
    except HTTPError as exc:
        return {'status': exc.code, 'final_url': url, 'type':'', 'body':''}
    except (URLError, TimeoutError, OSError) as exc:
        return {'status': 0, 'final_url': url, 'type':'', 'body':'', 'error': str(exc)[:200]}

class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.title=''; self.description=''; self.canonical=''; self.h1=[]; self.links=[]; self.images=0; self.missing_alt=0; self.noindex=False; self._title=False; self._h1=False; self._h1_text=''
    def handle_starttag(self, tag, attrs):
        a=dict(attrs)
        if tag=='title': self._title=True
        if tag=='h1': self._h1=True; self._h1_text=''
        if tag=='meta':
            if (a.get('name') or '').lower()=='description': self.description=a.get('content','').strip()
            if (a.get('name') or '').lower()=='robots' and 'noindex' in a.get('content','').lower(): self.noindex=True
        if tag=='link' and 'canonical' in (a.get('rel') or '').lower().split(): self.canonical=a.get('href','')
        if tag=='a' and a.get('href'): self.links.append(a['href'])
        if tag=='img':
            self.images+=1
            if not a.get('alt','').strip(): self.missing_alt+=1
    def handle_endtag(self,tag):
        if tag=='title': self._title=False
        if tag=='h1': self._h1=False; self.h1.append(self._h1_text.strip())
    def handle_data(self,data):
        if self._title: self.title+=data
        if self._h1: self._h1_text+=data

def audit():
    queue=deque([SITE]); visited=set(); pages=[]; internal_links=set()
    while queue and len(pages)<LIMIT:
        url=queue.popleft()
        if url in visited: continue
        visited.add(url)
        result=fetch(url)
        page={'url':url,'status':result['status'],'title':'','description':'','canonical':'','h1':[],'images':0,'missing_alt':0,'noindex':False,'issues':[]}
        if result['status']!=200: page['issues'].append({'severity':'high','message':f'HTTP status {result["status"]} (0 means request failed)'})
        if result['status']==200 and 'html' in result['type']:
            parser=PageParser()
            try: parser.feed(result['body'])
            except Exception: pass
            page.update({k:getattr(parser,k) for k in ('title','description','canonical','h1','images','missing_alt','noindex')})
            if not parser.title.strip(): page['issues'].append({'severity':'high','message':'Missing page title'})
            elif len(parser.title.strip())>60: page['issues'].append({'severity':'low','message':'Title longer than 60 characters (review SERP appearance)'})
            if not parser.description: page['issues'].append({'severity':'medium','message':'Missing meta description'})
            if not parser.h1: page['issues'].append({'severity':'medium','message':'Missing H1 heading'})
            if len(parser.h1)>1: page['issues'].append({'severity':'low','message':'Multiple H1 headings (review hierarchy)'})
            if not parser.canonical: page['issues'].append({'severity':'medium','message':'Missing canonical link'})
            elif not normalized(urljoin(url,parser.canonical)): page['issues'].append({'severity':'low','message':'Canonical points outside the audited host'})
            if parser.missing_alt: page['issues'].append({'severity':'low','message':f'{parser.missing_alt} images have empty or missing alt (review decorative exceptions)'})
            if parser.noindex: page['issues'].append({'severity':'medium','message':'Page declares noindex (verify intent)'})
            for href in parser.links:
                target=normalized(urljoin(url,href))
                if target:
                    internal_links.add(target)
                    if target not in visited and target not in queue: queue.append(target)
        pages.append(page)
        time.sleep(0.15)
    extras={}
    for name in ('robots.txt','sitemap.xml'):
        response=fetch(urljoin(SITE,name)); extras[name]={'status':response['status'],'available':response['status']==200}
    if not pages: raise RuntimeError('No pages audited')
    counts={'high':0,'medium':0,'low':0}
    for page in pages:
        for issue in page['issues']: counts[issue['severity']]+=1
    score=max(0,100-counts['high']*12-counts['medium']*5-counts['low']*2)
    report={'site':SITE,'generated_at':datetime.now(timezone.utc).isoformat(),'score':score,'pages_crawled':len(pages),'page_limit':LIMIT,'issues':counts,'resources':extras,'pages':pages,'notes':['Score is an internal diagnostic, not a Google ranking metric.','The crawler checks up to MAX_PAGES HTML URLs on the same host; links beyond the limit are not verified.','JavaScript-rendered content may not be visible to this crawler.','robots.txt and sitemap.xml are checked for HTTP 200 only, not semantic correctness.']}
    os.makedirs('docs/data',exist_ok=True)
    with open('docs/data/report.json','w',encoding='utf-8') as f: json.dump(report,f,indent=2,ensure_ascii=False)
    print(f'Completed: {len(pages)} pages, score {score}, issues {counts}')

if __name__=='__main__':
    try: audit()
    except Exception as exc:
        print(f'Audit failed: {exc}',file=sys.stderr); sys.exit(1)
