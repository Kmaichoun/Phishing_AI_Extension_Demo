import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from feature_extractor import extract_features, feature_vector, feature_names, HOST_CONTEXT_SCHEMA_VERSION as V6, QUERY_ROBUST_SCHEMA_VERSION as V5


class HostContextTests(unittest.TestCase):
    def test_root_context_shared_but_subdomain_evidence_retained(self):
        root = extract_features('https://facebook.com/', V6)
        web = extract_features('https://web.facebook.com/', V6)
        for key in ('registered_domain_length', 'registered_domain_entropy', 'structural_path_url_length'):
            self.assertEqual(root[key], web[key])
        self.assertEqual(web['subdomain_label_count'], 1)
        self.assertGreater(web['subdomain_max_label_length'], root['subdomain_max_label_length'])
        fake = extract_features('https://login.facebook.com.evil-provider.example/', V6)
        self.assertNotEqual(root['registered_domain_length'], fake['registered_domain_length'])
        self.assertGreater(fake['subdomain_suspicious_word_count'], 0)

    def test_query_tracking_invariance_and_empty_credentials(self):
        base = 'https://web.example.com/author/shopping'
        self.assertEqual(feature_vector(base, V6), feature_vector(base + '?q=login&track=' + 'Ab9_' * 200, V6))
        f = extract_features(base + '?password=&redirect=', V6)
        self.assertEqual(f['credential_parameter_count'], 1)
        self.assertEqual(f['redirect_parameter_count'], 1)
        self.assertEqual(f['suspicious_word_count'], 0)

    def test_versioned_vector_dimensions(self):
        self.assertEqual(len(feature_names(V6)), len(feature_vector('https://example.com/', V6)))
        self.assertEqual(len(feature_vector('https://example.com/', V5)), 32)
        self.assertEqual(feature_vector('https://www.example.com/', V6), feature_vector('https://example.com/', V6))


if __name__ == '__main__':
    unittest.main()
