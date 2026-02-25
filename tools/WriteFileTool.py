import os
from typing import Dict, Type

from langsmith import traceable

from copilot.baseutils.logging_envvar import read_optional_env_var
from copilot.core.tool_input import ToolField, ToolInput
from copilot.core.tool_wrapper import ToolWrapper


class WriteFileToolInput(ToolInput):
    filepath: str = ToolField(
        title="Filepath", description="""The path of the file to write."""
    )
    content: str = ToolField(
        title="Content", description="""The content of the file to write."""
    )
    override: bool = ToolField(
        default=True, description="""If true, the tool will override the file."""
    )
    lineno: int = ToolField(
        default=-1, description="""The line number where to write the content."""
    )


class WriteFileTool(ToolWrapper):
    name: str = "WriteFileTool"
    description: str = (
        'This is a tool for writing files. Receives: "filepath": string, "content": string, "lineno": integer.'
        'The "filepath" parameter is the path of the file to write.'
        'The "content" parameter is the content of the file to write.'
        'The "override" parameter is a boolean that indicates if the tool needs to override the file or not. '
        'The "lineno" parameter is the line number where to write the content. If the line number is not specified, '
        "the content will be appended to the end of the file."
        "The tool will return the content of the file. "
        'Example of input: { "filepath": "/tmp/test.txt", "content": "Hello world", "override": true, "lineno": 1 }'
    )
    args_schema: Type[ToolInput] = WriteFileToolInput

    @traceable
    def run(self, input_params: Dict, *args, **kwargs):
        chmod_env_value = read_optional_env_var("copilot.write.rule", None)
        p_filepath = input_params.get("filepath")
        p_content = input_params.get("content")
        p_lineno = input_params.get("lineno", -1)
        backup = False

        # Ensure the folder exists
        folder = os.path.dirname(p_filepath)
        if folder and (folder != "") and (not os.path.exists(folder)):
            os.makedirs(folder)
            if chmod_env_value:
                os.chmod(folder, int(chmod_env_value, 8))

        # Create the file if it doesn't exist
        file_content = ""
        if not os.path.exists(p_filepath):
            open(p_filepath, "w").close()
            if chmod_env_value:
                os.chmod(p_filepath, int(chmod_env_value, 8))
        else:
            # Read existing file, make a backup, and write content
            import time
            import shutil

            file_content = open(p_filepath).read()
            shutil.copyfile(p_filepath, p_filepath + ".bak" + str(time.time()))
            backup = True

        # Write or append content
        if not input_params.get("override", True):
            if p_lineno == -1:
                file_content += p_content
            else:
                lines = file_content.split("\n")
                lines.insert(p_lineno, p_content)
                file_content = "\n".join(lines)
            open(p_filepath, "w").write(file_content)
        else:
            os.remove(p_filepath)
            open(p_filepath, "w").write(p_content)

        # Apply chmod if COPILOT_WRITE_RULE is set
        if chmod_env_value:
            os.chmod(p_filepath, int(chmod_env_value, 8))

        msg = "File %s written successfully, backup: %s" % (p_filepath, backup)
        return {"message": msg}
