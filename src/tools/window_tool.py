"""Window management tool for Friday on Windows desktop."""

from __future__ import annotations

import logging
from typing import Any

from .base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


def _ensure_dpi_aware() -> None:
    """Ensure process is per-monitor DPI aware on Windows to avoid coordinate virtualization."""
    try:
        import ctypes

        # Try Per-Monitor V2 (Windows 10 1703+)
        try:
            ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
            return
        except Exception:
            pass

        # Try Per-Monitor (Windows 8.1+)
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
            return
        except Exception:
            pass

        # Try System DPI Aware (Windows Vista+)
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass
    except Exception:
        pass


def _get_monitor_work_area(window: Any, pyautogui: Any) -> tuple[int, int, int, int]:
    """Get the bounding work area (x, y, width, height) of the monitor containing the window.

    Uses the Windows Win32 API if available (accounting for multi-monitor offsets,
    taskbar exclusion, per-monitor DPI scaling, and minimized windows),
    falling back to pyautogui.size().
    """
    _ensure_dpi_aware()
    try:
        import ctypes
        import ctypes.wintypes

        class RECT(ctypes.Structure):
            _fields_ = [
                ("left", ctypes.c_long),
                ("top", ctypes.c_long),
                ("right", ctypes.c_long),
                ("bottom", ctypes.c_long),
            ]

        class MONITORINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", ctypes.wintypes.DWORD),
                ("rcMonitor", RECT),
                ("rcWork", RECT),
                ("dwFlags", ctypes.wintypes.DWORD),
            ]

        user32 = ctypes.windll.user32
        hmon = None

        # Try getting monitor from HWND first (accurate for minimized/restored windows)
        hwnd = getattr(window, "_hWnd", None) or getattr(window, "hwnd", None)
        if hwnd:
            try:
                hmon = user32.MonitorFromWindow(ctypes.wintypes.HWND(int(hwnd)), 2)
            except Exception:
                hmon = None

        if not hmon:
            win_left = getattr(window, "left", 0)
            win_top = getattr(window, "top", 0)
            win_w = getattr(window, "width", 800)
            win_h = getattr(window, "height", 600)
            center_x = win_left + win_w // 2
            center_y = win_top + win_h // 2
            # MONITOR_DEFAULTTONEAREST = 2
            hmon = user32.MonitorFromPoint(ctypes.wintypes.POINT(center_x, center_y), 2)

        if hmon:
            mi = MONITORINFO()
            mi.cbSize = ctypes.sizeof(MONITORINFO)
            if user32.GetMonitorInfoW(hmon, ctypes.byref(mi)):
                work_x = int(mi.rcWork.left)
                work_y = int(mi.rcWork.top)
                work_w = int(mi.rcWork.right - mi.rcWork.left)
                work_h = int(mi.rcWork.bottom - mi.rcWork.top)
                if work_w > 0 and work_h > 0:
                    return work_x, work_y, work_w, work_h
    except Exception as exc:
        logger.debug(f"Failed to query monitor work area via Win32: {exc}")

    # Fallback to pyautogui.size()
    try:
        screen_size = pyautogui.size()
        if hasattr(screen_size, "width") and hasattr(screen_size, "height"):
            return 0, 0, int(screen_size.width), int(screen_size.height)
        if isinstance(screen_size, (tuple, list)) and len(screen_size) >= 2:
            return 0, 0, int(screen_size[0]), int(screen_size[1])
        return 0, 0, 1920, 1080
    except Exception:
        return 0, 0, 1920, 1080


class WindowManagementTool(BaseTool):
    """Tool to manage and control active desktop application windows on Windows."""

    @property
    def name(self) -> str:
        return "manage_window"

    @property
    def description(self) -> str:
        return (
            "Manage and control desktop application windows on Windows. "
            "Can list open windows, minimize, maximize, restore, activate/focus, "
            "close, move/resize, and snap windows to parts of the screen "
            "(left, right, top, bottom, top-left, top-right, bottom-left, bottom-right, center)."
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "list",
                        "minimize",
                        "maximize",
                        "restore",
                        "activate",
                        "close",
                        "snap",
                        "move_resize",
                    ],
                    "description": "The window operation to perform.",
                },
                "title": {
                    "type": "string",
                    "description": (
                        "Window title or substring of the title to match. "
                        "Required for all actions except 'list'."
                    ),
                },
                "snap_position": {
                    "type": "string",
                    "enum": [
                        "left",
                        "right",
                        "top",
                        "bottom",
                        "top-left",
                        "top-right",
                        "bottom-left",
                        "bottom-right",
                        "center",
                        "maximize",
                    ],
                    "description": "Screen position to snap to when action is 'snap'.",
                },
                "x": {
                    "type": "integer",
                    "description": "X coordinate in pixels for 'move_resize'.",
                },
                "y": {
                    "type": "integer",
                    "description": "Y coordinate in pixels for 'move_resize'.",
                },
                "width": {
                    "type": "integer",
                    "description": "Window width in pixels for 'move_resize'.",
                },
                "height": {
                    "type": "integer",
                    "description": "Window height in pixels for 'move_resize'.",
                },
            },
            "required": ["action"],
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        """Execute window management action.

        Args:
            **kwargs: Tool parameters.

        Returns:
            ToolResult with operation status or list of windows.
        """
        action = kwargs.get("action")
        if not action or not str(action).strip():
            return ToolResult(success=False, error="Missing required parameter: action")

        action_str = str(action).strip().lower()
        valid_actions = {
            "list",
            "minimize",
            "maximize",
            "restore",
            "activate",
            "close",
            "snap",
            "move_resize",
        }
        if action_str not in valid_actions:
            return ToolResult(
                success=False,
                error=(
                    f"Invalid action '{action_str}'. Must be one of: "
                    f"{', '.join(sorted(valid_actions))}"
                ),
            )

        try:
            import pyautogui
            import pygetwindow as gw  # type: ignore[import-untyped]
        except (ImportError, Exception) as exc:
            return ToolResult(
                success=False,
                error=f"Window management dependencies not available: {exc}",
            )

        try:
            if action_str == "list":
                return self._list_windows(gw)

            title = kwargs.get("title")
            if not title or not str(title).strip():
                return ToolResult(
                    success=False,
                    error=f"Missing required parameter 'title' for action '{action_str}'.",
                )

            title_str = str(title).strip()
            target_window = self._find_window(gw, title_str)
            if not target_window:
                return ToolResult(
                    success=False,
                    error=f"No open window found matching title: '{title_str}'",
                )

            if action_str == "minimize":
                target_window.minimize()
                return ToolResult(
                    success=True,
                    output=f"Successfully minimized window '{target_window.title}'.",
                )

            if action_str == "maximize":
                target_window.maximize()
                return ToolResult(
                    success=True,
                    output=f"Successfully maximized window '{target_window.title}'.",
                )

            if action_str == "restore":
                target_window.restore()
                return ToolResult(
                    success=True,
                    output=f"Successfully restored window '{target_window.title}'.",
                )

            if action_str == "activate":
                try:
                    if getattr(target_window, "isMinimized", False):
                        target_window.restore()
                    target_window.activate()
                except Exception as e:
                    logger.warning(f"Could not directly activate window: {e}")
                    target_window.restore()
                return ToolResult(
                    success=True,
                    output=f"Successfully activated window '{target_window.title}'.",
                )

            if action_str == "close":
                target_window.close()
                return ToolResult(
                    success=True,
                    output=f"Successfully closed window '{target_window.title}'.",
                )

            if action_str == "snap":
                snap_pos = kwargs.get("snap_position")
                if not snap_pos or not str(snap_pos).strip():
                    return ToolResult(
                        success=False,
                        error="Missing required parameter 'snap_position' for snap action.",
                    )
                return self._snap_window(
                    target_window,
                    str(snap_pos).strip().lower().replace("_", "-"),
                    pyautogui,
                )

            if action_str == "move_resize":
                return self._move_resize_window(target_window, kwargs)

            return ToolResult(success=False, error=f"Unhandled action '{action_str}'")

        except Exception as exc:
            logger.exception(f"Window management error on action '{action_str}'")
            return ToolResult(
                success=False,
                error=f"Window management action '{action_str}' failed: {exc}",
            )

    def _list_windows(self, gw: Any) -> ToolResult:
        """List all open desktop windows with non-empty titles."""
        try:
            all_windows = gw.getAllWindows()
        except Exception as exc:
            return ToolResult(
                success=False,
                error=f"Failed to retrieve desktop windows: {exc}",
            )

        windows = [
            w for w in all_windows if getattr(w, "title", None) and str(w.title).strip()
        ]

        if not windows:
            return ToolResult(success=True, output="No active desktop windows found.")

        lines = [f"Open Windows (total: {len(windows)}):"]
        for idx, w in enumerate(windows, 1):
            status_tags: list[str] = []
            if getattr(w, "isActive", False):
                status_tags.append("Active")
            if getattr(w, "isMaximized", False):
                status_tags.append("Maximized")
            if getattr(w, "isMinimized", False):
                status_tags.append("Minimized")

            status_str = f" [{', '.join(status_tags)}]" if status_tags else ""
            pos_str = (
                f"(x={getattr(w, 'left', 0)}, y={getattr(w, 'top', 0)}, "
                f"w={getattr(w, 'width', 0)}, h={getattr(w, 'height', 0)})"
            )
            lines.append(f'{idx}. "{w.title}"{status_str} {pos_str}')

        return ToolResult(success=True, output="\n".join(lines))

    def _find_window(self, gw: Any, title: str) -> Any | None:
        """Find a window matching the title (exact match, substring, or token match)."""
        all_windows = [
            w
            for w in gw.getAllWindows()
            if getattr(w, "title", None) and str(w.title).strip()
        ]

        target_lower = title.strip().lower()

        # 1. Exact match
        for w in all_windows:
            if w.title.strip().lower() == target_lower:
                return w

        # 2. Substring match
        for w in all_windows:
            if target_lower in w.title.lower():
                return w

        # 3. Word tokens match (all query words present in window title)
        query_words = [q for q in target_lower.split() if len(q) > 1]
        if query_words:
            for w in all_windows:
                w_title_lower = w.title.lower()
                if all(word in w_title_lower for word in query_words):
                    return w

        return None

    def _snap_window(self, window: Any, snap_pos: str, pyautogui: Any) -> ToolResult:
        """Snap a window to a defined region of the screen."""
        snap_norm = snap_pos.strip().lower().replace("_", "-")
        valid_snaps = {
            "left",
            "right",
            "top",
            "bottom",
            "top-left",
            "top-right",
            "bottom-left",
            "bottom-right",
            "center",
            "maximize",
        }
        if snap_norm not in valid_snaps:
            return ToolResult(
                success=False,
                error=(
                    f"Invalid snap_position '{snap_pos}'. Must be one of: "
                    f"{', '.join(sorted(valid_snaps))}"
                ),
            )

        if snap_norm == "maximize":
            window.maximize()
            return ToolResult(
                success=True,
                output=f"Successfully maximized window '{window.title}'.",
            )

        # Restore window if maximized or minimized before moving/resizing
        if getattr(window, "isMaximized", False) or getattr(
            window, "isMinimized", False
        ):
            window.restore()

        work_x, work_y, work_w, work_h = _get_monitor_work_area(window, pyautogui)

        half_w = work_w // 2
        half_h = work_h // 2

        pos_map = {
            "left": (work_x, work_y, half_w, work_h),
            "right": (work_x + half_w, work_y, half_w, work_h),
            "top": (work_x, work_y, work_w, half_h),
            "bottom": (work_x, work_y + half_h, work_w, half_h),
            "top-left": (work_x, work_y, half_w, half_h),
            "top-right": (work_x + half_w, work_y, half_w, half_h),
            "bottom-left": (work_x, work_y + half_h, half_w, half_h),
            "bottom-right": (work_x + half_w, work_y + half_h, half_w, half_h),
            "center": (work_x + work_w // 4, work_y + work_h // 4, half_w, half_h),
        }

        x, y, w, h = pos_map[snap_norm]
        window.moveTo(x, y)
        window.resizeTo(w, h)

        return ToolResult(
            success=True,
            output=(
                f"Successfully snapped window '{window.title}' to '{snap_norm}' "
                f"(x={x}, y={y}, width={w}, height={h})."
            ),
        )

    def _move_resize_window(self, window: Any, kwargs: dict[str, Any]) -> ToolResult:
        """Move and/or resize a window with custom pixel coordinates."""
        if getattr(window, "isMaximized", False) or getattr(
            window, "isMinimized", False
        ):
            window.restore()

        x = kwargs.get("x")
        y = kwargs.get("y")
        w = kwargs.get("width")
        h = kwargs.get("height")

        new_x: int | None = None
        new_y: int | None = None
        new_w: int | None = None
        new_h: int | None = None

        if x is not None:
            try:
                new_x = int(x)
            except (ValueError, TypeError):
                return ToolResult(
                    success=False,
                    error=f"Window x coordinate must be an integer, got: {x}",
                )

        if y is not None:
            try:
                new_y = int(y)
            except (ValueError, TypeError):
                return ToolResult(
                    success=False,
                    error=f"Window y coordinate must be an integer, got: {y}",
                )

        if w is not None:
            try:
                new_w = int(w)
                if new_w <= 0:
                    return ToolResult(
                        success=False,
                        error=f"Window width must be a positive integer, got: {w}",
                    )
            except (ValueError, TypeError):
                return ToolResult(
                    success=False,
                    error=f"Window width must be an integer, got: {w}",
                )

        if h is not None:
            try:
                new_h = int(h)
                if new_h <= 0:
                    return ToolResult(
                        success=False,
                        error=f"Window height must be a positive integer, got: {h}",
                    )
            except (ValueError, TypeError):
                return ToolResult(
                    success=False,
                    error=f"Window height must be an integer, got: {h}",
                )

        if new_x is None and new_y is None and new_w is None and new_h is None:
            return ToolResult(
                success=False,
                error="For 'move_resize', at least one of (x, y, width, height) must be specified.",
            )

        if new_x is not None or new_y is not None:
            final_x = new_x if new_x is not None else getattr(window, "left", 0)
            final_y = new_y if new_y is not None else getattr(window, "top", 0)
            window.moveTo(final_x, final_y)

        if new_w is not None or new_h is not None:
            final_w = new_w if new_w is not None else getattr(window, "width", 800)
            final_h = new_h if new_h is not None else getattr(window, "height", 600)
            window.resizeTo(final_w, final_h)

        return ToolResult(
            success=True,
            output=f"Successfully adjusted position/size of window '{window.title}'.",
        )
