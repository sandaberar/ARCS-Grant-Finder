"""Conservative, auditable extraction from a single grant opportunity page.
Never synthesize open status or applicant eligibility from loose keyword matches.
"""
import re
from datetime import date
from bs4 import BeautifulSoup
from dateutil import parser

MONTH = r'(?:January|February|March|April|June|July|August|September|October|November|December|Jan\.?|Feb\.?|Mar\.?|Apr\.?|Jun\.?|Jul\.?|Aug\.?|Sep\.?|Sept\.?|Oct\.?|Nov\.?|Dec\.?)'
DATE = re.compile(rf'\b({MONTH}\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s+20\d{{2}}|20\d{{2}}-\d{{2}}-\d{{2}})\b',re.I)
DEADLINE = re.compile(r'\b(?:application\s+deadline|deadline\s+(?:to\s+apply|for\s+applications)|applications?\s+(?:due|close|must\s+be\s+received)|apply\s+by|submissions?\s+due|due\s+date|closing\s+date)\b',re.I)
ELIGIBLE = re.compile(r'\b(?:who\s+(?:can|may)\s+apply|eligib(?:le|ility)|applicants?\s+must|organizations?\s+must|nonprofits?\s+(?:must|may|can)|open\s+to\s+applications?\s+from)\b',re.I)


def compact(value):return ' '.join(value.split())

def extract(page_html_or_soup, checked_on=None):
    soup=BeautifulSoup(page_html_or_soup,'html.parser') if isinstance(page_html_or_soup,str) else page_html_or_soup
    for el in soup.select('script,style,nav,footer,header,aside'):el.decompose()
    # Context derived from small page blocks to avoid joining unrelated dates from a directory.
    blocks=[]
    for node in soup.select('p,li,td,h2,h3,h4'):
        s=compact(node.get_text(' ',strip=True))
        if 15<=len(s)<=900 and s not in blocks:blocks.append(s)
    deadlines=[];eligibility=[]
    for block in blocks:
        if DEADLINE.search(block):
            match=DATE.search(block)
            if match:
                try:
                    d=parser.parse(re.sub(r'(\d)(st|nd|rd|th)\b',r'\1',match.group(1),flags=re.I)).date()
                    deadlines.append((d.isoformat(),block[:350]))
                except (ValueError,OverflowError):pass
        if ELIGIBLE.search(block):eligibility.append(block[:350])
    unique_dates={d for d,_ in deadlines}
    # Trust a deadline ONLY if there is exactly one explicit deadline date in relevant blocks.
    deadline,proof=('','') if len(unique_dates)!=1 else deadlines[0]
    today=checked_on or date.today()
    status='Closed (date passed)' if deadline and date.fromisoformat(deadline)<today else 'Needs verification'
    return {'Deadline':deadline,'Deadline evidence':proof,'Status':status,
            'Eligibility evidence':' | '.join(eligibility[:3]),
            'Verification':'Explicit deadline in page text' if deadline else 'No unambiguous deadline extracted'}
