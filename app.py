import os
from datetime import date
from pathlib import Path
import pandas as pd
import streamlit as st
from core import CATEGORIES,PROGRAMS,FIELDS,normalize,deduplicate,similar_pairs,score,effective_status,federal_search,infer_import_columns

ROOT=Path(__file__).parent
st.set_page_config(page_title='ARCS Grant Finder v4',page_icon='🎭',layout='wide')
st.title('🎭 ARCS Grant Finder · v4')
st.caption('Five-category funding discovery for American Romanian Cultural Society. Priority scores are research heuristics, not eligibility or award predictions.')

@st.cache_data
def initial():
    return normalize(pd.read_csv(ROOT/'leads.csv',dtype=str,keep_default_na=False))
if 'additional' not in st.session_state:st.session_state.additional=normalize(None)
if 'pipeline' not in st.session_state:st.session_state.pipeline=pd.read_csv(ROOT/'pipeline.csv',dtype=str,keep_default_na=False)

with st.sidebar:
    st.header('Find funding')
    cats=st.multiselect('Funding categories',CATEGORIES,default=CATEGORIES)
    focus=st.selectbox('ARCS program',PROGRAMS)
    states=st.multiselect('Status',['Open','Rolling','Upcoming','Monitor','Research','Closed','Invitation only','Past deadline — recheck'],default=['Open','Rolling','Upcoming','Monitor','Research','Closed','Past deadline — recheck'])
    term=st.text_input('Search titles, funders, notes')
    st.caption('All statuses selected by default, including historical and closed cycles.')

raw=pd.concat([initial(),st.session_state.additional],ignore_index=True)
records,duplicates=deduplicate(raw)
records['Effective status']=records.apply(effective_status,axis=1)
records['Priority']=records.apply(lambda r:score(r,focus),axis=1)
records['Deadline sort']=pd.to_datetime(records.Deadline,errors='coerce')
shown=records[records.Category.isin(cats)&records['Effective status'].isin(states)]
if term:
    mask=shown[['Funder','Opportunity','Notes','Eligibility','ARCS_program']].astype(str).agg(' '.join,axis=1).str.contains(term,case=False,regex=False)
    shown=shown[mask]
shown=shown.sort_values(['Priority','Deadline sort'],ascending=[False,True],na_position='last')

m=st.columns(4)
m[0].metric('Unique leads',len(records));m[1].metric('City & county leads',len(records[records.Category.isin(CATEGORIES[:2])]))
m[2].metric('Open / upcoming / rolling',len(records[records['Effective status'].isin(['Open','Upcoming','Rolling'])]));m[3].metric('Imported this session',len(st.session_state.additional))
st.warning('Open/rolling statuses are based on recorded research or an import. A past deadline is automatically flagged; unknown opening dates cannot be verified automatically. Always inspect current funder guidelines.')

def show(df):
    if df.empty:st.info('No matching records. Broaden the filters or import more opportunities.');return
    cols=['Priority','Category','Funder','Opportunity','Award','Deadline_text','Effective status','ARCS_program','Eligibility','Source_URL','Verification']
    st.dataframe(df[cols],hide_index=True,use_container_width=True,column_config={'Priority':st.column_config.ProgressColumn('Priority / 100',min_value=0,max_value=100),'Source_URL':st.column_config.LinkColumn('Funder source',display_text='Open source')})

t1,t2,t3,t4,t5=st.tabs(['🔎 All opportunities','🇺🇸 Federal live search','📥 Import state & local','📋 Applications','📚 Sources & guidance'])
with t1:
    st.subheader('Unified ranked results')
    show(shown)
    st.download_button('Download filtered CSV',shown.drop(columns=['Effective status','Priority','Deadline sort']).to_csv(index=False).encode(),'arcs_filtered_leads.csv','text/csv')
    if duplicates:st.caption(f'{len(duplicates)} exact normalized duplicates merged (funder + opportunity).')
    fuzzy=similar_pairs(records)
    if fuzzy:
        with st.expander(f'Potential duplicate titles requiring manual review ({len(fuzzy)})'):
            for a,b in fuzzy:st.write(f'• {a} / {b}')
    st.subheader('By funding category')
    for category in CATEGORIES:
        subset=shown[shown.Category==category]
        with st.expander(f'{category} · {len(subset)}'):
            show(subset)
with t2:
    st.subheader('Live federal opportunities · Simpler.Grants.gov')
    st.write('Requires a free API key. Results are retained only for this browser session unless exported or saved to your own storage.')
    key=st.text_input('Federal API key',value=os.getenv('SIMPLER_GRANTS_API_KEY',''),type='password')
    query=st.text_input('Search query',value='arts')
    federal_status=st.multiselect('Federal status',['posted','forecasted','closed'],default=['posted','forecasted'])
    count=st.slider('Maximum results',10,100,50,step=10)
    if st.button('Search federal API',type='primary'):
        if not key:st.error('Enter the API key from simpler.grants.gov/developers.')
        elif not federal_status:st.error('Choose at least one federal status.')
        else:
            try:st.session_state.federal_found=federal_search(key,query,federal_status,count)
            except Exception as e:st.error(f'Federal API request failed: {e}. Check the key, network and API documentation.')
    found=st.session_state.get('federal_found',normalize(None))
    if len(found):
        st.success(f'{len(found)} federal records returned. Review eligibility before importing.')
        st.dataframe(found[['Funder','Opportunity','Deadline','Status','Application_URL']],hide_index=True,use_container_width=True,column_config={'Application_URL':st.column_config.LinkColumn('Opportunity')})
        st.download_button('Export federal results',found.to_csv(index=False).encode(),'arcs_federal_results.csv','text/csv')
        if st.button('Add federal results to unified list'):
            st.session_state.additional=normalize(pd.concat([st.session_state.additional,found],ignore_index=True));st.rerun()
with t3:
    st.subheader('Import opportunities from Washington State and other sources')
    st.write('Use CSV exports from official sources. Import files manually; there is no undocumented website scraping or live state-wide API in this version.')
    category=st.selectbox('Which category does the file belong to?',CATEGORIES,index=2)
    uploaded=st.file_uploader('Upload a CSV (Title or Opportunity required)',type=['csv'])
    if uploaded:
        try:
            parsed=infer_import_columns(pd.read_csv(uploaded,dtype=str,keep_default_na=False),category)
            st.caption(f'Preview: {len(parsed)} opportunities · imported records are labeled unverified.')
            st.dataframe(parsed[['Funder','Opportunity','Deadline','Award','Source_URL']],hide_index=True,use_container_width=True)
            if st.button('Add imported leads'):
                st.session_state.additional=normalize(pd.concat([st.session_state.additional,parsed],ignore_index=True));st.rerun()
        except Exception as exc:st.error(str(exc))
    st.download_button('Download import template',pd.DataFrame(columns=['Title','Agency','Close Date','Award Range','URL','Eligibility','Description']).to_csv(index=False).encode(),'arcs_import_template.csv','text/csv')
    st.download_button('Export complete merged leads',records[FIELDS].to_csv(index=False).encode(),'arcs_grants_master.csv','text/csv')
    restore=st.file_uploader('Restore previously saved master CSV',type=['csv'],key='restore')
    if restore:
        try:
            import_df=normalize(pd.read_csv(restore,dtype=str,keep_default_na=False))
            if st.button('Load saved master records'):
                st.session_state.additional=import_df;st.rerun()
        except Exception as exc:st.error(str(exc))
with t4:
    st.subheader('Application tracker')
    st.info('Changes are stored in this running session only. Download the CSV to retain edits for the next visit; no database or shared storage is configured yet.')
    saved=st.file_uploader('Restore saved application tracker CSV',type=['csv'],key='tracker_upload')
    if saved:
        try:
            candidate=pd.read_csv(saved,dtype=str,keep_default_na=False)
            if st.button('Load tracker CSV'):st.session_state.pipeline=candidate;st.rerun()
        except Exception as exc:st.error(str(exc))
    edited=st.data_editor(st.session_state.pipeline,num_rows='dynamic',hide_index=True,use_container_width=True,column_config={'Stage':st.column_config.SelectboxColumn(options=['Research','Eligibility review','Planning','Drafting','Submitted','Awarded','Declined','Deferred'])},key='pipeline_editor')
    st.download_button('Download current tracker CSV',edited.to_csv(index=False).encode(),'arcs_tracker_updated.csv','text/csv')
with t5:
    st.subheader('Official sources to check and import')
    for name,url,why in [
      ('Federal — Simpler.Grants.gov','https://simpler.grants.gov/developers','Live API supported with a key'),
      ('Washington Arts Commission (ArtsWA)','https://www.arts.wa.gov/grants/','Arts and culture funding; check each grant cycle'),
      ('Washington State Department of Commerce','https://www.commerce.wa.gov/','State grants and notices'),
      ('Washington Office of Equity funding','https://equity.wa.gov/resources/funding-opportunities','State funding links and resources'),
      ('FundHubWA','https://fundhub.wa.gov/funding-opportunities/','Mostly climate and clean-energy focus; not a general arts grant directory'),
      ('4Culture','https://www.4culture.org/grants/','King County arts, heritage, preservation'),
      ('Seattle Arts & Culture','https://www.seattle.gov/arts/opportunities','Seattle municipal arts funding'),
      ('Bellevue Arts','https://bellevuewa.gov/city-government/departments/community-development/arts-and-culture','Bellevue funding announcements'),
      ('Redmond Arts','https://www.redmond.gov/','Redmond city funding — navigate to cultural arts'),
      ('Issaquah','https://www.issaquahwa.gov/','Issaquah arts grants'),
      ('Kirkland','https://www.kirklandwa.gov/','Kirkland cultural funding'),
      ('IRS tax-exempt organization search','https://www.irs.gov/charities-non-profits/tax-exempt-organization-search','Foundation grant history and returns')]:
        st.markdown(f'**[{name}]({url})** — {why}')
    st.write('Scoring: up to 40 points for keyword match across ARCS programs, 25 for availability, 18 for local proximity and 12 for official sourcing. It is not a grant approval probability. Exact normalized funder+title matches are merged, fuzzy matches are flagged only.')
    st.write('A funder listing, a historical award, and an open call are different evidence types. Imported records are not independently verified.')
