from typing import Dict, Optional, Type

from copilot.core.tool_input import ToolField, ToolInput
from copilot.core.tool_wrapper import ToolOutput, ToolWrapper
from core.toolgen.api_tool_util import token_not_none
from core.toolgen.openapi_tool_gen import replace_base64_filepaths
from baseutils.logging_envvar import copilot_debug


class APICallToolInput(ToolInput):
    url: str = ToolField(title="URL", description="The url of the API. Is mandatory.")
    endpoint: str = ToolField(
        title="Endpoint", description="The endpoint of the API. Is mandatory."
    )
    method: str = ToolField(
        title="Method",
        description="The method of the API (GET, POST or PUT only supported). if not "
        "defined, it will be inferred from the endpoint.  Is mandatory.",
        enum=["GET", "POST", "PUT"],
    )
    body_params: Optional[str] = ToolField(
        title="Body Params",
        description="The body of the API (only for POST method). Is mandatory.",
    )
    query_params: Optional[str] = ToolField(
        title="Query Params",
        description="The query params of the API in json format. Is mandatory.",
    )
    token: Optional[str] = ToolField(
        title="Token", description="The bearer token of the API. Is mandatory. "
    )


def do_request(body_params, endpoint: str, method: str, url, token=None):
    """
    This function performs an HTTP request based on the provided parameters.

    Parameters:
    body_params (str): The body parameters for the API request.
    endpoint (str): The API endpoint as a string.
    headers (dict): The headers to be included in the API request.
    method (str): The HTTP method to be used (GET, POST, PUT)
    url (str): The base URL of the API.

    Returns:
    str: Returns the response text if the method is GET, POST or PUT.
         If the method is not supported, it returns a string indicating that the method is not supported.
    """
    if url is None or url == "":
        return {"error": "url is required"}
    if endpoint is None or endpoint == "":
        return {"error": "endpoint is required"}
    if method is None or method == "":
        return {"error": "method is required"}
    import requests

    headers = {}
    token_not_none(headers, token)

    # if a value in the body_params, that is a dict, is string and has @BASE64_FILEPATH@,
    # it will be replaced by the content of the file in base64
    if body_params and "@BASE64" in str(body_params):
        body_params = replace_base64_filepaths(body_params)
    if method.upper() in ["GET"]:
        get_result = requests.get(url=(url + endpoint), headers=headers)
        copilot_debug("GET method")
        copilot_debug("url: " + url + endpoint)
        copilot_debug("headers: " + str(headers))
        copilot_debug("response text: " + get_result.text)
        api_response = get_result
    elif method.upper() in ["POST", "PUT"]:
        copilot_debug("POST/PUT method")
        copilot_debug("url: " + url + endpoint)
        copilot_debug("body_params: " + body_params)
        headers["Content-Type"] = "application/json"
        headers["Accept"] = "application/json"
        copilot_debug("headers: " + str(headers))
        if method.upper() == "PUT":
            post_result = requests.put(
                url=(url + endpoint), data=body_params, headers=headers
            )
        else:
            post_result = requests.post(
                url=(url + endpoint), data=body_params, headers=headers
            )
        copilot_debug("----CURL----")
        import curlify

        copilot_debug(curlify.to_curl(post_result.request))
        copilot_debug("----Response RAW----")
        copilot_debug(str(post_result.raw))
        copilot_debug("--------")
        api_response = post_result

    else:
        raise Exception(f"Method {method} not supported")
    return api_response


def get_first_param(endpoint):
    """
    This function determines the first query parameter to be used in an API endpoint.

    Parameters:
    endpoint (str): The API endpoint as a string.

    Returns:
    str: Returns '&' if the endpoint already contains a query parameter (i.e., '?'),
         otherwise returns '?' to start a new query parameter.
    """
    if "?" in endpoint:
        first_query_param = "&"
    else:
        first_query_param = "?"
    return first_query_param


def endpoint_not_none(endpoint, method):
    if (
        endpoint is not None
        and endpoint.startswith("GET")
        or endpoint.startswith("POST")
    ):
        prefix = endpoint.split(" ")[0]
        endpoint = endpoint.split(" ")[1]
        # and if the method is not defined, set it to the method in the endpoint
        copilot_debug(f"Method = '{method}'")
        if method is None or method == "":
            method = prefix
            # uppercase the method
            method = method.upper()
    return endpoint, method


class APICallTool(ToolWrapper):
    name: str = "APICallTool"
    description: str = """ This Tool, executes a call to an API, and returns the response. This tool requires the following parameters:
    - url: The url of the API (for example: https://api.example.com) (required)
    - endpoint: The endpoint of the API (for example: /endpoint) (required)
    - method: The method of the API (GET, POST and PUT only supported). If not defined, it will be inferred from the endpoint. (for example: GET) (required)
    - body_params: The body of the API (only for POST method)
    - query_params: The query params of the API in json format
    - token: The bearer token of the API (if required)
    """

    args_schema: Type[ToolInput] = APICallToolInput

    def run(self, input_params: Dict = None, *args, **kwarg) -> ToolOutput:
        url = input_params.get("url")
        endpoint = input_params.get("endpoint")
        method = input_params.get("method")
        body_params = input_params.get("body_params")
        query_params = input_params.get("query_params")
        token = input_params.get("token")

        try:
            # if url starts with the method, for example GET https://api.example.com/endpoint
            endpoint, method = endpoint_not_none(endpoint, method)

            # if query_params is not empty, add it to the endpoint
            if query_params:
                if query_params.startswith("{"):
                    import json

                    query_params = json.loads(query_params)
                else:
                    return {"error": "query_params must be a json object"}
                first_query_param = get_first_param(endpoint)
                for key, value in query_params.items():
                    # if is a boolean, convert to string
                    if isinstance(value, (bool, int, float)):
                        value = str(value)
                    if isinstance(value, list):
                        value = ",".join(value)
                    value_url_encoded = value.replace(" ", "%20")
                    endpoint += f"{first_query_param}{key}={value_url_encoded}"
                    first_query_param = "&"

            copilot_debug(f"Method = '{method}'")
            api_response = do_request(body_params, endpoint, method, url, token)

            status_code = api_response.status_code

            response = {
                "requestResponse": api_response.text,
                "requestStatusCode": status_code,
            }
            return response
        except Exception as e:
            response = {"error": str(e)}
            return response
