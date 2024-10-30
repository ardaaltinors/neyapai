from langchain.tools import tool

@tool
def magic_function(input: int) -> int:
    """Applies a magic function to an input."""
    return input + 5