import io
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from baseline_feature_forest import BaselineFeatureForest


class BaselineFeatureForestTests(unittest.TestCase):
    def test_runtime_teacher_feature_matches_training_and_serializes(self):
        rng=np.random.RandomState(42);x=rng.normal(size=(200,3));y=(x[:,0]+x[:,1]>.1).astype(int)
        teacher=RandomForestClassifier(n_estimators=5,random_state=42).fit(x[:,:2],y)
        raw=teacher.predict_proba(x.astype(np.float32)[:,:2])[:,1]
        enriched=np.column_stack((x,raw)).astype(np.float32)
        forest=RandomForestClassifier(n_estimators=5,random_state=43).fit(enriched,y)
        model=BaselineFeatureForest(teacher,forest,3,baseline_width=2)
        np.testing.assert_array_equal(model.predict_proba(x),forest.predict_proba(enriched))
        buffer=io.BytesIO();joblib.dump(model,buffer);buffer.seek(0)
        np.testing.assert_array_equal(joblib.load(buffer).predict_proba(x),model.predict_proba(x))
        with self.assertRaises(ValueError):model.predict_proba(x[:,:2])


if __name__=='__main__':unittest.main()
