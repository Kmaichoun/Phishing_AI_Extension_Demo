"""Prevent silent label inversion and removal of phishing URL evidence."""
import unittest
from collect_quality_url_data import canonical, mapped_label
from train_quality_rf_candidate import no_regression
from diagnose_quality_calibration import separated_intervals


class QualityDataTests(unittest.TestCase):
    def test_publisher_label_mapping(self):
        self.assertEqual(mapped_label('1'), '0')
        self.assertEqual(mapped_label('0'), '1')
        with self.assertRaises(ValueError): mapped_label('benign')

    def test_url_identity_preserves_userinfo_query_and_fragment(self):
        self.assertEqual(canonical('https://user@Example.COM:443/?next=x#token'),
                         'https://user@example.com/?next=x#token')
        self.assertNotEqual(canonical('http://example.com/'), canonical('https://example.com/'))
        self.assertNotEqual(canonical('https://web.example.com/'), canonical('https://www.example.com/'))
        self.assertEqual(canonical('https://[::1]:443/'), 'https://[::1]/')

    def test_recall_loss_cannot_be_hidden_by_fewer_false_positives(self):
        old = {k:{'false_positive':10,'false_negative':20} for k in ('warning','blocking')}
        fewer_fp_more_misses = {k:{'false_positive':1,'false_negative':21} for k in ('warning','blocking')}
        self.assertFalse(no_regression(fewer_fp_more_misses,old))
        self.assertTrue(no_regression(old,old))

    def test_overlapping_feasible_operating_intervals(self):
        intervals=separated_intervals(.4,.7,.6,.8)
        self.assertIsNotNone(intervals)
        w,b=intervals
        self.assertTrue(.4==w[0]<w[1]<b[0]<b[1]==.8)
        self.assertIsNone(separated_intervals(.7,.6,.8,.9))


if __name__ == '__main__': unittest.main()
