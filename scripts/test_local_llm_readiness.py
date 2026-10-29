import io
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import llm_explainer


class LocalReadinessTests(unittest.TestCase):
    def test_server_without_configured_model_is_not_ready(self):
        with patch.dict(os.environ, {'LLM_PROVIDER':'ollama', 'OLLAMA_MODEL':'qwen3:0.6b'}):
            with patch.object(llm_explainer.urllib.request, 'urlopen', return_value=io.BytesIO(json.dumps({'models':[{'name':'other:latest'}]}).encode())):
                status = llm_explainer.llm_status()
            self.assertFalse(status['llm_ready'])
            self.assertEqual(status['readiness_reason'], 'configured_model_not_installed')

    def test_installed_model_and_unavailable_service(self):
        with patch.dict(os.environ, {'LLM_PROVIDER':'ollama', 'OLLAMA_MODEL':'qwen3:0.6b'}):
            with patch.object(llm_explainer.urllib.request, 'urlopen', return_value=io.BytesIO(json.dumps({'models':[{'name':'qwen3:0.6b'}]}).encode())):
                self.assertTrue(llm_explainer.llm_status()['llm_ready'])
            with patch.object(llm_explainer.urllib.request, 'urlopen', side_effect=OSError('offline')):
                self.assertEqual(llm_explainer.llm_status()['readiness_reason'], 'ollama_service_unavailable')


if __name__ == '__main__':
    unittest.main()
