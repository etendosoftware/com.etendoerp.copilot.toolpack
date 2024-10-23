import datetime
import uuid
from typing import Type, Dict

import docker

from copilot.core.threadcontext import ThreadContext
from copilot.core.tool_input import ToolField, ToolInput
from copilot.core.tool_wrapper import ToolWrapper, ToolOutputMessage, ToolOutput
from copilot.core.utils import copilot_debug


class DockerToolInput(ToolInput):
    executor: str = ToolField(name='Executor', description='The executor: python or bash.')
    code: str = ToolField(name='Code', description='The code to execute.')


def exec_code(docker_client, executor, code):
    
        name = get_container_name()
        try:    
            container = docker_client.containers.get(name)
        except docker.errors.NotFound:
            container = None
        if not container:
            container = start_container(docker_client)
        command = f'{executor} -c "{code}"' if executor in ['python', 'bash'] else None
         # Validar el tipo de executor
        if executor not in ['python', 'bash']:
            return ToolOutputMessage(message='Invalid executor, must be "python" or "bash"')

        # Escapar las comillas dobles
        code = code.replace('"', '\\"')

        # Comando para redirigir la salida al archivo de log y capturar el output
        if executor == 'python':
            command = f'python -c "{code}"'
        elif executor == 'bash':
            command = f'bash -c "{code}"'

        # Ejecutar el comando y capturar su salida
        result = container.exec_run(cmd=command, stdout=True, stderr=True)

        # Decodificar la salida del comando
        output = result.output.decode('utf-8')

        # Registrar el comando y su salida en el archivo de log del contenedor
        log_command = f'echo "Running {executor} command: {code}" >> /tmp/command.log && echo "{output}" >> /tmp/command.log'
        container.exec_run(cmd=f'bash -c "{log_command}"')

        return ToolOutputMessage(message=output)
    


def get_container_name():
    conversation_id = ThreadContext.get_data('conversation_id')
    name = f"tempenv-copilot-{conversation_id}"
    return name


def clean_old_containers(docker_client):
    all_containers = docker_client.containers.list(all=True, filters={'name': 'tempenv-copilot-*'})
    for container in all_containers:
        if 'last_interaction' not in container.labels or datetime.datetime.fromisoformat(
                container.labels['last_interaction']) < datetime.datetime.now() - datetime.timedelta(hours=1):
            container.stop()
            container.remove()
            copilot_debug(f"Container {container.name} removed due to inactivity")


def start_container(docker_client):
    clean_old_containers(docker_client)
    container_name = get_container_name()
    container = docker_client.containers.run("python:3.10-slim", name=container_name, detach=True, command="bash -c 'touch /tmp/command.log && tail -f /tmp/command.log'")
    return container


class DockerTool(ToolWrapper):
    name = 'DockerTool'
    description = ('A tool that manages Docker containers to run Python or Bash code. '
                   'Containers are deleted when specified after 1 hour of inactivity.')
    args_schema: Type[ToolInput] = DockerToolInput

    def run(self, input_params: Dict, *args, **kwargs) -> ToolOutput:
        executor = input_params['executor']
        code = input_params['code']
        docker_client = docker.from_env()
        if not executor:
            return ToolOutputMessage(message='Executor is required for EXEC mode')
        if executor not in ['python', 'bash']:
            return ToolOutputMessage(message='Invalid executor, must be "python" or "bash"')
        if not code:
            return ToolOutputMessage(message='Code is required for EXEC mode')
        return exec_code(docker_client, executor, code)
