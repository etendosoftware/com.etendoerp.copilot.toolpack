import unittest
from typing import Dict
from unittest.mock import patch
import pytest

from tools.TavilySearchTool import TavilySearchTool

class TestTavilySearchTool(unittest.TestCase):
    def setUp(self):
        self.tool = TavilySearchTool()
    @pytest.fixture(autouse=True)
    def set_env(self, monkeypatch):
        monkeypatch.setenv('TAVILY_API_KEY', 'test_key')

    @patch('tools.TavilySearchTool.TavilySearchResults.invoke')
    def test_search_success(self, mock_invoke):
        mock_invoke.return_value = {"results": ["result1", "result2"]}

        query : Dict = {"query": "test query"}
        expected_output = {"results": ["result1", "result2"]}
        output = self.tool.run(query)
        self.assertEqual(expected_output, output)

    @patch('tools.TavilySearchTool.TavilySearchResults.invoke')
    def test_search_failure(self, mock_invoke ):

        mock_invoke.return_value = {"error": "Failed to fetch data from Tavily"}

        query:Dict = {"query": "test query"}
        expected_output = {"error": "Failed to fetch data from Tavily"}

        output = self.tool.run(query)
        self.assertEqual(expected_output, output)

if __name__ == '__main__':
    unittest.main()