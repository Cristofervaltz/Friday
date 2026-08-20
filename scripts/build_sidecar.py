import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


def get_target_triple() -> str:
    """Detect the host target triple using rustc or platform fallback."""
    try:
        output = subprocess.check_output(["rustc", "-vV"], text=True)
        for line in output.splitlines():
            if line.startswith("host:"):
                return line.split(":", 1)[1].strip()
    except Exception:
        pass

    # Fallback based on platform and architecture
    system = platform.system().lower()
    machine = platform.machine().lower()

    if machine in ("x86_64", "amd64"):
        arch = "x86_64"
    elif machine in ("aarch64", "arm64"):
        arch = "aarch64"
    elif machine in ("i386", "i686", "x86"):
        arch = "i686"
    elif machine.startswith("arm"):
        arch = "armv7"
    else:
        arch = machine

    if system == "windows":
        return f"{arch}-pc-windows-msvc"
    elif system == "darwin":
        return f"{arch}-apple-darwin"
    elif system == "linux":
        return f"{arch}-unknown-linux-gnu"
    return f"{arch}-unknown-{system}"


def build_sidecar() -> None:
    print("Building Python Sidecar using PyInstaller...")

    # Run PyInstaller
    subprocess.run(
        [
            "pyinstaller",
            "--onefile",
            "--clean",
            "--paths",
            ".",
            "--hidden-import",
            "pyaudio",
            "--hidden-import",
            "speech_recognition",
            "--hidden-import",
            "pygame",
            "--hidden-import",
            "edge_tts",
            "--collect-all",
            "vosk",
            "--collect-all",
            "sounddevice",
            "--add-data",
            f"assets{os.pathsep}assets",
            "--name",
            "friday-api",
            "scripts/friday_sidecar.py",
        ],
        check=True,
    )

    # Tauri expects the binary to be named with the target triple
    target_triple = get_target_triple()
    exe_suffix = ".exe" if sys.platform == "win32" else ""

    source_exe = Path(f"dist/friday-api{exe_suffix}")
    if not source_exe.exists():
        raise RuntimeError(f"PyInstaller failed to create {source_exe}")

    dest_dir = Path("src/ui/src-tauri/binaries")
    dest_dir.mkdir(parents=True, exist_ok=True)

    dest_exe = dest_dir / f"friday-api-{target_triple}{exe_suffix}"

    print(f"Copying {source_exe} to {dest_exe}")
    shutil.copy2(source_exe, dest_exe)

    print("Sidecar build complete!")


if __name__ == "__main__":
    build_sidecar()
