"""Entry point for the Friday sidecar (used by Tauri)."""

import sys
import os
import subprocess
from pathlib import Path

def main():
    print("Starting Friday sidecar (thin wrapper)...")
    
    # Tauri sets the CWD differently depending on whether it's run in dev mode, 
    # as a compiled app.exe, or from an MSI installed directory.
    # We will search up the tree for the 'src' directory.
    
    current_dir = Path(os.getcwd()).resolve()
    project_root = current_dir
    
    while project_root.parent != project_root:
        if (project_root / "src" / "api" / "server.py").exists():
            break
        project_root = project_root.parent
    
    if not (project_root / "src" / "api" / "server.py").exists():
        # Fallback to hardcoded path for local dev if not found
        project_root = Path(r"C:\Users\Klim\OneDrive\Desktop\Friday")

    try:
        print(f"Launching API server in {project_root}")
        process = subprocess.Popen(
            ["python", "-m", "src.api.server"],
            cwd=str(project_root)
        )
        process.wait()
    except KeyboardInterrupt:
        print("Sidecar stopped.")
        if 'process' in locals():
            process.terminate()

if __name__ == "__main__":
    main()
