from datetime import date
from bs4 import BeautifulSoup
from verification import extract
from foundations import csv_link,scan_grants

def test_explicit_deadline():
    s='<p>Applications close on March 10, 2027 at 5 PM.</p><p>Eligible applicants must be nonprofit organizations operating in King County.</p>'
    r=extract(s,date(2026,11,2))
    assert r['Deadline']=='2027-03-10'
    assert 'nonprofit' in r['Eligibility evidence']
    assert r['Status']=='Needs verification'

def test_ambiguous_deadlines_not_guessed():
    s='<p>Applications close on March 10, 2027.</p><p>Applications close on April 20, 2027.</p>'
    assert extract(s)['Deadline']==''

def test_foundation_matching():
    rows=[{'F9_00_ORG_EIN':'123456789','OBJECTID':'OID-1','PF_15_G_PAID_RECIP_NAME_ORG_L1':'Mode Music','PF_15_G_PAID_RECIP_ADDR_STATE':'WA','PF_15_G_PAID_PURPOSE':'Arts education','PF_15_G_PAID_AMT':'8000'},
    {'F9_00_ORG_EIN':'234567890','OBJECTID':'OID-2','PF_15_G_PAID_RECIP_NAME_ORG_L1':'Unrelated Hospital','PF_15_G_PAID_RECIP_ADDR_STATE':'TX','PF_15_G_PAID_PURPOSE':'Hospital care','PF_15_G_PAID_AMT':'1000'}]
    r=scan_grants(rows,2025)
    assert len(r)==1 and r[0]['Amount']=='8000'

def test_catalog_link():
    soup=BeautifulSoup('<table><tr><td>PF-P15-T01-SUPPLEMENTARY-INFO-GRANT-PAID-2025</td><td><a href="https://example.org/file.CSV">CSV</a></td></tr></table>','html.parser')
    assert csv_link(soup,'PF-P15-T01-SUPPLEMENTARY-INFO-GRANT-PAID',2025)=='https://example.org/file.CSV'
