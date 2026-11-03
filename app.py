from __future__ import annotations
import os
from datetime import datetime
from pathlib import Path
import pandas as pd
import streamlit as st
from discovery import SOURCES,discover_web
from federal import discover_federal
from foundations import discover_foundations

CATEGORIES=['City Grants','King County & 4Culture','Washington State','Private Foundations','Federal Grants']
PROGRAMS=['All programs','Arts & exhibitions','Film festival','Journal & literature','Youth & education','Concerts & performances','Cultural exchange & heritage','Community & cultural events','Organizational support']
TERMS={'Arts & exhibitions':['art','exhibit','gallery','visual','photograph'], 'Film festival':['film','cinema','festival','screen'], 'Journal & literature':['literature','literary','journal','writer','book','reading','humanities'], 'Youth & education':['youth','education','student','school','teen'], 'Concerts & performances':['music','concert','perform','theater','theatre'], 'Cultural exchange & heritage':['heritage','culture','cultural','immigrant','language','history'], 'Community & cultural events':['community','neighborhood','event','festival'], 'Organizational support':['operating','capacity','organization','nonprofit']}
COLUMNS=['Category','Funder','Opportunity','Status','Award','Deadline','Deadline evidence','Eligibility','Source_URL','Details','Checked_UTC','Evidence','Suggested dates (unverified)','Eligibility evidence','Verification']

st.set_page_config(page_title='ARCS Grant Finder v6',page_icon='🎭',layout='wide')
st.title('🎭 ARCS Grant Finder v6 · Live discovery + grant history')
st.caption('Searches official grant sites live when you click Search All. Research screening only; confirm eligibility and dates with funders.')


def get_key():
    try: return st.secrets.get('SIMPLER_GRANTS_API_KEY','') or os.environ.get('SIMPLER_GRANTS_API_KEY','')
    except Exception: return os.environ.get('SIMPLER_GRANTS_API_KEY','')


def rank(row,focus):
    title=' '.join(str(row.get(k,'')) for k in ['Opportunity','Details','Eligibility']).lower()
    programs=TERMS if focus=='All programs' else {focus:TERMS.get(focus,[])}
    matches=max((sum(1 for w in words if w in title) for words in programs.values()),default=0)
    points=min(55,14*matches)
    points+= {'City Grants':22,'King County & 4Culture':21,'Washington State':17,'Private Foundations':13,'Federal Grants':9}.get(row.get('Category'),0)
    points+=12 if row.get('Evidence')=='Official API response' else 7
    if row.get('Status') in ('Closed','Archived'):points-=18
    return max(0,min(100,points))


def clean_frame(rows,focus):
    df=pd.DataFrame(rows)
    if df.empty:return pd.DataFrame(columns=['Priority']+COLUMNS)
    for c in COLUMNS:
        if c not in df:df[c]=''
    df=df.fillna('')
    # Dedup by normalized website path, not by foundation homepage.
    df['dedup']=df.Source_URL.str.lower().str.rstrip('/') + '|' + df.Funder.str.lower()
    df=df.drop_duplicates(subset=['Category','dedup']).drop(columns='dedup')
    df['Priority']=df.apply(lambda r:rank(r,focus),axis=1)
    return df.sort_values('Priority',ascending=False)[['Priority']+COLUMNS]

if 'found' not in st.session_state:st.session_state.found=[]
if 'diagnostics' not in st.session_state:st.session_state.diagnostics=[]
if 'last_check' not in st.session_state:st.session_state.last_check='Not checked yet'

with st.sidebar:
    st.header('Search configuration')
    cats=st.multiselect('Sources',CATEGORIES,default=CATEGORIES)
    focus=st.selectbox('ARCS program',PROGRAMS)
    historical=st.checkbox('Include historical and closed opportunities',value=True)
    term=st.text_input('Optional federal keyword override',placeholder='Leave blank for four ARCS-related searches')
    cap=st.slider('Linked pages to check per directory',2,12,6)
    historical_year=st.selectbox('IRS foundation grant-history tax year',[2025,2024,2023],index=0)
    do_irs=st.checkbox('Discover NEW foundations from IRS grant history (larger live download)',value=True)
    st.caption('Foundation analysis scans public IRS-derived NCCS tables. It may be slower than website checks and returns historical matches, not open applications.')
    st.caption('Site checks may take time. Some websites block automated requests; failures are reported explicitly.')
    secret_key=get_key()
    if secret_key:st.success('Federal API key configured in Secrets/environment')
    else:st.info('To use federal live search, configure the API key in Streamlit Secrets or enter it below.')
    entered_key=st.text_input('Federal API key (optional, session only)',type='password') if not secret_key else ''
    api_key=secret_key or entered_key
    run=st.button('🔎 Search All — LIVE',type='primary',use_container_width=True,disabled=not cats)

if run:
    data=[];logs=[]
    selected=set(cats)
    website_categories=selected-{'Federal Grants'}
    if 'Private Foundations' in website_categories and do_irs:
        with st.spinner('Analyzing IRS-derived historical foundation grant records...'):
            x,y,h=discover_foundations(historical_year);data+=x;logs+=y
            st.session_state.history=h
    if website_categories:
        with st.spinner('Checking official city, county, state and foundation websites...'):
            a,b=discover_web(website_categories,cap);data+=a;logs+=b
    if 'Federal Grants' in selected:
        if api_key:
            with st.spinner('Searching Simpler.Grants.gov API...'):
                a,b=discover_federal(api_key,[term] if term.strip() else None,
                   ['posted','forecasted','closed','archived'] if historical else ['posted','forecasted'])
                data+=a;logs+=b
        else:logs.append({'Category':'Federal Grants','Source':'Simpler.Grants.gov','Result':'SKIPPED: no API key configured'})
    st.session_state.found=data
    st.session_state.diagnostics=logs
    st.session_state.last_check=datetime.now().astimezone().strftime('%Y-%m-%d %H:%M %Z')

df=clean_frame(st.session_state.found,focus)
if not historical and not df.empty:
    df=df[~df.Status.isin(['Closed','Archived'])]

m=st.columns(4)
m[0].metric('Live entries',len(df))
m[1].metric('Categories found',df.Category.nunique() if len(df) else 0)
m[2].metric('Source errors',sum('FAILED' in x.get('Result','') for x in st.session_state.diagnostics))
m[3].metric('Last checked',st.session_state.last_check)

st.info('Explicit deadlines are extracted only from date + deadline language in the same page block. Dates and eligibility still need funder confirmation. IRS grant history identifies potential funders, NOT currently open applications.')

left,history_tab,right=st.tabs(['🔎 Live grant results','🏛️ Foundation grants paid','🩺 Source diagnostics & methodology'])
with left:
    search=st.text_input('Filter results by keyword')
    show=df
    if search and len(show):
        mask=show[['Funder','Opportunity','Details','Category']].astype(str).agg(' '.join,axis=1).str.contains(search,case=False,regex=False)
        show=show[mask]
    st.dataframe(show,hide_index=True,use_container_width=True,
        column_config={'Source_URL':st.column_config.LinkColumn('Official source',display_text='Open page'),
                       'Priority':st.column_config.ProgressColumn('Research priority / 100',min_value=0,max_value=100),
                       'Details':st.column_config.TextColumn('Page excerpt',width='large'),
                       'Deadline evidence':st.column_config.TextColumn('Deadline context',width='large')})
    st.download_button('Download latest live results (optional backup)',show.to_csv(index=False).encode(),'arcs_live_results.csv','text/csv',disabled=show.empty)
    st.caption('Priority is a keyword-based research heuristic, NOT confirmation of eligibility, open status or award likelihood.')
with history_tab:
    st.write('Historical award recipients from public IRS Form 990-PF returns via NCCS. These awards do **not** demonstrate current eligibility or an open grant cycle.')
    awards=pd.DataFrame(st.session_state.get('history',[]))
    if awards.empty:st.info('No grant-payment history loaded. Run Search All with Private Foundations and historical discovery selected; review diagnostics for access errors.')
    else:
        st.dataframe(awards,hide_index=True,use_container_width=True)
        st.download_button('Download historical grant evidence',awards.to_csv(index=False).encode(),'arcs_foundation_grant_history.csv','text/csv')
with right:
    st.subheader('Every source checked, including failures')
    logs=pd.DataFrame(st.session_state.diagnostics)
    if logs.empty:st.write('Click Search All to run source checks.')
    else:st.dataframe(logs,hide_index=True,use_container_width=True,column_config={'Source':st.column_config.LinkColumn('Source')})
    with st.expander('Sources configured'):
        st.dataframe(pd.DataFrame(SOURCES,columns=['Category','Funder','URL','Follow links']),hide_index=True,use_container_width=True,column_config={'URL':st.column_config.LinkColumn('Source')})
    st.write('**How this works:** Federal: the official Simpler.Grants.gov API. Other categories: download official public pages and follow selected official links in real time. The app does not use a third-party search engine, so its coverage is limited to the configured sites and their visible links.')
    st.write('**Verification boundaries:** A date is extracted only when explicitly attached to deadline language in a single page block, and only if there is one unambiguous date. It is not an assurance of current eligibility. Website failures, JavaScript-only content and ambiguities appear in diagnostics. Foundation grant-history scans are bounded and may be partial, so missing a funder is NOT evidence that it does not fund arts organizations. IRS history cannot establish that an application window is open.')
    st.write('**Team collaboration:** Data is in session memory, so search results are not shared across users or persisted after a Streamlit restart. A database is needed for a shared application tracker.')
