import datetime
import os
from typing import Dict, List, Type

from copilot.core.threadcontext import ThreadContext
from copilot.core.tool_input import ToolField, ToolInput
from copilot.core.tool_wrapper import ToolOutput, ToolOutputMessage, ToolWrapper
from copilot.core.utils import copilot_debug


class DockerToolInput(ToolInput):
    executor: str = ToolField(
        name="Executor", description="The executor: python or bash."
    )
    code: str = ToolField(name="Code", description="The code to execute.")
    files_to_copy: List[str] = ToolField(
        name="Files to copy",
        description="List of file paths to copy to the container. There will be copied to the same path in the "
        'container. Example: ["/path/to/file1", "/path/to/file2"]',
    )


def exec_code(docker_client, executor, code, file_to_copy=[]):
    import docker

    name = get_container_name()
    try:
        container = docker_client.containers.get(name)
    except docker.errors.NotFound:
        container = None
    if not container:
        container = start_container(docker_client)
    command = f'{executor} -c "{code}"' if executor in ["python", "bash"] else None
    # Validate the executor type
    if executor not in ["python", "bash"]:
        return ToolOutputMessage(message='Invalid executor, must be "python" or "bash"')

    # Escape double quotes
    code = code.replace('"', '\\"')

    # Command to redirect the output to the log file and capture the output
    if executor == "python":
        command = f'python -c "{code}"'
    elif executor == "bash":
        command = f'bash -c "{code}"'

    import tarfile
    import io

    # Copy files to the container
    for file_path in file_to_copy:
        # Create a tar file in memory
        file_data = io.BytesIO()
        with tarfile.open(fileobj=file_data, mode="w") as tar:
            tar.add(file_path, arcname=file_path.lstrip("/"))

        # Move the pointer to the beginning of the tar file
        file_data.seek(0)

        # Copy the tar file to the container at the specified path
        container.put_archive(path="/", data=file_data)

    # Run the command and capture its output
    result = container.exec_run(cmd=command, stdout=True, stderr=True)

    # Decode the command output
    output = result.output.decode("utf-8")

    log_command = f'echo "Running {executor} command: {code}" >> /tmp/command.log && echo "{output}" >> /tmp/command.log'
    try:
        log_command = str(log_command)
        log_command = log_command.replace('"', '\\"')
        container.exec_run(cmd=f'bash -c "{log_command}"')
    except Exception as e:
        copilot_debug(f"Error logging command: {str(e)}")

    return ToolOutputMessage(message=output)


def get_container_name():
    conversation_id = ThreadContext.get_data("conversation_id")
    name = f"tempenv-copilot-{conversation_id}"
    return name


def clean_old_containers(docker_client):
    # Get all containers that match the name filter
    all_containers = docker_client.containers.list(all=True)
    # Filter the containers that name starts with "tempenv-copilot-"
    temp_env_containers = []
    for container in all_containers:
        if "tempenv" in container.name and "copilot" in container.name:
            copilot_debug(f"Container {container.name} found")
            temp_env_containers.append(container)

    def stop_and_remove_container(container):
        """Function that stops and removes a specific container."""
        container.stop()
        container.remove()
        copilot_debug(f"Container {container.name} removed due to inactivity")

    # Iterates over the containers and creates a thread for each one that meets the inactivity criterion
    for container in temp_env_containers:
        if (
            "last_interaction" not in container.labels
            or datetime.datetime.fromisoformat(container.labels["last_interaction"])
            < datetime.datetime.now() - datetime.timedelta(hours=1)
        ):
            # Create a thread to stop and remove the container
            import threading

            thread = threading.Thread(
                target=stop_and_remove_container, args=(container,)
            )
            thread.start()  # Start the thread


def add_extra_info(environment_vars, extra_info):
    # iterate over the extra_info dictionary and add each key-value pair to the environment_vars dictionary
    for key, value in extra_info.items():
        # If is a value, add it to the environment_vars dictionary
        if isinstance(value, str):
            copilot_debug(f"Adding extra info: {key}")
            environment_vars[key] = value
        if isinstance(value, dict):
            # If is a dictionary, iterate over the dictionary use the function recursively
            copilot_debug(f"Adding recursive extra info: {key}")
            add_extra_info(environment_vars, value)


def start_container(docker_client):
    clean_old_containers(docker_client)
    container_name = get_container_name()
    environment_vars = dict(os.environ)  # Copy environment variables
    extra_info = ThreadContext.get_data("extra_info")
    add_extra_info(environment_vars, extra_info)
    container = docker_client.containers.run(
        "python:3.10-slim",
        name=container_name,
        detach=True,
        command="bash -c 'touch /tmp/command.log && tail -f /tmp/command.log'",
        environment=environment_vars,
        labels={"last_interaction": datetime.datetime.now().isoformat()},
    )
    return container


class DockerTool(ToolWrapper):
    name: str = "DockerTool"
    description: str = (
        "A tool that manages Docker containers to run Python or Bash code. "
        "Containers are deleted when specified after 1 hour of inactivity."
    )
    args_schema: Type[ToolInput] = DockerToolInput

    def run(self, input_params: Dict, *args, **kwargs) -> ToolOutput:
        import docker

        executor = input_params["executor"]
        code = input_params["code"]
        docker_client = docker.from_env()
        if not executor:
            return ToolOutputMessage(message="Executor is required for EXEC mode")
        if executor not in ["python", "bash"]:
            return ToolOutputMessage(
                message='Invalid executor, must be "python" or "bash"'
            )
        if not code:
            return ToolOutputMessage(message="Code is required for EXEC mode")
        files_to_copy = input_params["files_to_copy"]
        return exec_code(docker_client, executor, code, files_to_copy)
