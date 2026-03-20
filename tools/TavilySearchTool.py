from typing import Dict, Type

from langchain_community.tools.tavily_search import TavilySearchResults

from copilot.baseutils.logging_envvar import read_optional_env_var
from copilot.core.tool_input import ToolField, ToolInput
from copilot.core.tool_wrapper import ToolWrapper


class TavilySearchInput(ToolInput):
    query: str = ToolField(description="Query to search in internet for.")


class TavilySearchTool(ToolWrapper):
    """A tool to perform searches in Tavily.
    Tavily is a search engine that allows you to search the internet for information.
    This tool will return the search results for the given query.
    Example of input: { "query": "What is the capital of Spain?" }
    """

    name: str = "TavilySearchTool"
    description: str = (
        "Tool to perform searches in Tavily. Tavily is a search engine that allows you to search the "
        "internet for information. This tool will return the search results for the given query"
    )
    args_schema: Type[ToolInput] = TavilySearchInput
    return_direct: bool = False

    def __init__(self):
        super().__init__()

    def run(self, input_params: Dict, *args, **kwargs) -> dict:
        query = input_params.get("searchquery")

        tool = TavilySearchResults(
            tavily_api_key=read_optional_env_var("tavily.api.key", None),
            query=query,
        )
        return tool.invoke({"query": query})
