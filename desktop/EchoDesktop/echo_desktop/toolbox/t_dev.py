"""Developer tools: read-only git, code statistics, TODO finder, dependencies, templates, HTTP requests, small checks.
git runs with fixed read-only subcommands only (status, log, branch, diff --stat, remote, shortlog, show --stat)."""
from __future__ import annotations

import ast
import json
import os
import re
import shlex
from pathlib import Path
from typing import Literal

from . import ToolError, tool
from ..words import many

C = "dev"


def _repo(path: str, ctx) -> Path:
    from .t_files import resolve
    ws = getattr(ctx, "workspaces", None) or {}
    key = path.strip().lower()
    p = resolve(ws[key], ctx) if key in ws else resolve(path or ".", ctx)
    if p.is_file():
        p = p.parent
    cur = p
    while not (cur / ".git").exists():
        if cur.parent == cur:
            raise ToolError(f"{p} isn't inside a git repository")
        cur = cur.parent
    return cur


def git(repo: Path, *args) -> str:
    from .t_system import run
    exe = "git"
    bundled = Path(os.environ.get("LOCALAPPDATA", "")) / "EchoAndroid" / "Git" / "cmd" / "git.exe"
    if bundled.exists():
        exe = str(bundled)
    return run([exe, "-C", str(repo), "--no-pager", *args], timeout=30).strip()


@tool(C, keys="git status changes modified uncommitted repository")
def git_status(repo: str, ctx=None) -> str:
    """git status of a repository (path or workspace name): branch, changed and untracked files."""
    r = _repo(repo, ctx)
    return git(r, "status", "--short", "--branch") or "Clean working tree."


@tool(C, keys="git log history commits recent")
def git_log(repo: str, count: int = 15, ctx=None) -> str:
    """Recent commits of a repository."""
    return git(_repo(repo, ctx), "log", f"-{max(1, min(count, 100))}", "--pretty=format:%h %ad %an: %s", "--date=short")


@tool(C, keys="git branches list current")
def git_branches(repo: str, ctx=None) -> str:
    """Local branches (current marked with *) and their last commit."""
    return git(_repo(repo, ctx), "branch", "-vv")


@tool(C, keys="git diff changes summary stat")
def git_diff_summary(repo: str, staged: bool = False, ctx=None) -> str:
    """Which files changed and how much (diff --stat)."""
    args = ["diff", "--stat"] + (["--staged"] if staged else [])
    return git(_repo(repo, ctx), *args) or "No changes."


@tool(C, keys="git remotes origin url")
def git_remotes(repo: str, ctx=None) -> str:
    """The repository's remotes."""
    return git(_repo(repo, ctx), "remote", "-v") or "No remotes."


@tool(C, keys="git contributors authors commits count")
def git_contributors(repo: str, ctx=None) -> str:
    """Who committed, and how many commits each."""
    return git(_repo(repo, ctx), "shortlog", "-sne", "HEAD")


@tool(C, keys="git last commit show details")
def git_last_commit(repo: str, ctx=None) -> str:
    """The latest commit with the files it changed."""
    return git(_repo(repo, ctx), "show", "--stat", "--pretty=format:%h %an %ad%n%s%n%b", "--date=iso", "HEAD")[:4000]


LANG = {".py": "Python", ".js": "JavaScript", ".ts": "TypeScript", ".tsx": "TypeScript", ".jsx": "JavaScript", ".java": "Java", ".kt": "Kotlin",
        ".cs": "C#", ".go": "Go", ".rs": "Rust", ".c": "C", ".h": "C", ".cpp": "C++", ".hpp": "C++", ".rb": "Ruby", ".php": "PHP",
        ".swift": "Swift", ".dart": "Dart", ".lua": "Lua", ".html": "HTML", ".css": "CSS", ".scss": "SCSS", ".sql": "SQL", ".sh": "Shell",
        ".ps1": "PowerShell", ".vue": "Vue", ".svelte": "Svelte", ".md": "Markdown", ".json": "JSON", ".yml": "YAML", ".yaml": "YAML"}


@tool(C, keys="lines of code count languages project size statistics")
def code_stats(folder: str, ctx=None) -> list:
    """Lines of code per language in a project folder."""
    from .t_files import resolve, walk_files
    root = resolve(folder)
    stats = {}
    for f in walk_files(root, 50_000):
        lang = LANG.get(f.suffix.lower())
        if not lang:
            continue
        try:
            n = sum(1 for l in f.read_text(encoding="utf-8", errors="ignore").splitlines() if l.strip())
        except OSError:
            continue
        c, l = stats.get(lang, (0, 0))
        stats[lang] = (c + 1, l + n)
    return [f"{lang}: {many(l, 'line')} in {many(c, 'file')}" for lang, (c, l) in sorted(stats.items(), key=lambda x: -x[1][1])] or ["No code files found."]


@tool(C, keys="todo fixme hack notes in code find")
def find_todos(folder: str, ctx=None) -> list:
    """TODO / FIXME / HACK / XXX comments in a project."""
    from .t_files import resolve, walk_files
    root = resolve(folder)
    out = []
    for f in walk_files(root, 50_000):
        if f.suffix.lower() not in LANG:
            continue
        try:
            for i, l in enumerate(f.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                if re.search(r"\b(TODO|FIXME|HACK|XXX)\b", l):
                    out.append(f"{f.relative_to(root)}:{i}: {l.strip()[:140]}")
                    if len(out) >= 100:
                        return out
        except OSError:
            continue
    return out or ["No TODOs found."]


@tool(C, keys="dependencies packages requirements package.json pyproject list")
def project_dependencies(folder: str, ctx=None) -> dict:
    """Dependencies declared by a project (package.json, requirements.txt, pyproject.toml, Cargo.toml, go.mod)."""
    from .t_files import resolve
    root = resolve(folder)
    out = {}
    pj = root / "package.json"
    if pj.exists():
        d = json.loads(pj.read_text(encoding="utf-8"))
        out["npm"] = d.get("dependencies", {})
        out["npm (dev)"] = d.get("devDependencies", {})
    rq = root / "requirements.txt"
    if rq.exists():
        out["pip"] = [l.strip() for l in rq.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]
    for name in ("pyproject.toml", "Cargo.toml"):
        f = root / name
        if f.exists():
            import tomllib
            d = tomllib.loads(f.read_text(encoding="utf-8"))
            out[name] = d.get("project", {}).get("dependencies") or d.get("dependencies") or d.get("tool", {}).get("poetry", {}).get("dependencies")
    gm = root / "go.mod"
    if gm.exists():
        out["go"] = re.findall(r"^\s*([\w./-]+)\s+v[\w.-]+", gm.read_text(encoding="utf-8"), re.M)
    return out or {"note": "No dependency files found."}


@tool(C, ex={"code": "def f(x):\n    return x * 2\n"}, keys="python syntax check error compile valid")
def python_syntax_check(code: str) -> str:
    """Check Python code for syntax errors (it isn't run)."""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return f"Syntax error on line {e.lineno}: {e.msg}" + (f"\n  {e.text.rstrip()}" if e.text else "")
    funcs = [n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    classes = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
    return "No syntax errors." + (f" Functions: {', '.join(funcs[:20])}." if funcs else "") + (f" Classes: {', '.join(classes[:20])}." if classes else "")


@tool(C, ex={"code": "import os\nimport sys, json\nfrom pathlib import Path\n"}, keys="python imports list modules used")
def python_imports(code: str) -> list:
    """Modules a piece of Python code imports."""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        raise ToolError(f"that isn't valid Python (line {e.lineno}: {e.msg}), so I can't list its imports")
    mods = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            mods.update(a.name.split(".")[0] for a in n.names)
        elif isinstance(n, ast.ImportFrom) and n.module:
            mods.add(n.module.split(".")[0])
    return sorted(mods)


GITIGNORE = {
    "python": "__pycache__/\n*.py[cod]\n.venv/\nvenv/\n.env\n*.egg-info/\ndist/\nbuild/\n.pytest_cache/\n.mypy_cache/\n.coverage\n.ipynb_checkpoints/\n",
    "node": "node_modules/\ndist/\nbuild/\n.env\n.env.local\nnpm-debug.log*\nyarn-error.log\n.next/\n.cache/\ncoverage/\n",
    "java": "*.class\ntarget/\nbuild/\n.gradle/\n*.jar\n!gradle-wrapper.jar\n.idea/\n*.iml\nlocal.properties\n",
    "android": ".gradle/\nbuild/\nlocal.properties\n.idea/\n*.iml\ncaptures/\n.externalNativeBuild/\n.cxx/\n*.apk\n*.keystore\n",
    "dotnet": "bin/\nobj/\n*.user\n.vs/\n*.suo\npackages/\nTestResults/\n",
    "go": "bin/\n*.exe\n*.test\n*.out\nvendor/\n.env\n",
    "rust": "target/\nCargo.lock\n**/*.rs.bk\n",
    "unity": "[Ll]ibrary/\n[Tt]emp/\n[Oo]bj/\n[Bb]uild/\n[Bb]uilds/\n[Ll]ogs/\n[Uu]ser[Ss]ettings/\n*.csproj\n*.sln\n",
    "general": ".DS_Store\nThumbs.db\n*.log\n.env\n.idea/\n.vscode/\n*.swp\n",
}


@tool(C, ex={"kind": "python"}, keys="gitignore template ignore files")
def gitignore_template(kind: Literal["python", "node", "java", "android", "dotnet", "go", "rust", "unity", "general"]) -> str:
    """A starter .gitignore."""
    return GITIGNORE[kind] + ("" if kind == "general" else "\n# general\n" + GITIGNORE["general"])


@tool(C, ex={"license": "MIT", "holder": "Asha K"}, keys="license text mit isc open source")
def license_text(license: Literal["MIT", "ISC", "BSD-2-Clause"], holder: str, year: int = 0) -> str:
    """Full text of a short open-source licence."""
    from datetime import date
    y = year or date.today().year
    if license == "MIT":
        return (f"MIT License\n\nCopyright (c) {y} {holder}\n\nPermission is hereby granted, free of charge, to any person obtaining a copy\n"
                "of this software and associated documentation files (the \"Software\"), to deal\nin the Software without restriction, including without limitation the rights\n"
                "to use, copy, modify, merge, publish, distribute, sublicense, and/or sell\ncopies of the Software, and to permit persons to whom the Software is\n"
                "furnished to do so, subject to the following conditions:\n\nThe above copyright notice and this permission notice shall be included in all\n"
                "copies or substantial portions of the Software.\n\nTHE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR\n"
                "IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,\nFITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE\n"
                "AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER\nLIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,\n"
                "OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE\nSOFTWARE.\n")
    if license == "ISC":
        return (f"ISC License\n\nCopyright (c) {y} {holder}\n\nPermission to use, copy, modify, and/or distribute this software for any\n"
                "purpose with or without fee is hereby granted, provided that the above\ncopyright notice and this permission notice appear in all copies.\n\n"
                "THE SOFTWARE IS PROVIDED \"AS IS\" AND THE AUTHOR DISCLAIMS ALL WARRANTIES\nWITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF\n"
                "MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR\nANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES\n"
                "WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN\nACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF\n"
                "OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.\n")
    return (f"BSD 2-Clause License\n\nCopyright (c) {y}, {holder}\n\nRedistribution and use in source and binary forms, with or without\n"
            "modification, are permitted provided that the following conditions are met:\n\n1. Redistributions of source code must retain the above copyright notice, this\n"
            "   list of conditions and the following disclaimer.\n\n2. Redistributions in binary form must reproduce the above copyright notice,\n"
            "   this list of conditions and the following disclaimer in the documentation\n   and/or other materials provided with the distribution.\n\n"
            "THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS \"AS IS\"\nAND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE\n"
            "IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE\nDISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE\n"
            "FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL\nDAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR\n"
            "SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER\nCAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,\n"
            "OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE\nOF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.\n")


@tool(C, ex={"name": "echo-tools", "description": "Handy tools", "language": "python"}, keys="readme template documentation project")
def readme_template(name: str, description: str, language: Literal["python", "node", "other"] = "python") -> str:
    """A starter README.md."""
    install = {"python": "python -m venv .venv\n.venv\\Scripts\\activate\npip install -r requirements.txt", "node": "npm install\nnpm run dev", "other": "# describe setup here"}[language]
    return f"# {name}\n\n{description}\n\n## Getting started\n\n```bash\n{install}\n```\n\n## Usage\n\nDescribe how to use it.\n\n## License\n\nMIT\n"


DOCKERFILES = {
    "python": "FROM python:3.12-slim\nWORKDIR /app\nCOPY requirements.txt .\nRUN pip install --no-cache-dir -r requirements.txt\nCOPY . .\nCMD [\"python\", \"main.py\"]\n",
    "node": "FROM node:22-alpine\nWORKDIR /app\nCOPY package*.json ./\nRUN npm ci --omit=dev\nCOPY . .\nEXPOSE 3000\nCMD [\"node\", \"index.js\"]\n",
    "static": "FROM nginx:alpine\nCOPY . /usr/share/nginx/html\nEXPOSE 80\n",
    "go": "FROM golang:1.23 AS build\nWORKDIR /src\nCOPY . .\nRUN CGO_ENABLED=0 go build -o /app .\n\nFROM gcr.io/distroless/static\nCOPY --from=build /app /app\nENTRYPOINT [\"/app\"]\n",
}


@tool(C, ex={"kind": "python"}, keys="dockerfile docker template container")
def dockerfile_template(kind: Literal["python", "node", "static", "go"]) -> str:
    """A starter Dockerfile."""
    return DOCKERFILES[kind]


@tool(C, ex={"kind": "python"}, keys="github actions ci workflow yaml test")
def ci_workflow_template(kind: Literal["python", "node"]) -> str:
    """A starter GitHub Actions workflow that runs tests on every push."""
    if kind == "python":
        steps = "      - uses: actions/setup-python@v5\n        with:\n          python-version: '3.12'\n      - run: pip install -r requirements.txt\n      - run: python -m pytest -q\n"
    else:
        steps = "      - uses: actions/setup-node@v4\n        with:\n          node-version: 22\n      - run: npm ci\n      - run: npm test\n"
    return "name: tests\non: [push, pull_request]\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n" + steps


@tool(C, ex={"command": "curl -X POST https://api.example.com/v1/items -H 'Content-Type: application/json' -d '{\"name\": \"pen\"}'"}, keys="curl to python requests convert code")
def curl_to_python(command: str) -> str:
    """Convert a curl command into Python requests code."""
    try:
        parts = shlex.split(command.replace("\\\n", " "))
    except ValueError as e:
        raise ToolError(f"can't read that command: {e}")
    if not parts or parts[0] != "curl":
        raise ToolError("start with curl")
    method, url, headers, data = "GET", None, {}, None
    it = iter(parts[1:])
    for a in it:
        if a in ("-X", "--request"):
            method = next(it).upper()
        elif a in ("-H", "--header"):
            k, _, v = next(it).partition(":")
            headers[k.strip()] = v.strip()
        elif a in ("-d", "--data", "--data-raw", "--data-binary"):
            data = next(it)
            method = "POST" if method == "GET" else method
        elif a in ("-u", "--user"):
            headers["Authorization"] = "Basic <" + next(it).split(":")[0] + ":…>"
        elif not a.startswith("-"):
            url = a
    if not url:
        raise ToolError("no URL in the command")
    lines = ["import requests", "", f"url = {url!r}"]
    if headers:
        lines.append(f"headers = {json.dumps(headers, indent=4)}")
    body = ""
    if data is not None:
        try:
            lines.append(f"payload = {json.dumps(json.loads(data), indent=4)}")
            body = ", json=payload"
        except ValueError:
            lines.append(f"data = {data!r}")
            body = ", data=data"
    lines.append(f"response = requests.{method.lower()}(url{', headers=headers' if headers else ''}{body}, timeout=30)")
    lines += ["response.raise_for_status()", "print(response.json())"]
    return "\n".join(lines)


@tool(C, net=True, keys="http request api call get post rest test endpoint")
def http_request(url: str, method: Literal["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE"] = "GET", body: str = "",
                 headers: dict = None, ctx=None) -> str:
    """Call a public web API (GET/HEAD freely; POST/PUT/PATCH/DELETE ask you first). Private/local addresses are refused."""
    from .. import internet
    if method not in ("GET", "HEAD"):
        from .t_files import confirm
        confirm(ctx, f"Send a {method} request?", f"{url}\n\n{body[:400]}")
    h = {"Content-Type": "application/json"} if body.strip().startswith(("{", "[")) else {}
    h.update({str(k): str(v) for k, v in (headers or {}).items()})
    r = internet.request(url, method=method, headers=h, data=body.encode() if body else None, max_bytes=500_000)
    text = r.text()
    if "json" in r.content_type:
        try:
            text = json.dumps(json.loads(text), indent=1, ensure_ascii=False)
        except ValueError:
            pass
    return f"HTTP {r.status} ({r.elapsed * 1000:.0f} ms, {r.content_type})\n{text[:8000]}"


@tool(C, ex={"text": "The quick brown fox jumps over the lazy dog. " * 20}, keys="tokens count llm estimate prompt length")
def estimate_tokens(text: str) -> str:
    """Rough count of AI tokens in a text (≈ 4 characters or ¾ of a word each)."""
    words = len(text.split())
    return f"About {round((len(text) / 4 + words / 0.75) / 2):,} tokens ({many(len(text), 'character')}, {many(words, 'word')})."


@tool(C, ex={"message": "feat(api): add login endpoint"}, keys="commit message conventional check format")
def commit_message_check(message: str) -> str:
    """Check a commit message against Conventional Commits (feat:, fix:, docs:…)."""
    first = message.strip().splitlines()[0] if message.strip() else ""
    m = re.fullmatch(r"(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\([\w\-./]+\))?(!)?: (.+)", first)
    issues = []
    if not m:
        issues.append("start with a type like feat:, fix:, docs: (optionally feat(scope):)")
    if len(first) > 72:
        issues.append(f"keep the first line under 72 characters (it's {len(first)})")
    if first.endswith("."):
        issues.append("no full stop at the end of the first line")
    return "Looks good." if not issues else "Suggestions: " + "; ".join(issues) + "."


@tool(C, ex={"text": "Fix login bug on Safari #123"}, keys="branch name git make slug")
def branch_name(text: str, kind: Literal["feature", "fix", "chore", "docs"] = "feature") -> str:
    """A tidy git branch name from a description."""
    slug = "-".join(re.findall(r"[a-z0-9]+", text.lower()))[:50].strip("-")
    return f"{kind}/{slug}"


@tool(C, ex={"css": "body {\n  color: red;  /* main */\n  margin: 0 ;\n}\n"}, keys="css minify compress")
def minify_css(css: str) -> str:
    """Minify CSS."""
    c = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    c = re.sub(r"\s+", " ", c)
    c = re.sub(r"\s*([{}:;,>])\s*", r"\1", c)
    return c.replace(";}", "}").strip()


@tool(C, ex={"user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"}, keys="user agent parse browser os")
def parse_user_agent(user_agent: str) -> str:
    """Which browser and operating system a User-Agent string describes."""
    ua = user_agent
    browser = next((n for p, n in ((r"Edg/", "Edge"), (r"OPR/", "Opera"), (r"SamsungBrowser", "Samsung Internet"), (r"Chrome/", "Chrome"),
                                   (r"Firefox/", "Firefox"), (r"Safari/", "Safari")) if re.search(p, ua)), "unknown browser")
    ver = re.search({"Edge": r"Edg/([\d.]+)", "Opera": r"OPR/([\d.]+)", "Chrome": r"Chrome/([\d.]+)", "Firefox": r"Firefox/([\d.]+)",
                     "Safari": r"Version/([\d.]+)"}.get(browser, r"$^"), ua)
    os_ = next((n for p, n in ((r"Windows NT 10", "Windows 10/11"), (r"Android ([\d.]+)", "Android"), (r"iPhone OS ([\d_]+)", "iOS"),
                               (r"Mac OS X", "macOS"), (r"Linux", "Linux")) if re.search(p, ua)), "unknown OS")
    return f"{browser} {ver.group(1) if ver else ''} on {os_}{' (mobile)' if 'Mobile' in ua else ''}".replace("  ", " ")


@tool(C, ex={"username": "admin", "password": "example"}, keys="basic auth header authorization encode")
def basic_auth_header(username: str, password: str) -> str:
    """The HTTP Basic Authorization header for a username and password (for testing your own APIs)."""
    import base64
    return "Authorization: Basic " + base64.b64encode(f"{username}:{password}".encode()).decode()


@tool(C, ex={}, keys="workspaces projects my folders echo")
def list_workspaces(ctx=None) -> dict:
    """Your project folders set in Echo's Settings (Workspaces)."""
    ws = getattr(ctx, "workspaces", None) or {}
    return ws or {"note": "No workspaces yet. Add them in Echo Settings → Workspaces (name=path; …)."}


@tool(C, keys="localhost open dev server browser port")
def open_localhost(port: int, path: str = "/") -> str:
    """Open your local dev server (http://localhost:PORT) in the browser."""
    from .. import control
    if not 1 <= port <= 65535:
        raise ToolError("ports go from 1 to 65535")
    url = f"http://localhost:{port}/{path.lstrip('/')}"
    control.open_url(url)
    return f"Opened {url}."


@tool(C, ex={"text": "<div><p>Hi</p></div>"}, keys="html validate tags balanced check")
def html_tag_check(text: str) -> str:
    """Check that HTML tags are balanced (finds unclosed or stray closing tags)."""
    void = {"br", "img", "hr", "input", "meta", "link", "area", "base", "col", "embed", "source", "track", "wbr"}
    stack, problems = [], []
    for m in re.finditer(r"<(/?)([a-zA-Z][\w-]*)[^>]*?(/?)>", text):
        close, tag, selfclose = m.group(1), m.group(2).lower(), m.group(3)
        if tag in void or selfclose:
            continue
        if not close:
            stack.append(tag)
        elif stack and stack[-1] == tag:
            stack.pop()
        else:
            problems.append(f"stray </{tag}>")
    problems += [f"unclosed <{t}>" for t in stack]
    return "Tags are balanced." if not problems else "Problems: " + ", ".join(problems[:20])
