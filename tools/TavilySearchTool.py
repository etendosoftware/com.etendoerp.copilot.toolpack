from copilot.core.tool_wrapper import ToolWrapper
from langchain_core.pydantic_v1 import Field, BaseModel
from typing import Type, Dict
import os
from langchain_community.tools.tavily_search import TavilySearchResults

class TavilySearchInput(BaseModel):
    query: str = Field(description="Query to search in internet for.")

class TavilySearchTool(ToolWrapper):
    """A tool to perform searches in Tavily.
    Tavily is a search engine that allows you to search the internet for information.
    This tool will return the search results for the given query.
    Example of input: { "query": "What is the capital of Spain?" }
    """

    name = "TavilySearchTool"
    description = "Tool to perform searches in Tavily. Tavily is a search engine that allows you to search the internet for information. This tool will return the search results for the given query"
    args_schema: Type[BaseModel] = TavilySearchInput
    return_direct: bool = False

    def __init__(self):
        super().__init__()

    def run(self, input_params: Dict, *args, **kwargs) -> dict:
        query = input_params.get("query")
        os.environ["TAVILY_API_KEY"] = os.getenv("TAVILY_API_KEY", "")
        tool = TavilySearchResults()
        return tool.invoke({"query": query})