"""Live analysis of public 990-PF grants-paid tables (IRS-derived NCCS data).
Results are historical leads, not an assertion that applications are currently open.
Large public CSVs are streamed with transfer caps; no user uploads required.
"""
import csv
import io
import re
from collections import defaultdict
from datetime import datetime,timezone
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

CATALOG='https://nccs.urban.org/nccs/catalogs/catalog-efilepf-v3_1.html'
PREFIX='PF-P15-T01-SUPPLEMENTARY-INFO-GRANT-PAID'
HEADER='F9-P00-T00-HEADER'
KEYWORDS=('art','museum','music','theater','theatre','film','cinema','culture','cultural','heritage','humanities','literary','literature','festival','symphony','orchestra','photograph','romanian','immigrant','community')
RECIPIENT_STATES={'WA'}
MAX_BYTES=240_000_000

def csv_link(soup,table,year):
    target=f'{table}-{year}'
    for row in soup.find_all('tr'):
        if target not in row.get_text(' ',strip=True):continue
        for a in row.find_all('a',href=True):
            if a.get_text(' ',strip=True).lower()=='csv':return urljoin(CATALOG,a['href'])
    # The page may use markdown tables or a different HTML structure.
    for a in soup.find_all('a',href=True):
        if target.lower() in a['href'].lower() and '.csv' in a['href'].lower():return urljoin(CATALOG,a['href'])
    raise ValueError(f'No CSV link for {target} in source catalog')

def stream_rows(url,session,max_bytes=MAX_BYTES):
    """Bounded streamed csv; caller iterates without loading dataset into memory."""
    resp=session.get(url,stream=True,timeout=(8,75),headers={'User-Agent':'ARCSGrantFinder/6.0 public nonprofit research'})
    resp.raise_for_status()
    try:
        total=0
        # Requests' iter_lines handles chunk boundaries and avoids newline-in-quoted-fields issues
        # via text wrapper (csv.reader handles embedded newlines).
        class Capped(io.RawIOBase):
            def __init__(self, response):self.response=response;self.iterator=response.iter_content(chunk_size=64*1024);self.pending=b''
            def readable(self):return True
            def readinto(self,b):
                nonlocal total
                try:
                    while not self.pending:self.pending=next(self.iterator)
                except StopIteration:return 0
                size=min(len(b),len(self.pending));b[:size]=self.pending[:size];self.pending=self.pending[size:];total+=size
                if total>max_bytes:raise ValueError('Dataset exceeds download safety cap; use narrower year')
                return size
        f=io.TextIOWrapper(io.BufferedReader(Capped(resp)),encoding='utf-8-sig',errors='replace',newline='')
        yield from csv.DictReader(f)
    finally:resp.close()

def val(row,name):return str(row.get(name,'') or '').strip()

def scan_grants(rows,year,limit=500):
    matched=[]
    for r in rows:
        state=val(r,'PF_15_G_PAID_RECIP_ADDR_STATE').upper()
        recipient=val(r,'PF_15_G_PAID_RECIP_NAME_ORG_L1')
        purpose=val(r,'PF_15_G_PAID_PURPOSE')
        if not recipient:continue
        hay=(recipient+' '+purpose).lower()
        # Awards to Washington organizations plus explicitly named cultural grantmaking nationally
        if state not in RECIPIENT_STATES and not any(k in recipient.lower() for k in ('romanian','cultural','arts','museum','symphony','film')):continue
        if not any(k in hay for k in KEYWORDS):continue
        ein=re.sub('[^0-9]','',val(r,'F9_00_ORG_EIN'))
        # Some research tables expose OBJECTID only. Preserve identity, do not fabricate EIN.
        object_id=val(r,'OBJECTID')
        matched.append({'EIN':ein,'Object_ID':object_id,'Recipient':recipient,'State':state,
                        'Purpose':purpose[:300], 'Amount':val(r,'PF_15_G_PAID_AMT'),'Tax_Year':year})
    # Scan the whole annual file, not merely the first matching rows.
    # Favor cultural purpose/WA local evidence and grant amounts over file order.
    def priority(g):
        words=(g['Recipient']+' '+g['Purpose']).lower()
        points=sum(4 for w in ('romanian','art','culture','music','film','heritage','literature') if w in words)
        points+=7 if g['State']=='WA' else 0
        try: amount=float(g['Amount'].replace(',',''))
        except ValueError: amount=0
        points+=3 if 1000<=amount<=50000 else 0
        return points
    matched.sort(key=priority,reverse=True)
    return matched[:limit]

def discover_foundations(year=2025,limit=450,max_funders=25):
    """Live NCCS search, then resolve grantmakers from grant table/header or ProPublica EIN API.
    Partial scans are explicitly logged; never call them comprehensive.
    """
    checked=datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    session=requests.Session(); logs=[]; historical=[]
    try:
        resp=session.get(CATALOG,timeout=(5,20));resp.raise_for_status()
        soup=BeautifulSoup(resp.text,'html.parser')
        url=csv_link(soup,PREFIX,year)
        historical=scan_grants(stream_rows(url,session),year,limit=limit)
        logs.append({'Category':'Private Foundations','Source':url,'Result':f'Scanned annual recipient table; retained up to {limit} strongest matching records (matching is heuristic)'})
    except (requests.RequestException,ValueError,csv.Error,UnicodeError) as e:
        return [],[{'Category':'Private Foundations','Source':CATALOG,'Result':'FAILED historical source: '+str(e)[:200]}],[]
    # Resolve funder name through IRS-derived NCCS header. 2025 ~57k rows; bounded scan.
    names={}
    wanted={x['Object_ID'] for x in historical if x['Object_ID']}
    try:
        header_url=csv_link(soup,HEADER,year)
        for r in stream_rows(header_url,session,max_bytes=90_000_000):
            oid=val(r,'OBJECTID')
            if oid in wanted:
                names[oid]=(val(r,'F9_00_ORG_NAME_L1'),val(r,'F9_00_ORG_EIN'))
        logs.append({'Category':'Private Foundations','Source':header_url,'Result':f'Resolved {len(names)} grantmaker filing headers'})
    except (requests.RequestException,ValueError,csv.Error,UnicodeError) as e:
        logs.append({'Category':'Private Foundations','Source':CATALOG,'Result':'Funder header lookup failed: '+str(e)[:160]})
    groups=defaultdict(list)
    for item in historical:
        name,ein=names.get(item['Object_ID'],('',''))
        ein=ein or item['EIN']
        if not name:
            # Distinct fallback protects against incorrectly merging different foundations.
            name='Foundation filing '+(item['Object_ID'] or ein or 'unidentified')
        item['Funder']=name;item['EIN']=ein
        groups[(ein or item['Object_ID'] or name)].append(item)
    sorted_groups=sorted(groups.values(),key=lambda g:(len(g),sum(float(r['Amount']) for r in g if r['Amount'].replace('.','',1).isdigit())),reverse=True)[:max_funders]
    leads=[]
    for g in sorted_groups:
        first=g[0];ein=first['EIN']
        url=f'https://projects.propublica.org/nonprofits/organizations/{ein}' if ein else CATALOG
        amounts=[]
        for x in g:
            try:amounts.append(float(x['Amount'].replace(',','')))
            except ValueError:pass
        leads.append({'Category':'Private Foundations','Funder':first['Funder'],'Opportunity':'Historical grants to comparable cultural organizations',
          'Status':'Historical funding lead — application unverified','Award':f'${sum(amounts):,.0f} across {len(amounts)} matching grants' if amounts else '',
          'Deadline':'','Deadline evidence':'','Eligibility':'Unknown — research current guidelines','Eligibility evidence':'',
          'Source_URL':url,'Details':'; '.join(f"{r['Recipient']} (${r['Amount'] or '?'})" for r in g[:4]),
          'Checked_UTC':checked,'Evidence':f'IRS 990-PF grants paid, tax year {year}, distributed by NCCS','Verification':'Award history only',
          'Suggested dates (unverified)':''})
    return leads,logs,historical
