import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from feature_extractor import extract_features, feature_vector, feature_names, QUERY_ROBUST_SCHEMA_VERSION, FEATURE_SCHEMA_VERSION


class QueryFeatureTests(unittest.TestCase):
    def test_regular_queries_do_not_change_structural_vector(self):
        for base in ['https://www.google.com/search', 'https://www.youtube.com/watch', 'https://www.nike.com/th/men']:
            self.assertEqual(feature_vector(base, QUERY_ROBUST_SCHEMA_VERSION),
                             feature_vector(base + '?q=login&v=aQT2HyfmVbk&tracking=' + 'A9_'*200, QUERY_ROBUST_SCHEMA_VERSION))
        self.assertNotEqual(feature_vector('https://www.youtube.com/watch', FEATURE_SCHEMA_VERSION),
                            feature_vector('https://www.youtube.com/watch?v=aQT2HyfmVbk', FEATURE_SCHEMA_VERSION))

    def test_redirects_credentials_and_encoded_urls_remain_observable(self):
        f = extract_features('https://example.com/?redirect=https%3A%2F%2Fevil.example&password=secret', QUERY_ROBUST_SCHEMA_VERSION)
        self.assertEqual(f['redirect_parameter_count'], 1)
        self.assertEqual(f['credential_parameter_count'], 1)
        self.assertEqual(f['has_nested_url'], 1)
        self.assertEqual(f['has_encoded_url'], 1)
        self.assertEqual(len(feature_vector('https://example.com/', QUERY_ROBUST_SCHEMA_VERSION)), len(feature_names(QUERY_ROBUST_SCHEMA_VERSION)))

    def test_lookalikes_still_have_different_host_features(self):
        self.assertNotEqual(feature_vector('https://www.google.com/search?q=x', QUERY_ROBUST_SCHEMA_VERSION),
                            feature_vector('https://google.com.evil.example/search?q=x', QUERY_ROBUST_SCHEMA_VERSION))


if __name__ == '__main__':
    unittest.main()
