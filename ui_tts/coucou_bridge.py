"""Floating top-of-screen status bar for Sound OS. Never raises (CONTRACT Rule 7)."""

import queue
import threading

_q = queue.Queue()
_lock = threading.Lock()
_thread = None
_coucou = None
_coucou_checked = False

GREEN, RED, WHITE = "#34c759", "#ff3b30", "#ffffff"


# ---------- Coucou island (optional) ----------
def _try_coucou(name, *args):
    """Call coucou.<name>(*args) if a 'coucou' module with it exists. True if handled."""
    global _coucou, _coucou_checked
    try:
        if not _coucou_checked:
            _coucou_checked = True
            try:
                import coucou  # ASSUMPTION: module name and function names
                _coucou = coucou
            except Exception:
                _coucou = None
        fn = getattr(_coucou, name, None) if _coucou else None
        if callable(fn):
            fn(*args)
            return True
    except Exception:
        pass
    return False


# ---------- Tkinter bar (runs in its own thread) ----------
def _run():
    try:
        import tkinter as tk
        root = tk.Tk()
    except Exception:
        return  # no display / no tkinter: stay silent

    try:
        root.withdraw()
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        try:
            root.attributes("-alpha", 0.95)
        except Exception:
            pass

        label = tk.Label(root, text="", font=("Sans", 14, "bold"),
                         fg=WHITE, bg="#202124", padx=28, pady=10)
        label.pack()
        timer = [None]

        def place():
            root.update_idletasks()
            w, h = root.winfo_reqwidth(), root.winfo_reqheight()
            x = (root.winfo_screenwidth() - w) // 2
            root.geometry(f"{w}x{h}+{x}+16")

        def cancel_timer():
            if timer[0] is not None:
                try:
                    root.after_cancel(timer[0])
                except Exception:
                    pass
                timer[0] = None

        def show(text, color=WHITE):
            cancel_timer()
            label.config(text=text, fg=color)
            place()
            root.deiconify()
            root.lift()
            root.attributes("-topmost", True)

        def hide():
            timer[0] = None
            root.withdraw()

        def handle(cmd, arg):
            if cmd == "wake":
                show("Sound OS: Listening...")
            elif cmd == "heard":
                show(f"Heard: {arg}")
            elif cmd == "done":
                show("\u2714  Done" if arg else "\u2718  Failed", GREEN if arg else RED)
                timer[0] = root.after(2000, hide)

        def poll():
            try:
                while True:
                    cmd, arg = _q.get_nowait()
                    try:
                        handle(cmd, arg)
                    except Exception:
                        pass
            except queue.Empty:
                pass
            root.after(50, poll)

        poll()
        root.mainloop()
    except Exception:
        pass


def _send(cmd, arg=None):
    global _thread
    try:
        with _lock:
            if _thread is None or not _thread.is_alive():
                _thread = threading.Thread(target=_run, daemon=True)
                _thread.start()
        _q.put((cmd, arg))
    except Exception:
        pass


# ---------- Public API ----------
def on_wake() -> None:
    try:
        if not _try_coucou("on_wake"):
            _send("wake")
    except Exception:
        pass


def on_heard(text) -> None:
    try:
        text = str(text)
        text = text if len(text) <= 80 else text[:77] + "..."
        if not _try_coucou("on_heard", text):
            _send("heard", text)
    except Exception:
        pass


def on_done(success) -> None:
    try:
        ok = bool(success)
        if not _try_coucou("on_done", ok):
            _send("done", ok)
    except Exception:
        pass
