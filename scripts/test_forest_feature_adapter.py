import io
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from forest_feature_adapter import extend_forest


class ForestFeatureAdapterTests(unittest.TestCase):
    def test_preserves_old_predictions_and_original_artifact(self):
        rng=np.random.RandomState(42)
        x=rng.normal(size=(200,3)); y=(x[:,0]+x[:,1]>.2).astype(int)
        forest=RandomForestClassifier(n_estimators=7,random_state=42).fit(x,y)
        original=forest.predict_proba(x)
        extended=extend_forest(forest,['a','b','c'],['a','b','c','new'])
        wide=np.column_stack((x,rng.normal(size=200)))
        np.testing.assert_array_equal(extended.predict_proba(wide),original)
        np.testing.assert_array_equal(forest.predict_proba(x),original)
        self.assertEqual(forest.n_features_in_,3)
        buffer=io.BytesIO(); joblib.dump(extended,buffer);buffer.seek(0)
        np.testing.assert_array_equal(joblib.load(buffer).predict_proba(wide),original)

    def test_rejects_reordered_original_features(self):
        forest=RandomForestClassifier(n_estimators=2,random_state=42).fit([[0,1],[1,0]],[0,1])
        with self.assertRaises(ValueError): extend_forest(forest,['a','b'],['b','a','new'])


if __name__=='__main__':unittest.main()
