"""Launcher for Echo's toolbox MCP server (600+ tools), so AI apps can start it from any folder:
    <python 3.12>\\python.exe C:\\path\\to\\Echo-main\\desktop\\EchoDesktop\\echo_tools_mcp.py
    py -3.12 C:\\path\\to\\Echo-main\\desktop\\EchoDesktop\\echo_tools_mcp.py      (no space after the dash: "py - 3.12"
                                                                               makes Python wait for a script on stdin)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from echo_desktop.mcp_toolbox import main  # noqa: E402

main()
