import importlib.util
import sys
import unittest
from unittest.mock import patch
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from feature_extractor import feature_names,feature_vector,REFERENCE_ORIGIN_SCHEMA_VERSION as V9,REFERENCE_ROOT_SCHEMA_VERSION as V10
from reference_origin_features import reference_origin_match,registry


class ReferenceOriginTests(unittest.TestCase):
    def test_root_context_is_narrow_and_preserves_earlier_features(self):
        for url in ['https://web.facebook.com/?locale=th_TH&_rdc=1&_rdr#','https://gemini.google.com/?hl=th']:
            self.assertEqual(feature_vector(url,V10)[-1],1.)
            self.assertEqual(feature_vector(url,V10)[:-1],feature_vector(url,V9))
        for url in ['https://gemini.google.com/share/abc','https://gemini.google.com/?url=https://evil.example/',
                    'https://web.facebook.com/?password=x','https://gemini.google.com/?access_token=x',
                    'https://gemini.google.com.evil.example/']:
            self.assertEqual(feature_vector(url,V10)[-1],0.,url)
    def test_loader_rejects_a_model_with_different_reference_metadata(self):
        import app
        bundle={'model':object(),'feature_schema_version':V9,'reference_origin_registry_sha256':'different-metadata'}
        with patch.object(app.joblib,'load',return_value=bundle):
            with self.assertRaisesRegex(ValueError,'metadata changed'):
                app._load_model_bundle.__wrapped__(0)
        bundle['reference_origin_registry_sha256']=registry()[1]
        with patch.object(app.joblib,'load',return_value=bundle):
            self.assertIs(app._load_model_bundle.__wrapped__(0),bundle)

    def test_origin_boundary_and_protocol(self):
        self.assertEqual(reference_origin_match('https://gemini.google.com/?hl=th'),1.)
        for url in ['https://gemini.google.com.evil.example/','https://gemini-google.com/',
                    'https://gemini.google.com@evil.example/','http://gemini.google.com/',
                    'https://gemini.google.com:444/','https://unlisted.google.com/']:
            self.assertEqual(reference_origin_match(url),0.,url)
        self.assertEqual(reference_origin_match('https://GEMINI.GOOGLE.COM.:443/'),1.)

    def test_metadata_does_not_discard_dangerous_query_features(self):
        benign=feature_vector('https://gemini.google.com/?hl=th',V9)
        redirect=feature_vector('https://gemini.google.com/?url=https%3A%2F%2Fevil.example%2Flogin&password=x',V9)
        names=feature_names(V9)
        self.assertEqual(benign[-1],1.)
        self.assertEqual(redirect[-1],1.)
        self.assertGreater(redirect[names.index('has_nested_url')],benign[names.index('has_nested_url')])
        self.assertGreater(redirect[names.index('credential_parameter_count')],benign[names.index('credential_parameter_count')])

    def test_earlier_schemas_are_exactly_unchanged(self):
        spec=importlib.util.spec_from_file_location('old_feature_extractor',ROOT/'output/before-reference-origin-20261008/feature_extractor.py')
        old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
        urls=['https://web.facebook.com/','https://gemini.google.com/?hl=th',
              'https://example.com/login?url=https://elsewhere.example/&otp=123',
              'https://例え.テスト/買物?q=情報','http://127.0.0.1:8080/a.zip']
        for schema in ['url-v3-www-canonical','url-v4-public-suffix','url-v5-query-structural',
                       'url-v6-host-context','url-v7-domain-lexical','url-v8-domain-enriched']:
            self.assertEqual(feature_names(schema),old.feature_names(schema))
            for url in urls:
                self.assertEqual(feature_vector(url,schema),old.feature_vector(url,schema))
                if schema=='url-v8-domain-enriched':self.assertEqual(feature_vector(url,V9)[:-1],feature_vector(url,schema))


if __name__=='__main__':unittest.main()
