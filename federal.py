"""Official Simpler.Grants.gov live API integration."""
from datetime import datetime, timezone
import requests

SEARCH_URL='https://api.simpler.grants.gov/v1/opportunities/search'

def discover_federal(key,search_terms=None,statuses=None,page_size=30):
    if not key: raise ValueError('Add SIMPLER_GRANTS_API_KEY to Streamlit Secrets, or enter the key in the sidebar.')
    search_terms=search_terms or ['arts','cultural heritage','humanities','community education']
    statuses=statuses or ['posted','forecasted','closed']
    rows=[];logs=[]
    for term in search_terms:
        payload={'query':term,'filters':{'opportunity_status':{'one_of':statuses}},'pagination':{'page_offset':1,'page_size':page_size}}
        try:
            r=requests.post(SEARCH_URL,json=payload,headers={'X-API-Key':key,'Content-Type':'application/json'},timeout=(5,25))
            r.raise_for_status(); data=r.json().get('data',[])
            if isinstance(data,dict):data=data.get('opportunities',data.get('items',[]))
            if not isinstance(data,list):raise ValueError('Unrecognized opportunity response structure')
            checked=datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
            for x in data:
                if not isinstance(x,dict):continue
                uid=str(x.get('opportunity_id') or x.get('opportunity_number') or '').strip()
                if not uid:continue
                st=str(x.get('opportunity_status') or '').lower()
                u='https://simpler.grants.gov/opportunity/'+uid
                rows.append({'Category':'Federal Grants','Funder':str(x.get('agency_name') or x.get('top_level_agency_name') or 'Federal agency'),
                  'Opportunity':str(x.get('opportunity_title') or x.get('title') or 'Untitled opportunity'),
                  'Deadline':str(x.get('close_date') or '')[:10],
                  'Deadline evidence':'Official API close_date', 'Status':{'posted':'Posted','forecasted':'Forecasted','closed':'Closed','archived':'Archived'}.get(st,'Needs review'),
                  'Award':str(x.get('award_ceiling') or ''),'Eligibility':'Check federal applicant_type and the full announcement',
                  'Source_URL':u,'Details':'Federal API search match: '+term,
                  'Checked_UTC':checked,'Evidence':'Official API response', 'Suggested dates (unverified)':''})
            logs.append({'Category':'Federal Grants','Source':SEARCH_URL,'Result':f'Query {term!r}: {len(data)} returned'})
        except (requests.RequestException,ValueError) as e:
            logs.append({'Category':'Federal Grants','Source':SEARCH_URL,'Result':f'FAILED query {term!r}: {str(e)[:180]}'})
    return rows,logs
