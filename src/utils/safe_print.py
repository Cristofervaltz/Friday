"""Safe print utility for Windows GUI and non-UTF-8 console environments."""

from __future__ import annotations

import sys
from typing import Any


def safe_print(*args: object, **kwargs: Any) -> None:
    """Print that never crashes, even without a console or on non-UTF-8 locales.

    Handles three failure modes common on Windows:
    1. sys.stdout is None (launched via pythonw.exe or as a GUI sidecar)
    2. UnicodeEncodeError (Cyrillic/emoji on cp1252/cp866 consoles)
    3. OSError (broken pipe, closed handle, etc.)
    """
    target = kwargs.get("file")
    if target is None:
        target = sys.stdout

    if target is None:
        return

    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        encoding = getattr(target, "encoding", None) or "ascii"
        safe_args = []
        for a in args:
            text = str(a)
            try:
                safe_args.append(
                    text.encode(encoding, errors="replace").decode(
                        encoding, errors="replace"
                    )
                )
            except Exception:
                safe_args.append(text.encode("ascii", errors="replace").decode("ascii"))
        try:
            print(*safe_args, **kwargs)
        except Exception:
            pass
    except OSError:
        # stdout handle is invalid (GUI mode, closed pipe)
        pass
    except Exception:
        pass
