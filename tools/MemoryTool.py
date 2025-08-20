"""
Memory Tool for Etendo Copilot Toolpack

This module provides a comprehensive tool for managing memories in a vector database
using Chroma as the backend storage. It supports CRUD operations (Create, Read, Update, Delete)
for user-specific memories with vector similarity search capabilities.

Author: Etendo Software
Version: 1.0
"""

import uuid
from typing import Optional, Type

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langsmith import traceable

from copilot.baseutils.logging_envvar import copilot_debug
from copilot.core.threadcontext import ThreadContext
from copilot.core.tool_input import ToolField, ToolInput
from copilot.core.tool_wrapper import ToolWrapper

from copilot.core.vectordb_utils import (
    get_chroma_settings,
    get_embedding,
    get_vector_db_path,
)


class MemoryToolInput(ToolInput):
    """
    Input schema for the MemoryTool.

    This class defines the expected input parameters for memory operations including
    mode selection, memory content, search queries, and memory identifiers.

    Attributes:
        mode (str): Operation mode - must be 'add', 'search', 'update', or 'delete'
        memory (Optional[str]): Memory content to store or update (required for add/update modes)
        query (Optional[str]): Search query string for finding similar memories (required for search mode)
        memory_id (Optional[str]): Unique identifier for targeting specific memories (required for update/delete modes)
        k (int): Maximum number of search results to return, only applies to search mode (default: 3)
    """

    mode: str = ToolField(
        description="Operation mode. Must be one of: 'add', 'search', 'update', or 'delete'."
    )
    memory: Optional[str] = ToolField(
        description="The memory content to store or update. Required for 'add' and 'update' modes.",
        default=None,
    )
    query: Optional[str] = ToolField(
        description="Search query string to find similar memories. Required for 'search' mode.",
        default=None,
    )
    memory_id: Optional[str] = ToolField(
        description="Unique identifier of the memory to modify or remove. Required for 'update' and 'delete' modes.",
        default=None,
    )
    k: int = ToolField(
        description="Maximum number of search results to return. Only used in 'search' mode.",
        default=3,
    )


@traceable
def validate_and_process_input(input_params):
    """
    Validate and process input parameters for memory operations.

    This function validates the input mode and extracts all necessary parameters
    for the memory operation. It ensures the mode is valid and returns all
    parameters in a structured format.

    Args:
        input_params (dict): Dictionary containing input parameters from the user

    Returns:
        tuple: A tuple containing (mode, memory, query, memory_id, k)

    Raises:
        ValueError: If the mode is not one of the supported operations

    Example:
        >>> params = {"mode": "add", "memory": "Test memory", "k": 5}
        >>> mode, memory, query, memory_id, k = validate_and_process_input(params)
    """
    mode = input_params.get("mode")
    memory = input_params.get("memory")
    query = input_params.get("query")
    memory_id = input_params.get("memory_id")
    k = input_params.get("k", 3)

    if mode not in ["add", "search", "update", "delete"]:
        raise ValueError(
            f"Invalid mode '{mode}'. Use 'add', 'search', 'update', or 'delete'."
        )

    return mode, memory, query, memory_id, k


def get_vector_store(kb_vectordb_id):
    """
    Initialize and return a Chroma vector database instance.

    This function sets up a connection to the Chroma vector database using
    the provided knowledge base vector database ID. It configures the database
    with the appropriate embedding function and client settings.

    Args:
        kb_vectordb_id (str): Unique identifier for the knowledge base vector database

    Returns:
        Chroma: Configured Chroma vector database instance ready for operations

    Example:
        >>> vector_store = get_vector_store("assistant_123_memories")
        >>> # vector_store is now ready for add/search/update/delete operations
    """
    db_path = get_vector_db_path(kb_vectordb_id)
    db = Chroma(
        persist_directory=db_path,
        embedding_function=get_embedding(),
        client_settings=get_chroma_settings(),
    )
    return db


def delete(memory_id, user_id, vector_store):
    """
    Delete a specific memory from the vector database.

    This function removes a memory document from the vector store based on the
    provided memory ID. It first verifies that the memory exists and belongs
    to the specified user before performing the deletion.

    Args:
        memory_id (str): Unique identifier of the memory to delete
        user_id (str): ID of the user who owns the memory
        vector_store (Chroma): Vector database instance to delete from

    Returns:
        dict: Result dictionary containing either success message or error
              - On success: {"result": "Memory with memory_id {id} deleted for user_id {user}"}
              - On error: {"error": "Error description"}

    Example:
        >>> result = delete("mem_123", "user_456", vector_store)
        >>> if "result" in result:
        ...     print("Memory deleted successfully")
    """
    if not memory_id:
        return {"error": "The 'memory_id' parameter is required for 'delete' mode."}
    current_docs = vector_store.get(ids=[memory_id])
    if not current_docs["ids"] or current_docs["metadatas"][0]["user_id"] != user_id:
        return {
            "error": f"No memory found with memory_id {memory_id} for user_id {user_id}"
        }
    vector_store.delete(ids=[memory_id])
    result = f"Memory with memory_id {memory_id} deleted for user_id {user_id}"
    copilot_debug(f"Tool MemoryTool output: {result}")
    return {"result": result}


def update(memory, memory_id, user_id, vector_store):
    """
    Update an existing memory in the vector database.

    This function modifies the content of an existing memory document while
    preserving its metadata. It verifies that the memory exists and belongs
    to the specified user before performing the update operation.

    Args:
        memory (str): New content for the memory
        memory_id (str): Unique identifier of the memory to update
        user_id (str): ID of the user who owns the memory
        vector_store (Chroma): Vector database instance to update

    Returns:
        dict: Result dictionary containing either success message or error
              - On success: {"result": "Memory updated for user_id {user}: {content} (memory_id: {id})"}
              - On error: {"error": "Error description"}

    Example:
        >>> result = update("Updated memory content", "mem_123", "user_456", vector_store)
        >>> if "result" in result:
        ...     print("Memory updated successfully")
    """
    if not memory_id or not memory:
        return {
            "error": "Both 'memory_id' and 'memory' are required for 'update' mode."
        }
    current_docs = vector_store.get(ids=[memory_id])
    if not current_docs["ids"] or current_docs["metadatas"][0]["user_id"] != user_id:
        return {
            "error": f"No memory found with memory_id {memory_id} for user_id {user_id}"
        }
    updated_doc = Document(
        page_content=memory, metadata={"user_id": user_id, "memory_id": memory_id}
    )
    vector_store.update_documents(ids=[memory_id], documents=[updated_doc])
    result = f"Memory updated for user_id {user_id}: {memory} (memory_id: {memory_id})"
    copilot_debug(f"Tool MemoryTool output: {result}")
    return {"result": result}


def search(k, query, user_id, vector_store):
    """
    Search for memories using vector similarity search.

    This function performs a semantic search over the user's memories using
    vector similarity. It returns the most relevant memories based on the
    query string, filtered by the user ID.

    Args:
        k (int): Maximum number of results to return
        query (str): Search query to find similar memories
        user_id (str): ID of the user whose memories to search
        vector_store (Chroma): Vector database instance to search in

    Returns:
        dict: Result dictionary containing either search results or error
              - On success: {"result": "Formatted list of matching memories with IDs"}
              - On no results: {"result": "No memories found message"}
              - On error: {"error": "Error description"}

    Example:
        >>> result = search(3, "important meeting", "user_456", vector_store)
        >>> if "result" in result:
        ...     print(f"Found memories: {result['result']}")
    """
    if not query:
        return {"error": "The 'query' parameter is required for 'search' mode."}
    results = vector_store.similarity_search(
        query=query, k=k, filter={"user_id": user_id}
    )
    if not results:
        result = f"No memories found for user_id {user_id} with query: {query}"
    else:
        result = "\n".join(
            [
                f"- {doc.page_content} (memory_id: {doc.metadata['memory_id']})"
                for doc in results
            ]
        )
    copilot_debug(f"Tool MemoryTool output: {result}")
    return {"result": result}


def add(memory, user_id, vector_store):
    """
    Add a new memory to the vector database.

    This function creates a new memory document with the provided content and
    associates it with the specified user. A unique memory ID is automatically
    generated using UUID1.

    Args:
        memory (str): Content of the memory to store
        user_id (str): ID of the user who owns the memory
        vector_store (Chroma): Vector database instance to add to

    Returns:
        dict: Result dictionary containing either success message or error
              - On success: {"result": "Memory added for user_id {user}: {content} (memory_id: {id})"}
              - On error: {"error": "Error description"}

    Example:
        >>> result = add("Remember to call John tomorrow", "user_456", vector_store)
        >>> if "result" in result:
        ...     print("Memory added successfully")
    """
    if not memory:
        return {"error": "The 'memory' parameter is required for 'add' mode."}
    memory_id = str(uuid.uuid1())
    document = Document(
        page_content=memory, metadata={"user_id": user_id, "memory_id": memory_id}
    )
    vector_store.add_documents(documents=[document], ids=[memory_id])
    result = f"Memory added for user_id {user_id}: {memory} (memory_id: {memory_id})"
    copilot_debug(f"Tool MemoryTool output: {result}")
    return {"result": result}


def read_context_variables():
    """
    Retrieve context variables from the current thread context.

    This function extracts the assistant ID and user ID from the thread context,
    which are required for memory operations. These values are used to create
    user-specific vector stores and ensure data isolation.

    Returns:
        tuple: A tuple containing (assistant_id, user_id)
               - assistant_id (str|None): Unique identifier for the assistant
               - user_id (str|None): Unique identifier for the user (AD User ID)

    Example:
        >>> assistant_id, user_id = read_context_variables()
        >>> if assistant_id and user_id:
        ...     print(f"Context loaded: Assistant {assistant_id}, User {user_id}")
    """
    assistant_id = ThreadContext.get_data("assistant_id", None)
    user_id = ThreadContext.get_data("ad_user_id", None)
    return assistant_id, user_id


class MemoryTool(ToolWrapper):
    """
    A comprehensive tool for managing user memories in a vector database.

    This class provides a complete interface for memory management operations
    including adding, searching, updating, and deleting memories. Each memory
    is associated with a specific user and stored in a vector database for
    efficient similarity-based retrieval.

    The tool uses Chroma as the vector database backend and maintains user
    isolation by filtering operations based on user IDs. Memory operations
    are traced for debugging and monitoring purposes.

    Supported Operations:
        - add: Create a new memory with automatic ID generation
        - search: Find memories using vector similarity search
        - update: Modify existing memory content
        - delete: Remove a specific memory

    Attributes:
        name (str): Tool identifier "MemoryTool"
        description (str): Human-readable description of tool capabilities
        args_schema (Type[ToolInput]): Input validation schema class

    Example:
        >>> tool = MemoryTool()
        >>> params = {"mode": "add", "memory": "Important meeting notes"}
        >>> result = tool.run(params)
        >>> print(result["result"])
    """

    name: str = "MemoryTool"
    description: str = (
        "A comprehensive tool for managing user memories in a vector database. "
        "Supports four operation modes: "
        "'add' (requires 'memory' field), "
        "'search' (requires 'query' field, optional 'k' for result limit), "
        "'update' (requires 'memory_id' and 'memory' fields), "
        "'delete' (requires 'memory_id' field). "
        "All operations are user-scoped and use memory_id for specific memory identification."
    )
    args_schema: Type[ToolInput] = MemoryToolInput

    @traceable
    def run(self, input_params, *args, **kwargs):
        """
        Execute the memory operation based on the provided parameters.

        This method serves as the main entry point for all memory operations.
        It validates inputs, retrieves context variables, initializes the vector
        store, and delegates to the appropriate operation function.

        Args:
            input_params (dict): Dictionary containing operation parameters
                - mode (str): Operation type ('add', 'search', 'update', 'delete')
                - memory (str, optional): Memory content for add/update
                - query (str, optional): Search query for search operations
                - memory_id (str, optional): Memory identifier for update/delete
                - k (int, optional): Maximum search results (default: 3)
            *args: Additional positional arguments (unused)
            **kwargs: Additional keyword arguments (unused)

        Returns:
            dict: Operation result containing either success data or error message
                  - On success: {"result": "Operation-specific success message"}
                  - On error: {"error": "Detailed error description"}

        Raises:
            ValueError: If required context variables are missing
            Exception: For any other operation failures

        Example:
            >>> params = {"mode": "search", "query": "meeting notes", "k": 5}
            >>> result = tool.run(params)
            >>> if "error" not in result:
            ...     print(f"Search results: {result['result']}")
        """
        try:
            mode, memory, query, memory_id, k = validate_and_process_input(input_params)
            assistant_id, user_id = read_context_variables()
            if not assistant_id or not user_id:
                # throw exception
                raise ValueError("assistant_id or ad_user_id not found in Payload.")
            vector_store = get_vector_store(kb_vectordb_id=assistant_id + "_memories")
            if mode == "add":
                return add(memory, user_id, vector_store)

            elif mode == "search":
                return search(k, query, user_id, vector_store)

            elif mode == "update":
                return update(memory, memory_id, user_id, vector_store)

            elif mode == "delete":
                return delete(memory_id, user_id, vector_store)

        except Exception as e:
            errmsg = f"Error in MemoryTool: {str(e)}"
            copilot_debug(errmsg)
            return {"error": errmsg}
