import os
import subprocess
import shutil
from pathlib import Path

def build_sidecar():
    print("Building Python Sidecar using PyInstaller...")
    
    # Run PyInstaller
    subprocess.run(
        ["pyinstaller", "--onefile", "--paths", ".", "--name", "friday-api", "scripts/friday_sidecar.py"],
        check=True
    )
    
    # Tauri expects the binary to be named with the target triple
    # For Windows 64-bit, it's typically x86_64-pc-windows-msvc
    # We will hardcode this for now since we are on Windows 64-bit
    target_triple = "x86_64-pc-windows-msvc"
    
    source_exe = Path("dist/friday-api.exe")
    if not source_exe.exists():
        raise RuntimeError(f"PyInstaller failed to create {source_exe}")
        
    dest_dir = Path("src/ui/src-tauri/binaries")
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    dest_exe = dest_dir / f"friday-api-{target_triple}.exe"
    
    print(f"Copying {source_exe} to {dest_exe}")
    shutil.copy2(source_exe, dest_exe)
    
    print("Sidecar build complete!")

if __name__ == "__main__":
    build_sidecar()
