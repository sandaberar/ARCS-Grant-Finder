"""Live, bounded official-site discovery. No claims of verified deadlines unless extracted.
Website pages vary: failure is shown, not hidden behind preloaded CSV results.
"""
from __future__ import annotations
import re
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse, urldefrag
import requests
from verification import extract
from bs4 import BeautifulSoup

SOURCES = [
 # category, organization, URL, discover links?, narrow terms for linked opportunities
 ('City Grants','Seattle Office of Arts & Culture','https://www.seattle.gov/arts/opportunities/current-calls-and-funding',True),
 ('City Grants','Seattle Office of Arts & Culture','https://www.seattle.gov/arts/programs/grants/smart-ventures-grant',False),
 ('City Grants','Seattle Department of Neighborhoods','https://www.seattle.gov/neighborhoods/community-grants/neighborhood-matching-fund',True),
 ('City Grants','Bellevue Arts & Culture','https://bellevuewa.gov/city-government/departments/community-development/arts-and-culture/grants',True),
 ('City Grants','Redmond Cultural Arts','https://www.redmond.gov/FormCenter/Parks-Recreation-11/2027-Cultural-Arts-Operating-Support-Gra-306',False),
 ('City Grants','Issaquah Arts & Culture','https://www.issaquahwa.gov/m/newsflash/Home/Detail/6565',False),
 ('King County & 4Culture','4Culture','https://www.4culture.org/project-grants/',True),
 ('King County & 4Culture','4Culture','https://www.4culture.org/grants/open-4culture/',False),
 ('King County & 4Culture','4Culture','https://www.4culture.org/grants/',True),
 ('Washington State','Washington State Arts Commission','https://www.arts.wa.gov/grants/',True),
 ('Washington State','Washington Department of Commerce','https://www.commerce.wa.gov/contracting/',True),
 ('Washington State','Humanities Washington','https://www.humanities.org/programs/grants-and-sponsorships/',True),
 ('Private Foundations','MMS Giving Foundation','https://mmsgiving.org/app.html',False),
 ('Private Foundations','Seattle Foundation','https://www.seattlefoundation.org/grantmaking/',True),
 ('Private Foundations','ArtsFund','https://www.artsfund.org/grants/',True),
]
KEYWORDS = ('grant','fund','funding','apply','application','opportunit','arts','heritage','culture','sponsor','support','award','fellowship','matching')
BAD_LABELS = ('privacy','cookie','accessibility','contact','login','sign in','newsletter','donate','social media','facebook','instagram','twitter','staff','board','career','job','about us','home','terms')
PROGRAM_WORDS=('arts','art','culture','cultural','heritage','humanities','film','music','festival','literature','youth','education','exhibit','community','nonprofit','grant','funding','organization','project','artswa')
MONTHS=r'(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'
DATE_RE=re.compile(r'\b('+MONTHS+r'\s+\d{1,2},?\s+20\d{2}|20\d{2}-\d{2}-\d{2})\b',re.I)
DEADLINE_RE=re.compile(r'\b(deadline|due date|applications? (?:close|due)|apply by|final application|closing date)\b',re.I)


def _clean(value): return ' '.join(str(value).split())

def _same_site(a,b):
    x=urlparse(a).hostname or ''; y=urlparse(b).hostname or ''
    return x.lstrip('www.')==y.lstrip('www.')

def _candidate(label,url):
    name=_clean(label)
    if not 5 <= len(name) <= 120: return False
    low=name.lower()
    if any(w in low for w in BAD_LABELS): return False
    if not any(w in low for w in KEYWORDS): return False
    p=urlparse(url)
    if p.scheme not in ('http','https'): return False
    if re.search(r'\.(pdf|docx?|xlsx?|png|jpg|zip)$',p.path,re.I):return False
    if '/tag/' in p.path or '/category/' in p.path:return False
    return True

def _extract_evidence(soup):
    # Text is taken from the *same linked program page*, not the parent directory.
    # Extract snippet around a deadline expression; don't assume it applies if ambiguous.
    text=_clean(soup.get_text(' ',strip=True))[:45000]
    matches=list(DEADLINE_RE.finditer(text))
    evidence=[]
    for m in matches[:10]:
        s=text[max(0,m.start()-55):min(len(text),m.end()+160)]
        evidence.append(s)
    first=evidence[0] if evidence else ''
    dates=[]
    for snip in evidence:
        for d in DATE_RE.findall(snip):
            try:
                from dateutil import parser
                day=parser.parse(d,fuzzy=False).date().isoformat()
                if day not in dates:dates.append(day)
            except (ValueError,OverflowError):pass
    return text,first,dates

def _fetch(session,url):
    r=session.get(url,timeout=(5,13),allow_redirects=True,headers={'User-Agent':'ARCSGrantFinder/5.0 (+public grants research; respects official site access)'})
    r.raise_for_status()
    if 'text/html' not in r.headers.get('Content-Type','text/html').lower():raise ValueError('Page is not HTML')
    if len(r.content)>2_500_000:raise ValueError('HTML page too large')
    soup=BeautifulSoup(r.text,'html.parser')
    for tag in soup.select('script,style,nav,footer,header,aside'):tag.decompose()
    return soup,r.url

def _one_entry(category,funder,label,url,soup,parent=False):
    text,deadline_evidence,dates=_extract_evidence(soup)
    verified=extract(soup)
    # No inferred dates or open statuses from loose page text; present evidence for review.
    intro=' '.join(text[:380].split())
    checked=datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    return {'Category':category,'Funder':funder,'Opportunity':_clean(label),
      'Deadline':verified['Deadline'] if not parent else '', 'Deadline evidence':verified['Deadline evidence'] if not parent else '',
      'Status':verified['Status'] if not parent else 'Directory / check links',
      'Award':'','Eligibility':'Requires review of official guidelines','Eligibility evidence':verified['Eligibility evidence'] if not parent else '', 'Verification':verified['Verification'] if not parent else 'Directory only',
      'Source_URL':url,'Details':intro,'Checked_UTC':checked,
      'Evidence':'Official website fetched live' if not parent else 'Official directory checked live',
      'Suggested dates (unverified)':'; '.join(dates[:4])}

def discover_web(selected_categories=None,max_linked_per_source=7):
    """Fetch current public agency/funder pages and *selected linked pages* (bounded requests).
    Returns (records, diagnostics). Network failures appear in diagnostics.
    """
    selected=set(selected_categories or [s[0] for s in SOURCES]); rows=[];log=[];seen=set()
    s=requests.Session()
    for category,funder,src,follow in SOURCES:
        if category not in selected:continue
        try:
            soup,actual=_fetch(s,src)
            title=soup.find('h1') or soup.title
            label=_clean(title.get_text(' ',strip=True))[:100] if title else funder+' funding page'
            # A direct program page is an opportunity; a directory page only contributes verified links.
            if not follow:
                rows.append(_one_entry(category,funder,label,actual,soup))
            if follow:
                candidates=[]
                for link in soup.find_all('a',href=True):
                    url=urldefrag(urljoin(actual,link['href']))[0]
                    name=_clean(link.get_text(' ',strip=True))
                    if not _same_site(actual,url) or url==actual or not _candidate(name,url):continue
                    # Prefer cultural granting links over broader agency portals
                    pts=sum(w in name.lower() for w in PROGRAM_WORDS)+sum(w in url.lower() for w in ('grant','fund','arts','heritage'))
                    candidates.append((pts,name,url))
                candidates.sort(key=lambda x:x[0],reverse=True)
                visited=set();count=0
                for pts,name,url in candidates:
                    if url in visited or url in seen:continue
                    visited.add(url)
                    if count>=max_linked_per_source:break
                    try:
                        sub,actual_sub=_fetch(s,url)
                        h=sub.find('h1')
                        label=_clean(h.get_text(' ',strip=True)) if h else name
                        rows.append(_one_entry(category,funder,label[:120],actual_sub,sub))
                        seen.add(actual_sub); count+=1
                    except (requests.RequestException,ValueError) as e:
                        log.append({'Category':category,'Source':url,'Result':'Linked page failed: '+str(e)[:130]})
                if count==0:
                    rows.append(_one_entry(category,funder,label,actual,soup,parent=True))
                log.append({'Category':category,'Source':src,'Result':f'Checked; {count} linked opportunity pages read'})
            else:
                log.append({'Category':category,'Source':src,'Result':'Direct program page checked'})
        except (requests.RequestException,ValueError) as e:
            log.append({'Category':category,'Source':src,'Result':'FAILED: '+str(e)[:180]})
    return rows,log
