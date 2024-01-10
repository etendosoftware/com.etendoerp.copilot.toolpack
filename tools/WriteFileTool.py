import os

from copilot.core.tool_wrapper import ToolWrapper


class WriteFileTool(ToolWrapper):
    name = 'WriteFileTool'
    description = (
        'This is a tool for writing files. Receives: "filepath": string, "content": string, "lineno": integer.'
        'The "filepath" parameter is the path of the file to write.'
        'The "content" parameter is the content of the file to write.'
        'The "override" parameter is a boolean that indicates if the tool needs to override the file or not. '
        'The "lineno" parameter is the line number where to write the content. If the line number is not specified, the content will be appended to the end of the file.'
        'The tool will return the content of the file. '
        'Example of input: { "filepath": "/tmp/test.txt", "content": "Hello world", "override": true, "lineno": 1 }')
    inputs = ['filepath', 'content','override', 'lineno']
    outputs = ['message']

    def run(self, input, *args, **kwargs):
        import json

        # if json is a string, convert it to json, else, use the json
        if isinstance(input, str):
            try:
                json = json.loads(input)
            except:
                return {
                    "message": "Invalid input. Example of input: { \"filepath\": \"/tmp/test.txt\", \"content\": \"Hello world\", \"lineno\": 1 }"}
        else:
            json = input
        p_filepath = json.get('filepath')
        p_content = json.get('content')
        p_lineno = json.get('lineno', -1)
        backup = False
        # if the file doesn't exist, create it
        file_content = ''
        if not os.path.exists(p_filepath):
            open(p_filepath, 'w').close()
        else:  # if the files exists, read it, make a backup(adds .bak%timestamp%) and write the content
            file_content = open(p_filepath).read()
            # backup the file
            import time
            import shutil
            shutil.copyfile(p_filepath, p_filepath + '.bak' + str(time.time()))
            backup = True
            # write the content
        if json.get('override', False):
            if p_lineno == -1:
                file_content += p_content
            else:
                lines = file_content.split('\n')
                lines.insert(p_lineno, p_content)
                file_content = '\n'.join(lines)
            open(p_filepath, 'w').write(file_content)
        else:
            # if overrides, clean the file and write the content
            open(p_filepath, 'a').write(p_content)
        msg = "File %s written successfully, backup: %s" % (p_filepath, backup)
        return {"message": msg}
