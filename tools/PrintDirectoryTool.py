import os

from copilot.core.tool_wrapper import ToolWrapper


class PrintDirectoryTool(ToolWrapper):
    name = 'PrintDirectoryTool'
    description = (''' This tool prints the files and directories of in the current directory. Receives "recursive" boolean and "parent_doubledot_qty" integer parameters.
    The 'recursive' parameter is a boolean that indicates if the tool needs to print the subdirectories recursively or not. 
    And the 'parent_doubledot_qty' parameter where you can specify the number of parent directories to print. The tool will make a .. for each parent_doubledot_qty.
    For example, { "recursive": true, "parent_doubledot_qty": 2 } will print the files and directories of the parent directory of the parent directory of the current directory recursively.
    ''')
    inputs = ['recursive', 'parent_doubledot_qty']
    outputs = ['message']

    def run(self, inputs, *args, **kwargs):
        import json

        # if json is a string, convert it to json, else, use the json
        if isinstance(inputs, str):
            json = json.loads(inputs)

        else:
            json = inputs
        p_parent_doubledot_qty = json.get('parent_doubledot_qty', 0)
        p_recursive = json.get('recursive')

        # read the directory
        p_dir = '.' + p_parent_doubledot_qty * '/..'
        result = []
        if (p_recursive):
            for root, dirs, files in os.walk(p_dir):
                for file in files:
                    #ignore if .git/ is in the path
                    if ".git/" in root:
                        continue
                    if ".idea/" in root:
                        continue
                    if "venv/" in root:
                        continue
                    if "web/com.etendoerp.copilot.dist/" in root:
                        continue
                    result.append(os.path.join(root, file))
        else:
            for file in os.listdir(p_dir):
                #ignore .git folder
                if file == ".git":
                    continue
                result.append(os.path.join(p_dir, file))


        return {"message": result}

