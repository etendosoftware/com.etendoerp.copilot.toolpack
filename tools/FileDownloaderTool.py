from typing import Type, Dict

from pydantic import BaseModel, Field

from copilot.core.tool_wrapper import ToolWrapper


class FileDownloaderToolInput(BaseModel):
    file_path_or_url: str = Field(
        title="File path or URL",
        description='''The file path or URL to download.'''
    )


class FileDownloaderTool(ToolWrapper):
    name = 'FileDownloaderTool'
    description = (
        'This tool receives a URL , downloads the file to a temporary directory if its a URL in a temp file. It returns the path to the temporary file.')
    args_schema: Type[BaseModel] = FileDownloaderToolInput

    def run(self, input_params: Dict, *args, **kwargs):
        import requests
        import os
        import tempfile
        import shutil
        from urllib.parse import urlparse

        file_path_or_url = input_params.get('file_path_or_url')

        if not file_path_or_url.startswith('http://') and not file_path_or_url.startswith('https://'):
            return {'error': 'The provided input is not a valid URL.'}
        else:
            response = requests.get(file_path_or_url, stream=True)
            if response.status_code != 200:
                return {'error': 'File could not be downloaded. Status code: {}'.format(response.status_code)}
            else:
                # Intentar extraer el nombre del archivo del URL
                parsed_url = urlparse(file_path_or_url)
                file_name = os.path.basename(parsed_url.path)

                # Si no se puede determinar el nombre del archivo, usar un nombre genérico
                if not file_name:
                    file_name = "downloaded_file"

                # Determinar si el archivo es de texto o binario
                content_type = response.headers['content-type']
                if 'text' in content_type:
                    # Añadir extensión .txt si el nombre no tiene una
                    if not os.path.splitext(file_name)[1]:
                        file_name += '.txt'
                    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='_' + file_name, mode='w',
                                                            encoding='utf-8')
                    with temp_file as f:
                        f.write(response.text)
                else:
                    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='_' + file_name)
                    with temp_file as f:
                        shutil.copyfileobj(response.raw, f)
                return {'temp_file_path': temp_file.name}
