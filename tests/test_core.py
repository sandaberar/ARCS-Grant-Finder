import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pandas as pd
from core import normalize,deduplicate,effective_status,score,infer_import_columns
from datetime import date
class TestCore(unittest.TestCase):
    def test_duplicate(self):
        a=normalize(pd.DataFrame([{'Funder':'City of Seattle','Opportunity':'2027 Art Grants','Notes':'old','Verified_on':'2026-01-01'},{'Funder':'City of Seattle','Opportunity':'Art Grants','Notes':'new','Verified_on':'2026-02-01'}]))
        b,cl=deduplicate(a);self.assertEqual(len(b),1);self.assertEqual(len(cl),1);self.assertEqual(b.iloc[0]['Notes'],'new')
    def test_deadline(self):
        self.assertEqual(effective_status({'Status':'Open','Deadline':'2020-01-01'},date(2026,11,2)),'Past deadline — recheck')
    def test_import(self):
        a=infer_import_columns(pd.DataFrame([{'Title':'Arts Fund','Agency':'ArtsWA','Close Date':'2027-05-01'}]),'Washington State')
        self.assertEqual(a.iloc[0]['Category'],'Washington State');self.assertEqual(a.iloc[0]['Verification'],'Imported — unverified')
    def test_scoring(self):
        self.assertGreater(score({'Category':'City Grants','Opportunity':'Cultural arts exhibition','Status':'Open','Verification':'Official listing','Deadline':''}),score({'Category':'Federal Grants','Opportunity':'Infrastructure drainage','Status':'Closed','Verification':'Imported — unverified','Deadline':''}))
if __name__=='__main__':unittest.main()
