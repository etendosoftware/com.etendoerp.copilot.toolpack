from typing import Dict, Optional, Type

from copilot.core import etendo_utils
from copilot.core.etendo_utils import get_etendo_host, get_etendo_token
from copilot.core.exceptions import ToolException
from copilot.core.threadcontext import ThreadContext
from copilot.core.tool_input import ToolField, ToolInput
from copilot.core.tool_wrapper import (
    ToolOutput,
    ToolOutputError,
    ToolOutputMessage,
    ToolWrapper,
)


class LoadOAuthTokenInput(ToolInput):
    al: Optional[str] = ToolField(
        default=None,
        description="Alias of the OAuth token to load. If not provided, the default "
        "alias will be used.",
    )


class LoadOAuthTokenTool(ToolWrapper):
    name: str = "LoadOAuthTokenTool"
    description: str = (
        "This tool loads an OAuth token and returns a message indicating"
        " the alias wich was used to load the token."
    )

    args_schema: Type[ToolInput] = LoadOAuthTokenInput
    return_direct: bool = False

    def run(self, input_params: Dict = None, *args, **kwargs) -> ToolOutput:
        import uuid

        try:
            alias = input_params.get("al", "TOKEN_" + str(uuid.uuid4()))
            token_oauth = etendo_utils.call_etendo(
                url=get_etendo_host(),
                method="POST",
                endpoint="/webhooks/ReadOAuthToken",
                access_token=get_etendo_token(),
                body_params={},
            )
            if not token_oauth or token_oauth.get("token") is None:
                raise ToolException(
                    f"No OAuth token found. " f"Error " f"message:{str(token_oauth)}"
                )

            tokens = ThreadContext.get_data("oauth_tokens")
            if not tokens:
                tokens = {}
            tokens[alias] = token_oauth
            ThreadContext.set_data("oauth_tokens", tokens)
            ThreadContext.save_conversation()
            result_message = (
                f"OAuth token loaded successfully with alias: {alias}. "
                "You can now use this alias to access the token."
            )

            # Implement your tool's logic here
            return ToolOutputMessage(message=result_message)
        except Exception as e:
            error_message = f"Error loading OAuth token: {str(e)}"
            return ToolOutputError(message=error_message)
