import os
from typing import Type, Dict

from copilot.core.tool_input import ToolField, ToolInput
from copilot.core.tool_wrapper import ToolWrapper


# Input model for the UncompressTool
class UncompressToolInput(ToolInput):
    compressed_file_path: str = ToolField(description="Path to the compressed file")


# Example : Compressed file path: /app/data/test.zip -> files inside the zip file will be extracted to /app/data/test/

# Function to create output directory based on compressed file name
def create_output_dir(compressed_file_path, extension=None):
    output_dir = compressed_file_path[:-len(extension)] if extension else compressed_file_path
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    return output_dir


# Function to list all files and subfiles recursively, ignoring __MACOSX folder
def get_all_files_recursive(directory):
    file_paths = []
    for root, dirs, files in os.walk(directory):
        # Ignore "__MACOSX" folders
        dirs[:] = [d for d in dirs if d != "__MACOSX"]
        for file in files:
            file_paths.append(os.path.join(root, file))
    return file_paths


# Function to uncompress gzip files
def ungzip(compressed_file_path, extension=None):
    import gzip
    import shutil
    output_dir = create_output_dir(compressed_file_path, extension)
    output_file_path = os.path.join(output_dir, os.path.basename(compressed_file_path)[:-3])
    with gzip.open(compressed_file_path, 'rb') as f_in:
        with open(output_file_path, 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)
    return get_all_files_recursive(output_dir)


# Function to uncompress rar files
def unrar(compressed_file_path, extension=None):
    import rarfile
    output_dir = create_output_dir(compressed_file_path, extension)
    with rarfile.RarFile(compressed_file_path) as rf:
        rf.extractall(output_dir)
    return get_all_files_recursive(output_dir)


# Function to uncompress bzip2 files
def unbzip2(compressed_file_path, extension=None):
    import bz2
    import shutil
    output_dir = create_output_dir(compressed_file_path, extension)
    output_file_path = os.path.join(output_dir, os.path.basename(compressed_file_path)[:-4])
    with bz2.open(compressed_file_path, 'rb') as f_in:
        with open(output_file_path, 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)
    return get_all_files_recursive(output_dir)


# Function to uncompress zip files
def unzip(compressed_file_path, extension=None):
    import zipfile
    output_dir = create_output_dir(compressed_file_path, extension)
    with zipfile.ZipFile(compressed_file_path, 'r') as zip_ref:
        zip_ref.extractall(output_dir)
    return get_all_files_recursive(output_dir)


# Function to build a map of file extensions to their corresponding uncompress functions
def build_extension_function_map():
    uncompress_functions = {
        ".zip": unzip,
        ".gz": ungzip,
        ".bz2": unbzip2,
        ".rar": unrar,
    }
    return uncompress_functions


# Main class for the UncompressTool
def check_extension(compressed_file_path):
    for extension in build_extension_function_map().keys():
        if compressed_file_path.endswith(extension):
            return extension
    return None


class UncompressTool(ToolWrapper):
    name = "UncompressTool"
    description = ("This tool uncompresses a file and returns the path list of the uncompressed files."
                   "It receives a path to a compressed file and uncompresses it. ")
    args_schema: Type[ToolInput] = UncompressToolInput

    # Main function to run the tool
    def run(self, input_params: Dict, *args, **kwargs):
        uncompress_functions = build_extension_function_map()
        compressed_file_path = '/app' + input_params.get("compressed_file_path")
        if not os.path.exists(compressed_file_path):
            compressed_file_path = '..' + input_params.get("compressed_file_path")
        if not os.path.exists(compressed_file_path):
            compressed_file_path = input_params.get("compressed_file_path")
        if not os.path.exists(compressed_file_path):
            return {"error": f"The mentioned path was not found {compressed_file_path}."}
        extension = check_extension(compressed_file_path)
        if extension is None:
            return {
                "error": f"Unsupported file type {extension}, supported types are {list(uncompress_functions.keys())}"}

        return {"uncompressed_files_paths": uncompress_functions[extension](compressed_file_path, extension)}