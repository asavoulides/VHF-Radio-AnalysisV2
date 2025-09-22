#!/usr/bin/env python3
"""
Police Scanner Dashboard Launcher

Simple launcher for the consolidated web dashboard.
"""

import subprocess
import sys
from pathlib import Path


def main():
    """Launch the consolidated scanner dashboard"""
    dashboard_file = Path("C:\\Users\\alexa\\OneDrive\\Desktop\\Folders\\Scripts\\Python\\Local Police Scanner Analysis\\scanner_dashboard.py")

    if not dashboard_file.exists():
        print("❌ Dashboard file not found!")
        sys.exit(1)

    print("🌐 Root: http://localhost:4000")
    print("⏹️ Press Ctrl+C to stop")
    print()

    try:
        # Use the virtual environment Python
        python_exe = Path(".venv/Scripts/python.exe")
        if python_exe.exists():
            subprocess.run([str(python_exe), "scanner_dashboard.py"], check=True)
        else:
            subprocess.run([sys.executable, "scanner_dashboard.py"], check=True)
    except KeyboardInterrupt:
        print("\n🛑 Dashboard stopped by user")
    except Exception as e:
        print(f"❌ Error launching dashboard: {e}")


if __name__ == "__main__":
    main()
