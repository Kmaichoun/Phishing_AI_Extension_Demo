import io
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import joblib
import numpy as np
from probability_calibration import IsotonicProbabilityCalibrator, BetaProbabilityCalibrator, BrierSigmoidCalibrator, ValidationConstrainedSigmoidCalibrator


class CalibrationTests(unittest.TestCase):
    def test_constrained_sigmoid_respects_operating_bounds_and_serializes(self):
        raw=np.linspace(0,1,30).reshape(-1,1)
        y=(raw[:,0]>.45).astype(int)
        calibrator=ValidationConstrainedSigmoidCalibrator((.45,.50),(.60,.66)).fit(raw,y)
        p=calibrator.predict_proba([[.45],[.50],[.60],[.66]])[:,1]
        self.assertLess(p[0],.6);self.assertGreater(p[1],.6)
        self.assertLess(p[2],.8);self.assertGreater(p[3],.8)
        buffer=io.BytesIO();joblib.dump(calibrator,buffer);buffer.seek(0)
        np.testing.assert_allclose(joblib.load(buffer).predict_proba(raw),calibrator.predict_proba(raw))
    def test_monotonic_valid_probabilities_and_serialization(self):
        x = np.arange(12, dtype=float).reshape(-1, 1) / 11
        y = [0, 0, 1, 0, 0, 1, 0, 1, 1, 1, 0, 1]
        for method in (IsotonicProbabilityCalibrator, BetaProbabilityCalibrator, BrierSigmoidCalibrator):
            with self.subTest(method=method):
                calibrator = method().fit(x, y)
                test = np.linspace(-.1, 1.1, 31).reshape(-1, 1)
                result = calibrator.predict_proba(test)
                self.assertTrue(np.all((result >= 0) & (result <= 1)))
                np.testing.assert_allclose(result.sum(axis=1), 1)
                self.assertTrue(np.all(np.diff(result[:, 1]) >= 0))
                buffer = io.BytesIO(); joblib.dump(calibrator, buffer); buffer.seek(0)
                np.testing.assert_allclose(joblib.load(buffer).predict_proba(test), result)

    def test_rejects_missing_class_and_multiple_features(self):
        with self.assertRaises(ValueError):
            IsotonicProbabilityCalibrator().fit([[.1], [.2]], [0, 0])
        with self.assertRaises(ValueError):
            IsotonicProbabilityCalibrator().fit([[.1, .2], [.5, .7]], [0, 1])


if __name__ == '__main__': unittest.main()
