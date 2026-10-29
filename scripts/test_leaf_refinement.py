"""Refinement must preserve unmodified predictions and guard positive regions."""
import io
import sys
import unittest
from pathlib import Path
import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from forest_feature_adapter import extend_forest
from forest_leaf_refinement import learn_regions, refine_estimator


class RefinementTests(unittest.TestCase):
    def setUp(self):
        self.x = np.column_stack([np.zeros(40), np.r_[np.zeros(20), np.ones(20)]])
        self.y = np.r_[np.zeros(20, dtype=int), np.ones(20, dtype=int)]
        base = RandomForestClassifier(n_estimators=1, bootstrap=False, random_state=1).fit(self.x[:, :1], self.y)
        self.est = extend_forest(base, ['old'], ['old', 'new']).estimators_[0]

    def test_empty_refinement_is_exact_and_serializable(self):
        refined, changed = refine_estimator(self.est, [], 3, 8)
        self.assertEqual(changed, 0)
        np.testing.assert_array_equal(refined.predict_proba(self.x), self.est.predict_proba(self.x))
        buf = io.BytesIO(); joblib.dump(refined, buf); buf.seek(0)
        np.testing.assert_array_equal(joblib.load(buf).predict_proba(self.x), refined.predict_proba(self.x))

    def test_learned_split_lowers_benign_only(self):
        regions = learn_regions(self.est, self.x, self.y, self.y == 0,
                                self.x[20:], self.y[20:], 1)
        refined, changed = refine_estimator(self.est, regions, 3, 8)
        self.assertGreater(changed, 0)
        self.assertLess(refined.predict_proba(self.x[:20])[:, 1].max(), .1)
        np.testing.assert_array_equal(refined.predict_proba(self.x[20:]), self.est.predict_proba(self.x[20:]))

    def test_guard_phishing_prevents_benign_override(self):
        regions = learn_regions(self.est, self.x, self.y, self.y == 0,
                                self.x[:1], np.ones(1, dtype=int), 1)
        refined, changed = refine_estimator(self.est, regions, 3, 8)
        self.assertEqual(changed, 0)
        np.testing.assert_array_equal(refined.predict_proba(self.x), self.est.predict_proba(self.x))

    def test_single_feature_remapping_preserves_every_outside_context_prediction(self):
        x=self.x.copy(); x[:,1]=1-x[:,1]
        regions=learn_regions(self.est,x,self.y,self.y==0,x[20:],self.y[20:],1,columns=[1])
        refined,changed=refine_estimator(self.est,regions,1,8,required_feature=1)
        self.assertGreater(changed,0)
        np.testing.assert_array_equal(refined.predict_proba(x[20:]),self.est.predict_proba(x[20:]))
        self.assertLess(refined.predict_proba(x[:20])[:,1].max(),.1)


if __name__ == '__main__': unittest.main()
