import os
from pathlib import Path
from typing import Type

from langsmith import traceable

from copilot.core.tool_input import ToolField, ToolInput
from copilot.core.tool_wrapper import ToolWrapper
from copilot.core.utils import copilot_debug
from copilot.core.utils import get_openai_client


class AudioToolInput(ToolInput):
    path: str = ToolField(description="Path of the audio to be processed.")


@traceable
def get_file_path(input_params):
    rel_path = input_params.get("path")
    audio_path = "/app" + rel_path
    copilot_debug(f"Tool AudioTool input: {audio_path}")
    copilot_debug(f"Current directory: {os.getcwd()}")
    if not Path(audio_path).exists():
        audio_path = ".." + rel_path
    if not Path(audio_path).exists():
        audio_path = rel_path
    if not Path(audio_path).is_file():
        raise Exception(f"Filename {audio_path} doesn't exist")
    return audio_path


class AudioTool(ToolWrapper):
    """Audio recognition tool."""

    name: str = "AudioTool"
    description: str = (
        "This is a tool that uses OpenAI's API to transcribe audio files."
    )
    args_schema: Type[ToolInput] = AudioToolInput

    @traceable
    def run(self, input_params, *args, **kwargs):
        try:
            file_path = get_file_path(input_params)

            client = get_openai_client()

            audio_file = open(file_path, "rb")
            transcription = client.audio.transcriptions.create(
                model="whisper-1", file=audio_file
            )
            print(transcription.text)
        except Exception as e:
            errmsg = f"An error occurred: {e}"
            copilot_debug(errmsg)
            return {"error": errmsg}
        copilot_debug(f"Tool AudioTool output: {transcription}")
        return transcription
