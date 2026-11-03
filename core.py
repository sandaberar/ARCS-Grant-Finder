"""Normalization, deduplication and transparent ARCS screening heuristic."""
from datetime import date
from difflib import SequenceMatcher
from urllib.parse import urlsplit
import re
import pandas as pd

CATEGORIES=['City Grants','King County & 4Culture','Washington State','Private Foundations','Federal Grants']
FIELDS=['ID','Category','Funder','Opportunity','Geography','Award','Deadline','Deadline_text','Status','ARCS_program','Eligibility','Application_URL','Source_URL','Notes','Verification','Verified_on']
PROGRAMS=['All programs','Arts & exhibitions','Film festival','Journal & literature','Youth & education','Concerts & performances','Cultural exchange & heritage','Community & cultural events','Organizational support']
TERMS={'Arts & exhibitions':['art','exhibit','gallery','visual','photograph'], 'Film festival':['film','cinema','festival','movie'], 'Journal & literature':['literature','literary','journal','writer','book','reading'], 'Youth & education':['youth','young','education','student','school','teen'], 'Concerts & performances':['music','concert','perform','theater','theatre'], 'Cultural exchange & heritage':['heritage','culture','cultural','immigrant','language','history'], 'Community & cultural events':['community','neighborhood','event','cultural'], 'Organizational support':['operating','capacity','organization','nonprofit']}

def normalize(df):
    if df is None or len(df)==0:return pd.DataFrame(columns=FIELDS)
    df=df.copy()
    for c in FIELDS:
        if c not in df:df[c]=''
    df=df[FIELDS].fillna('').astype(str)
    return df.apply(lambda col: col.str.strip())

def normalized_name(s):
    s=re.sub(r'\b(202[0-9]|fy\s*2[0-9]|grant(?:s)?|program|funding|the)\b',' ',str(s).lower())
    return re.sub(r'[^a-z0-9]+',' ',s).strip()

def fingerprint(r):
    url=str(r.get('Application_URL') or r.get('Source_URL') or '').strip()
    # Never merge all entries merely because they have the same funder homepage.
    return (normalized_name(r.get('Funder','')),normalized_name(r.get('Opportunity','')))

def deduplicate(df):
    """Exact normalized title+funder merging; flag close matches for human review."""
    df=normalize(df)
    merged={}; collisions=[]
    for _,r in df.iterrows():
        k=fingerprint(r)
        if k not in merged:merged[k]=r.copy();continue
        older=merged[k]; collisions.append((older['Opportunity'],r['Opportunity']))
        # Prefer populated data and the most recent verification, don't overwrite with blanks.
        preferred,secondary=(r,older) if r['Verified_on']>=older['Verified_on'] else (older,r)
        combined=preferred.copy()
        for c in FIELDS:
            if not combined[c]:combined[c]=secondary[c]
        merged[k]=combined
    out=normalize(pd.DataFrame(list(merged.values())))
    return out,collisions

def similar_pairs(df,threshold=.88):
    """Only flag, never silently merge fuzzy matches."""
    rows=normalize(df).to_dict('records'); flagged=[]
    for i,a in enumerate(rows):
        for b in rows[i+1:]:
            if normalized_name(a['Funder'])!=normalized_name(b['Funder']):continue
            x,y=normalized_name(a['Opportunity']),normalized_name(b['Opportunity'])
            if x!=y and SequenceMatcher(None,x,y).ratio()>=threshold:flagged.append((a['Opportunity'],b['Opportunity']))
    return flagged

def effective_status(r,today=None):
    today=today or date.today()
    d=pd.to_datetime(r.get('Deadline',''),errors='coerce')
    if pd.notna(d) and d.date()<today:return 'Past deadline — recheck'
    return r.get('Status','Research') or 'Research'

def score(r,focus='All programs',today=None):
    """0-100 investigation priority, NOT eligibility or success probability."""
    t=' '.join(str(r.get(k,'')) for k in ['Opportunity','ARCS_program','Notes','Eligibility']).lower()
    candidates=[focus] if focus!='All programs' else list(TERMS)
    hits=max((sum(w in t for w in TERMS[p]) for p in candidates),default=0)
    relevance=min(40,12*hits)
    status=effective_status(r,today)
    available={'Open':25,'Rolling':25,'Upcoming':20,'Monitor':8,'Research':5,'Closed':0,'Past deadline — recheck':0}.get(status,3)
    proximity={'City Grants':18,'King County & 4Culture':18,'Washington State':14,'Private Foundations':10,'Federal Grants':8}.get(r.get('Category'),0)
    evidence=12 if r.get('Verification') in ('Official listing','Official API') else 5 if r.get('Source_URL') else 0
    return min(100,relevance+available+proximity+evidence)

def federal_search(api_key,query,statuses=('posted','forecasted'),page_size=50):
    import requests
    body={'query':query,'filters':{'opportunity_status':{'one_of':list(statuses)}},'pagination':{'page_offset':1,'page_size':min(100,max(1,page_size)),'sort_order':[{'order_by':'close_date','sort_direction':'ascending'}]}}
    response=requests.post('https://api.simpler.grants.gov/v1/opportunities/search',headers={'X-API-Key':api_key,'Content-Type':'application/json'},json=body,timeout=30)
    response.raise_for_status(); payload=response.json()
    items=payload.get('data',[])
    if not isinstance(items,list):items=items.get('opportunities',items.get('items',[]))
    records=[]
    for x in items:
        title=str(x.get('opportunity_title') or '')
        uid=str(x.get('opportunity_id') or x.get('opportunity_number') or '')
        url='https://simpler.grants.gov/opportunity/'+uid if uid else 'https://simpler.grants.gov/search'
        close=str(x.get('close_date') or '')[:10]
        state=str(x.get('opportunity_status') or '').lower()
        records.append({'ID':'FED-'+uid,'Category':'Federal Grants','Funder':str(x.get('agency_name') or 'Federal agency'),'Opportunity':title,'Geography':'United States','Award':str(x.get('award_ceiling') or ''),'Deadline':close,'Deadline_text':close,'Status':{'posted':'Open','forecasted':'Upcoming','closed':'Closed'}.get(state,'Research'),'ARCS_program':'','Eligibility':'Review federal applicant eligibility and project restrictions','Application_URL':url,'Source_URL':url,'Notes':'Imported from federal API; verify announcement and eligibility','Verification':'Official API','Verified_on':date.today().isoformat()})
    return normalize(pd.DataFrame(records))

def infer_import_columns(df,category):
    """Accept ARCS template or common source exports; never pretend they are verified."""
    df=df.copy(); keys={str(c).strip().lower():c for c in df.columns}
    mappings={'Opportunity':['opportunity','title','grant name','program name'],'Funder':['funder','agency','organization','source','grantor'],'Deadline':['deadline','close date','application close date','due date'],'Award':['award','award range','amount','funding amount'],'Source_URL':['source_url','url','link','website','program url'],'Application_URL':['application_url','apply url','application link'],'Eligibility':['eligibility','eligible applicants'],'Status':['status'],'ARCS_program':['arcs_program','program'],'Notes':['notes','description','summary']}
    mapped={}
    for dest,alternates in mappings.items():
        for alt in alternates:
            if alt in keys:mapped[dest]=df[keys[alt]];break
    if 'Opportunity' not in mapped:raise ValueError('Import needs an Opportunity or Title column.')
    out=pd.DataFrame(mapped).fillna('')
    out['Category']=category
    if 'Funder' not in out:out['Funder']='Source to verify'
    if 'Status' not in out:out['Status']='Research'
    if 'Source_URL' not in out:out['Source_URL']=''
    out['Verification']='Imported — unverified'
    out['Verified_on']=''
    out['ID']=['IMP-'+str(i+1) for i in range(len(out))]
    return normalize(out)
