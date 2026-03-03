import os
import shutil
import subprocess
import time
from datetime import datetime

exe_name = "NFC_Writer_Tool.exe"
dist_dir = "dist"
exe_path = os.path.join(dist_dir, exe_name)

# Ensure dist dir exists
if not os.path.exists(dist_dir):
    os.makedirs(dist_dir)

print(f"Killing running instances of {exe_name}...")
os.system(f"taskkill /F /IM {exe_name} >nul 2>&1")
time.sleep(1)

print("Running PyInstaller...")
# Use python -m PyInstaller to avoid PATH issues
# Note: We are NOT bundling the DLL inside the EXE because ctypes loading from temp _MEIPASS requires code changes.
# Instead, we will copy the DLL next to the EXE.
cmd = 'python -m PyInstaller --onefile --noconsole --add-data "ntag424_manager.py;." gui_writer.py --name "NFC_Writer_Tool" --clean --noconfirm'
try:
    subprocess.check_call(cmd, shell=True)
except subprocess.CalledProcessError as e:
    print(f"Build failed: {e}")
    exit(1)

# Copy dependencies to dist folder
dependencies = ["OUR_MIFARE.dll", "syssetup.ini"]
for dep in dependencies:
    if os.path.exists(dep):
        shutil.copy(dep, dist_dir)
        print(f"Copied {dep} to {dist_dir}")
    else:
        print(f"Warning: {dep} not found in current directory!")

if os.path.exists(exe_path):
    mod_time = os.path.getmtime(exe_path)
    dt = datetime.fromtimestamp(mod_time)
    print(f"\nSUCCESS: {exe_path} created at {dt}")
    
    # Check if it's recent (within 1 minute)
    now = datetime.now()
    diff = (now - dt).total_seconds()
    if diff < 60:
        print("✓ Timestamp is CURRENT.")
    else:
        print(f"⚠ Timestamp is OLD! (Diff: {diff}s)")
else:
    print("\nFAILURE: EXE not found!")
