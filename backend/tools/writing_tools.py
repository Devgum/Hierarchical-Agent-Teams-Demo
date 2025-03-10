# coding: utf-8

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import List, Dict, Optional, Annotated, Callable, Any, Literal, Union
import uuid
import functools

from langchain_experimental.utilities import PythonREPL
from langchain_core.tools import tool


class WritingTools:
    def __init__(self, working_directory: Path):
        self.working_directory = working_directory
        # Tool cache
        self._tools_cache = {}
        
        # Tool builder method mapping
        self._tool_builders = {
            "writing": self._build_write_document_tool,
            "editing": self._build_edit_document_tool,
            "repl": self._build_python_repl_tool,
            "outline": self._build_create_outline_tool,
            "reading": self._build_read_document_tool
        }

    def _build_create_outline_tool(self):
        @tool
        def create_outline(
            points: Annotated[List[str], "List of main points or sections."],
            file_name: Annotated[str, "File path to save the outline."],
        ) -> Annotated[str, "Path of the saved outline file."]:
            """Create and save an outline."""
            with (self.working_directory / file_name).open("w") as file:
                for i, point in enumerate(points):
                    file.write(f"{i + 1}. {point}\n")
            return f"Outline saved to {file_name}"
        return create_outline

    def _build_read_document_tool(self):
        @tool
        def read_document(
            file_name: Annotated[str, "File path to read the document from."],
            start: Annotated[Optional[int], "The start line. Default is 0"] = None,
            end: Annotated[Optional[int], "The end line. Default is None"] = None,
        ) -> str:
            """Read the specified document."""
            with (self.working_directory / file_name).open("r") as file:
                lines = file.readlines()
            if start is None:
                start = 0
            return "\n".join(lines[start:end])
        return read_document

    def _build_write_document_tool(self):
        @tool
        def write_document(
            content: Annotated[str, "Text content to be written into the document."],
            file_name: Annotated[str, "File path to save the document."],
        ) -> Annotated[str, "Path of the saved document file."]:
            """Create and save a text document."""
            with (self.working_directory / file_name).open("w") as file:
                file.write(content)
            return f"Document saved to {file_name}"
        return write_document
    
    def _build_edit_document_tool(self):
        @tool
        def edit_document(
            file_name: Annotated[str, "Path of the document to be edited."],
            inserts: Annotated[
                Dict[int, str],
                "Dictionary where key is the line number (1-indexed) and value is the text to be inserted at that line.",
            ],
        ) -> Annotated[str, "Path of the edited document file."]:
            """Edit a document by inserting text at specific line numbers."""

            with (self.working_directory / file_name).open("r") as file:
                lines = file.readlines()

            sorted_inserts = sorted(inserts.items())

            for line_number, text in sorted_inserts:
                if 1 <= line_number <= len(lines) + 1:
                    lines.insert(line_number - 1, text + "\n")
                else:
                    return f"Error: Line number {line_number} is out of range."

            with (self.working_directory / file_name).open("w") as file:
                file.writelines(lines)

            return f"Document edited and saved to {file_name}"
        
        return edit_document
    
    def _build_python_repl_tool(self):
        repl = PythonREPL()

        @tool
        def python_repl_tool(
            code: Annotated[str, "The python code to execute to generate your chart."],
        ):
            """Use this to execute python code. If you want to see the output of a value,
            you should print it out with `print(...)`. This is visible to the user."""
            try:
                result = repl.run(code)
            except BaseException as e:
                return f"Failed to execute. Error: {repr(e)}"
            return f"Successfully executed:\n```python\n{code}\n```\nStdout: {result}"
        
        return python_repl_tool
    
    def get_tools(self, tool_types: Union[List[Literal["writing", "editing", "repl", "outline", "reading"]], Literal["writing", "editing", "repl", "outline", "reading"]]):
        """
        Get tools of specified types
        
        Args:
            tool_types: Can be a single tool type or a list of tool types
            
        Returns:
            A list containing the requested tools
        """
        # 如果传入的是单个工具类型，转换为列表
        # If a single tool type is passed, convert it to a list
        if isinstance(tool_types, str):
            tool_types = [tool_types]
            
        tools = []
        for tool_type in tool_types:
            if tool_type in self._tool_builders:
                # 按需构建工具：如果缓存中没有，则构建并缓存
                if tool_type not in self._tools_cache:
                    self._tools_cache[tool_type] = self._tool_builders[tool_type]()
                tools.append(self._tools_cache[tool_type])
            else:
                raise ValueError(f"Unknown tool type: {tool_type}")
                
        return tools
