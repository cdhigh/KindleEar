import builtins
import logging
import unittest
from unittest.mock import Mock, patch

with patch.object(builtins, 'default_log', logging.getLogger(__name__), create=True):
    from simple_ai_provider import SimpleAiProvider


class ApiRouteTest(unittest.TestCase):
    def setUp(self):
        self.provider = SimpleAiProvider('api-route', apiKey='test-key')
        self.provider.opener = Mock()
        self.provider.opener.post.return_value.json.return_value = {'choices': [{'message': {'content': 'Summary'}}]}

    def test_chat_uses_compatible_endpoint_and_auth(self):
        response = self.provider.opener.post.return_value
        response.json.return_value = {'choices': [{'message': {'content': 'Summary'}}]}
        self.assertEqual(self.provider.chat('Summarize this'), 'Summary')
        self.provider.opener.post.assert_called_once_with(
            'https://global.api-route.com/v1/chat/completions',
            headers={'Authorization': 'Bearer test-key', 'Content-Type': 'application/json'},
            json={'model': 'gpt-6.1-sol', 'messages': [{'role': 'user', 'content': 'Summarize this'}]})
        response.raise_for_status.assert_called_once()

    def test_models_are_discovered(self):
        self.provider.opener.get.return_value.json.return_value = {'data': [{'id': 'account-model'}]}
        self.assertEqual(self.provider.models(), ['account-model'])
        self.assertEqual(self.provider.opener.get.call_args.args[0],
                         'https://global.api-route.com/v1/models')

    def test_custom_model_and_host_are_preserved(self):
        provider = SimpleAiProvider('api-route', apiKey='test-key', model='account-model',
                                    apiHost='https://proxy.example')
        provider.opener = self.provider.opener
        provider.chat([{'role': 'user', 'content': 'Hello'}])
        self.assertEqual(provider.model, 'account-model')
        self.assertEqual(provider.opener.post.call_args.args[0],
                         'https://proxy.example/v1/chat/completions')

    def test_http_error_is_not_swallowed(self):
        self.provider.opener.get.return_value.raise_for_status.side_effect = RuntimeError('401')
        with self.assertRaisesRegex(RuntimeError, '401'):
            self.provider.models()


if __name__ == '__main__':
    unittest.main()
