"""Start EchoDesktop: python -m echo_desktop (from desktop/EchoDesktop)."""
import sys
import traceback
from datetime import datetime
from pathlib import Path


def record_location() -> None:
    """Write where Echo runs from, so the ECHO website's bridge finds it wherever the zip was unzipped."""
    from . import storage
    try:
        storage.APP_DIR.mkdir(parents=True, exist_ok=True)
        (storage.APP_DIR / "location.txt").write_text(str(Path(__file__).resolve().parents[1]), encoding="utf-8")
    except OSError:
        pass


def log_path() -> Path:
    from . import storage
    return storage.APP_DIR / "echo.log"


def log_crash(where: str) -> Path:
    """Echo runs without a console (pythonw): an error that stops it is written to %APPDATA%\\EchoDesktop\\echo.log."""
    path = log_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"\n=== {datetime.now():%Y-%m-%d %H:%M:%S} {where} (Python {sys.version.split()[0]})\n")
            f.write(traceback.format_exc())
        lines = path.read_text("utf-8").splitlines()
        if len(lines) > 2000:                                   # keep the log small
            path.write_text("\n".join(lines[-1000:]) + "\n", encoding="utf-8")
    except OSError:
        pass
    return path


def already_running() -> bool:
    """One Echo at a time: a second start (desktop icon while the sign-in copy runs) would write the same encrypted
    files from two processes. A named Windows mutex tells."""
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        global _MUTEX
        _MUTEX = kernel32.CreateMutexW(None, False, "Local\\EchoDesktop-single-instance")
        return kernel32.GetLastError() == 183                # ERROR_ALREADY_EXISTS
    except (AttributeError, OSError):
        return False


_MUTEX = None


def main() -> None:
    if already_running():
        try:
            import tkinter.messagebox as mb
            mb.showinfo("Echo", "Echo is already running: look for the orb near the bottom-right of your screen.")
        except Exception:
            pass
        return
    record_location()
    try:
        from .ui import App
        App().run()
    except Exception:
        path = log_crash("Echo stopped")
        try:
            import tkinter.messagebox as mb
            mb.showerror("Echo", f"Echo hit a problem and had to stop. The details are in:\n{path}\n\n"
                                 "Start Echo again from the Start menu. If it keeps happening, send that file to whoever "
                                 "gave you Echo.")
        except Exception:
            pass
        raise


if __name__ == "__main__":
    main()
