import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from feature_extractor import DOMAIN_LEXICAL_SCHEMA_VERSION as V7, DOMAIN_ENRICHED_SCHEMA_VERSION as V8, QUERY_ROBUST_SCHEMA_VERSION as V5, extract_features, feature_names, feature_vector


class DomainLexicalTests(unittest.TestCase):
    def test_enriched_prefix_is_exactly_old_schema(self):
        for url in ['https://web.facebook.com/','https://facebook.com.evil.example/login?password=&redirect=https://elsewhere.example',
                    'https://web.пример.рф/author','https://www.google.com/search?q=example&token=secret']:
            self.assertEqual(feature_vector(url,V8)[:32],feature_vector(url,V5))
    def test_parent_domain_identity_without_erasing_subdomain_evidence(self):
        a=extract_features('https://www.facebook.com/',V7)
        b=extract_features('https://web.facebook.com/',V7)
        fake=extract_features('https://web.facebook.com.example.net/',V7)
        keys=[k for k in feature_names(V7) if k.startswith('domain_ngram_')]
        self.assertEqual([a[k] for k in keys],[b[k] for k in keys])
        self.assertNotEqual([a[k] for k in keys],[fake[k] for k in keys])
        self.assertLess(a['subdomain_label_count'],b['subdomain_label_count'])
        self.assertEqual(len(feature_vector('https://example.com/',V5)),32)

    def test_query_signals_retained_and_idna_subdomain_correct(self):
        a=extract_features('https://web.пример.рф/',V7)
        b=extract_features('https://web.xn--e1afmkfd.xn--p1ai/',V7)
        for key in ['subdomain_max_label_length','subdomain_label_count','registered_domain_length']:
            self.assertEqual(a[key],b[key])
        clean=extract_features('https://example.com/?utm_campaign=test',V7)
        query=extract_features('https://example.com/?password=&redirect=https://other.example',V7)
        self.assertEqual(query['credential_parameter_count'],1)
        self.assertEqual(query['redirect_parameter_count'],1)
        self.assertEqual(clean['structural_path_url_length'],query['structural_path_url_length'])


if __name__=='__main__': unittest.main()
