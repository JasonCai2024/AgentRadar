"""Build AgentRadar into a standalone executable using PyInstaller.
"""

import os
import sys
import shutil
import PyInstaller.__main__

def build():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.abspath(os.path.join(script_dir, ".."))
    main_py = os.path.join(root_dir, "src", "main.py")
    icon_ico = os.path.join(root_dir, "assets", "icon.ico")
    assets_dir = os.path.join(root_dir, "assets")

    print(f"Building AgentRadar executable...")
    print(f"Root: {root_dir}")
    print(f"Main: {main_py}")
    print(f"Icon: {icon_ico}")

    dist_dir = os.path.join(root_dir, "dist")
    build_dir = os.path.join(root_dir, "build")

    args = [
        main_py,
        "--name=AgentRadar",
        "--onefile",
        "--noconsole",
        f"--icon={icon_ico}",
        f"--add-data={assets_dir};assets",
        f"--distpath={dist_dir}",
        f"--workpath={build_dir}",
        "--clean",
        "--noconfirm",
    ]

    PyInstaller.__main__.run(args)

    output_exe = os.path.join(dist_dir, "AgentRadar.exe")
    if os.path.exists(output_exe):
        sz_mb = os.path.getsize(output_exe) / (1024 * 1024)
        print("\n" + "=" * 60)
        print(f"BUILD SUCCESS: {output_exe} ({sz_mb:.2f} MB)")
        print("=" * 60)
    else:
        print("\nBUILD FAILED: Output executable not found.")

if __name__ == "__main__":
    build()
