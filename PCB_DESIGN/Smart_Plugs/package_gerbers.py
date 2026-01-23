import os
import shutil
import zipfile
from pathlib import Path
from datetime import datetime

# ==========================================
# ⚙️ CONFIGURATION
# ==========================================

# The folder where Altium dumps the files
SOURCE_DIR = "Project Outputs for Smart_Plugs"

# Where you want the clean files to go
OUTPUT_DIR = "Release_Package"

# The name of the zip file to create
ZIP_NAME = f"Smart_Plug_Pro_V1_Gerbers_{datetime.now().strftime('%Y-%m-%d')}"

# List of extensions to include (Standard Altium Extensions)
VALID_GERBER_EXTENSIONS = {
    # --- Copper Layers ---
    '.GTL', '.GBL', 
    # --- Solder Mask ---
    '.GTS', '.GBS',
    # --- Silkscreen ---
    '.GTO', '.GBO',
    # --- Mechanical / Outline ---
    '.GKO', '.GM1', '.GML', '.GM13', '.GM15', # Added GM15 seen in your tree
    # --- Paste Mask ---
    '.GTP', '.GBP',
    # --- Drill Files ---
    '.TXT', '.DRL', '.LDP', '.DRR'
}

# ==========================================
# 🚀 SCRIPT LOGIC
# ==========================================

def collect_files():
    src_path = Path(SOURCE_DIR)
    dest_path = Path(OUTPUT_DIR)
    
    # 1. Check if source exists
    if not src_path.exists():
        print(f"❌ Error: Source folder '{SOURCE_DIR}' not found!")
        return False

    # 2. Clean/Create Destination
    if dest_path.exists():
        shutil.rmtree(dest_path)
    dest_path.mkdir(parents=True)
    
    print(f"📂 Scanning recursively in: {src_path}")
    
    count = 0
    
    # 3. Walk through ALL folders (Recursive search)
    # rglob('*') looks inside BOM, Gerber, NC Drill, etc.
    for file in src_path.rglob('*'):
        if file.is_file():
            
            filename_upper = file.name.upper()
            suffix_upper = file.suffix.upper()
            
            # --- Logic A: Standard Gerber & Drill Files ---
            if suffix_upper in VALID_GERBER_EXTENSIONS:
                shutil.copy2(file, dest_path / file.name)
                print(f"   ✅ Copied Gerber/Drill: {file.name}")
                count += 1
                
            # --- Logic B: Bill of Materials (CSV) ---
            # Looks for 'Bill of Materials' in the name and ensures it is a CSV
            elif suffix_upper == '.CSV' and "BILL OF MATERIALS" in filename_upper:
                shutil.copy2(file, dest_path / file.name)
                print(f"   📋 Copied BOM:          {file.name}")
                count += 1
                
            # --- Logic C: Pick and Place (CSV) ---
            # Looks for 'Pick Place' in the name and ensures it is a CSV
            elif suffix_upper == '.CSV' and "PICK PLACE" in filename_upper:
                shutil.copy2(file, dest_path / file.name)
                print(f"   📍 Copied Pick & Place: {file.name}")
                count += 1

    if count == 0:
        print("⚠️  Warning: No valid files found. Check your Output Job settings.")
        return False
        
    print(f"🎉 Successfully gathered {count} files into '{OUTPUT_DIR}'")
    return True

def create_zip():
    dest_path = Path(OUTPUT_DIR)
    # Define the full path inside the destination folder
    zip_file_path = dest_path / f"{ZIP_NAME}.zip"
    
    print(f"📦 Zipping files to {zip_file_path}...")
    
    with zipfile.ZipFile(zip_file_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file in dest_path.iterdir():
            # CRITICAL: Skip the zip file itself if it's detected in the loop
            if file.name != zip_file_path.name:
                zipf.write(file, file.name)
            
    print(f"🚀 DONE! Ready to upload to PCBWay: {zip_file_path}")

if __name__ == "__main__":
    print("--- 🦅 Altium Gerber Packager (Recursive) ---")
    
    # 1. Collect ALL files (Gerbers, Drill, BOM, PnP) first
    if collect_files():
        # 2. THEN Zip them all together
        create_zip()
        
    print("---------------------------------------------")