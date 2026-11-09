"""Echo's built-in website control: drives the Chrome or Edge already on this PC through the DevTools protocol
(standard library only). Used in-process by the web agent (BrowserHub) and served to other AI apps as an MCP server
(browser/mcp.py, launcher echo_browser_mcp.py)."""
from .control import TOOLS, Browser, BrowserHub  # noqa: F401
from .sites import load_sites  # noqa: F401
