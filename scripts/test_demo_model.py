import hashlib
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from demo_model import authorized_demo


class DemoAuthorizationTests(unittest.TestCase):
    def test_loader_rejects_draft_and_revoked_authorization(self):
        import app
        import joblib
        with tempfile.TemporaryDirectory() as directory:
            model = Path(directory) / 'model.pkl'
            authorization = Path(directory) / 'authorization.json'
            joblib.dump({'production_ready': False, 'model': 'test fixture'}, model)
            with patch.object(app, 'MODEL_PATH', model), patch.object(app, 'DEMO_AUTHORIZATION_PATH', authorization):
                app._load_model_bundle.cache_clear()
                with self.assertRaises(ValueError):
                    app.load_model_bundle()
                authorization.write_text(json.dumps({'mode': 'user_requested_web_test',
                    'model_sha256': hashlib.sha256(model.read_bytes()).hexdigest()}))
                self.assertEqual(app.load_model_bundle()['deployment_mode'], 'experimental_demo')
                self.assertIs(app.load_model_bundle()['production_ready'], False)
                authorization.unlink()
                with self.assertRaises(ValueError):
                    app.load_model_bundle()
            app._load_model_bundle.cache_clear()

    def test_only_explicit_exact_artifact_is_allowed(self):
        with tempfile.TemporaryDirectory() as directory:
            model = Path(directory) / 'model.pkl'
            authorization = Path(directory) / 'authorization.json'
            model.write_bytes(b'round-one-research-artifact')
            self.assertFalse(authorized_demo(model, authorization))
            record = {'mode': 'user_requested_web_test',
                      'model_sha256': hashlib.sha256(model.read_bytes()).hexdigest()}
            authorization.write_text(json.dumps(record))
            self.assertTrue(authorized_demo(model, authorization))
            model.write_bytes(b'another-candidate')
            self.assertFalse(authorized_demo(model, authorization))
            record['model_sha256'] = hashlib.sha256(model.read_bytes()).hexdigest()
            record['mode'] = 'production'
            authorization.write_text(json.dumps(record))
            self.assertFalse(authorized_demo(model, authorization))
            authorization.write_text('broken json')
            self.assertFalse(authorized_demo(model, authorization))


if __name__ == '__main__':
    unittest.main()
