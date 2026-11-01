import builtins
import logging
import unittest
from unittest.mock import Mock, patch

with patch.object(builtins, 'default_log', logging.getLogger(__name__), create=True):
    from simple_ai_provider import SimpleAiProvider


class RuncrateTest(unittest.TestCase):
    def setUp(self):
        self.provider = SimpleAiProvider('runcrate', apiKey='test-key')
        self.provider.opener = Mock()
        self.provider.opener.post.return_value.json.return_value = {'choices': [{'message': {'content': 'Summary'}}]}

    def test_chat_uses_compatible_endpoint_and_auth(self):
        response = self.provider.opener.post.return_value
        self.assertEqual(self.provider.chat('Summarize this'), 'Summary')
        self.provider.opener.post.assert_called_once_with(
            'https://api.runcrate.ai/v1/chat/completions',
            headers={'Authorization': 'Bearer test-key', 'Content-Type': 'application/json'},
            json={'model': 'deepseek-ai/DeepSeek-V4.1-Flash', 'messages': [{'role': 'user', 'content': 'Summarize this'}]})
        response.raise_for_status.assert_called_once()

    def test_default_model_limits(self):
        self.assertEqual(self.provider.model, 'deepseek-ai/DeepSeek-V4.1-Flash')
        self.assertEqual(self.provider.rpm, 60)
        self.assertEqual(self.provider.context_size, 1000000)

    def test_listed_model_uses_its_context_size(self):
        provider = SimpleAiProvider('runcrate', apiKey='test-key', model='Qwen/Qwen3.5-397B-A17B')
        self.assertEqual(provider.model, 'Qwen/Qwen3.5-397B-A17B')
        self.assertEqual(provider.context_size, 262144)

    def test_models_are_discovered(self):
        self.provider.opener.get.return_value.json.return_value = {'data': [{'id': 'zai-org/GLM-5.3'}]}
        self.assertEqual(self.provider.models(), ['zai-org/GLM-5.3'])
        self.assertEqual(self.provider.opener.get.call_args.args[0],
                         'https://api.runcrate.ai/v1/models')

    def test_custom_host_is_preserved(self):
        provider = SimpleAiProvider('runcrate', apiKey='test-key', apiHost='https://proxy.example')
        provider.opener = self.provider.opener
        provider.chat([{'role': 'user', 'content': 'Hello'}])
        self.assertEqual(provider.opener.post.call_args.args[0],
                         'https://proxy.example/v1/chat/completions')


if __name__ == '__main__':
    unittest.main()
