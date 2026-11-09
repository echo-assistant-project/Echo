"""Launcher for Echo's browser MCP server (website control), so AI apps can start it from any folder:
    <python 3.12>\\python.exe C:\\path\\to\\Echo-main\\desktop\\EchoDesktop\\echo_browser_mcp.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from echo_desktop.browser.mcp import main  # noqa: E402

main()
