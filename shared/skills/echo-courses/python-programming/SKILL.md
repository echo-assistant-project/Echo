---
name: python-programming
description: Learn, write, read and fix Python code — from first steps to clean, tested scripts. Use for "teach me Python", "write a Python script that…", "what does this Python error mean", "how do I loop / read a file / use a dictionary".
audience: developers
field: Technology
courses: CS50's Introduction to Programming with Python (Harvard) | https://cs50.harvard.edu/python/ ; Python for Everybody (University of Michigan, Dr. Chuck) | https://www.py4e.com/ ; Google's Python Class | https://developers.google.com/edu/python ; The official Python Tutorial | https://docs.python.org/3/tutorial/
source: Echo (written for Echo from these courses' syllabi)
license: same as Echo
---

# Python programming

## 1. Set up and run code
- Install Python 3 from python.org (Windows: tick "Add Python to PATH"). Check with `py --version`.
- Run a file with `py script.py`; try ideas in the interactive prompt (`py`) or a notebook.
- One folder per project, with a virtual environment: `py -m venv .venv`, then `.venv\Scripts\activate`, then `pip install …`.

## 2. The core ideas, in the order courses teach them
1. **Values and variables**: numbers, strings, `True/False`, `None`; names point to values.
2. **Input/output**: `print()`, `input()`, f-strings: `f"Total: {total:.2f}"`.
3. **Decisions**: `if / elif / else`, comparison and `and/or/not`.
4. **Loops**: `for item in items`, `range()`, `while`; `break` and `continue`.
5. **Functions**: `def`, parameters, `return`; one job per function.
6. **Collections**: list (ordered), dict (key → value), set (unique), tuple (fixed). Comprehensions: `[x*2 for x in nums if x > 0]`.
7. **Files**: `with open("data.txt", encoding="utf-8") as f:`; `csv` and `json` modules.
8. **Errors**: read the last line of a traceback first; `try/except SpecificError`.
9. **Modules and libraries**: `import`, the standard library first, then `pip` packages.
10. **Classes** when data and behaviour belong together.

## 3. Writing a script for someone
- Ask: input (file? typed? web?), output (screen, file, spreadsheet), and one example.
- Write the smallest working version, run it on the example, then add edge cases (empty file, bad number, missing key).
- Keep it readable: clear names, functions under ~30 lines, a docstring saying what it does.

## 4. Reading an error
- `NameError` — misspelled or undefined name. `TypeError` — wrong kind of value (e.g. adding str + int: use `int()` or `str()`). `IndexError/KeyError` — the item isn't there; check length or use `.get()`. `IndentationError` — mixed spaces/tabs or a missing block. `ModuleNotFoundError` — `pip install` it in the active venv.
- Explain the cause in one sentence, show the fixed line, and say how to avoid it next time.

## 5. Good habits
- Test small pieces: `assert add(2, 2) == 4`, then `pytest` for real projects.
- Use `pathlib` for paths, `logging` instead of many prints, and never hard-code passwords (use environment variables).
- Format with `black`/`ruff`; follow PEP 8 names (`snake_case` functions, `CapWords` classes).

## 6. Practice path
Week 1 basics and loops → week 2 functions and lists/dicts → week 3 files and errors → week 4 a real mini-project (expense tracker, file renamer, web page scraper with permission). Small daily practice beats long weekend sessions.
