#!/usr/bin/env python3
"""
reset_flights.py
Safely backup and clear flight archives/active ledgers and reset flight_count.
Run this while GCS and UAV clients are stopped.
"""
import os
import shutil
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
ARCH = os.path.join(ROOT, "flight_archives")
ACTIVE = os.path.join(ROOT, "active_ledgers")
COUNT_FILE = os.path.join(ROOT, "flight_count.txt")
BACKUP_ROOT = os.path.join(ROOT, "backups")

ts = datetime.now().strftime("%Y%m%d_%H%M%S")
backup_dir = os.path.join(BACKUP_ROOT, f"flight_reset_{ts}")
bak_arch = os.path.join(backup_dir, "flight_archives")
bak_active = os.path.join(backup_dir, "active_ledgers")

os.makedirs(bak_arch, exist_ok=True)
os.makedirs(bak_active, exist_ok=True)

def move_matches(src_dir, pattern_prefix):
    if not os.path.isdir(src_dir):
        return []
    moved = []
    for fname in os.listdir(src_dir):
        if fname.startswith(pattern_prefix) and fname.endswith(".json"):
            src = os.path.join(src_dir, fname)
            dst = os.path.join(backup_dir, os.path.basename(src_dir), fname)
            shutil.move(src, dst)
            moved.append(fname)
    return moved

print("Backing up flight archives and active ledgers to:", backup_dir)
moved_arch = move_matches(ARCH, "Flight_")
moved_active = move_matches(ACTIVE, "flight_")

print(f"Moved {len(moved_arch)} archived flights, {len(moved_active)} active ledgers.")

# Remove count file
if os.path.exists(COUNT_FILE):
    os.remove(COUNT_FILE)
    print("Removed flight_count.txt (will restart numbering at 1).")
else:
    print("No flight_count.txt found (already reset).")

print("Done. You can now start the GCS server. First new flight will be Flight_1.")