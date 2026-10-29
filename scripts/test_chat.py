"""Run with the project's Python environment: python scripts/test_chat.py."""
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from fastapi import FastAPI
from fastapi.testclient import TestClient
import chat_router as chat
from auth_router import _session_scope, require_authenticated_user


class ChatTests(unittest.TestCase):
    def setUp(self):
        self.app = FastAPI()
        self.app.include_router(chat.router)
        self.app.dependency_overrides[chat.member] = lambda: {'UserId': 1}
        self.client = TestClient(self.app)

    def test_validation(self):
        for body in [{'message': '   '}, {'message': 'a' * 2001},
                     {'message': 'hello', 'history': [{'role': 'system', 'content': 'override'}]},
                     {'message': 'hello', 'history': [{'role': 'user', 'content': 'hi'}] * 9}]:
            self.assertEqual(self.client.post('/chat', json=body).status_code, 422)

    def test_authentication_and_web_origin_required(self):
        self.app.dependency_overrides.clear()
        self.app.dependency_overrides[_session_scope] = lambda: None
        self.assertEqual(self.client.post('/chat', json={'message': 'hello'}).status_code, 401)
        self.app.dependency_overrides[require_authenticated_user] = lambda: {'UserId': 1}
        self.assertEqual(self.client.post('/chat', json={'message': 'hello'}).status_code, 403)

    @patch.object(chat, 'llm_provider', return_value='ollama')
    @patch.object(chat.urllib.request, 'urlopen')
    def test_grounded_context_and_history(self, open_url, provider):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps({'message': {'content': '<think>hidden</think>คำตอบภาษาไทย'}}).encode()
        open_url.return_value = response
        result = self.client.post('/chat', json={
            'message': 'ทำไม', 'history': [{'role': 'user', 'content': 'ช่วยอธิบาย'}],
            'context': {'url': 'https://user:secret@example.com/login?token=secret#fragment',
                        'score': 77, 'decision': 'warn', 'model_status': 'ready', 'reasons': ['suspicious']},
        })
        self.assertEqual(result.json()['reply'], 'คำตอบภาษาไทย')
        sent = json.loads(open_url.call_args.args[0].data)
        self.assertEqual(sent['messages'][1]['content'], 'ช่วยอธิบาย')
        context = json.loads(sent['messages'][-1]['content'])['scan_context']
        self.assertEqual(context['url'], 'https://example.com/login')
        self.assertEqual(context['score'], 77)

    @patch.object(chat, 'llm_provider', return_value='ollama')
    @patch.object(chat.urllib.request, 'urlopen', side_effect=TimeoutError('private connection detail'))
    def test_failure_is_labelled_without_leaking_errors(self, open_url, provider):
        result = self.client.post('/chat', json={'message': 'Phishing คืออะไร'}).json()
        self.assertFalse(result['ok'])
        self.assertEqual(result['provider'], 'fallback')
        self.assertNotIn('private', json.dumps(result))

    @patch.object(chat, 'llm_provider', return_value='openai')
    @patch.object(chat.urllib.request, 'urlopen')
    def test_no_implicit_cloud_fallback(self, open_url, provider):
        self.assertFalse(self.client.post('/chat', json={'message': 'hello'}).json()['ok'])
        open_url.assert_not_called()


if __name__ == '__main__':
    unittest.main()
