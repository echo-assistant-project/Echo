"""Launcher for Echo's PC-control MCP server, so AI apps can start it from any folder:
    <python 3.12>\\python.exe C:\\path\\to\\Echo-main\\desktop\\EchoDesktop\\echo_mcp.py
    py -3.12 C:\\path\\to\\Echo-main\\desktop\\EchoDesktop\\echo_mcp.py      (no space after the dash: "py - 3.12"
                                                                         makes Python wait for a script on stdin)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from echo_desktop.mcp_server import main  # noqa: E402

main()
