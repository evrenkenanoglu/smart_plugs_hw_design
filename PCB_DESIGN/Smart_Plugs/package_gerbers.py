import os
import shutil
import zipfile
from pathlib import Path
from datetime import datetime

# ==========================================
# ⚙️ CONFIGURATION
# ==========================================

# The folder where Altium dumps the files (Check your Altium Project Options)
# Usually: "Project Outputs for <ProjectName>"
SOURCE_DIR = "Project Outputs for Smart_Plugs"

# Where you want the clean files to go
OUTPUT_DIR = "Release_Package"

# The name of the zip file to create
ZIP_NAME = f"Smart_Plug_Pro_V1_Gerbers_{datetime.now().strftime('%Y-%m-%d')}"

# List of extensions to include (Standard Altium Extensions)
VALID_EXTENSIONS = {
    # --- Copper Layers ---
    '.GTL', # Top Layer
    '.GBL', # Bottom Layer
    
    # --- Solder Mask ---
    '.GTS', # Top Solder
    '.GBS', # Bottom Solder
    
    # --- Silkscreen ---
    '.GTO', # Top Overlay
    '.GBO', # Bottom Overlay
    
    # --- Mechanical / Outline ---
    '.GKO', # Keep-Out
    '.GM1', # Mechanical 1 (Often Outline)
    '.GML', # Mechanical Layer (General)
    '.GM13', # Mechanical 13 (3D Bodies sometimes)
    
    # --- Paste Mask (Optional - For Stencil) ---
    '.GTP', # Top Paste
    '.GBP', # Bottom Paste
    
    # --- Drill Files ---
    '.TXT', # ASCII Drill Data
    '.DRL', # Binary Drill Data
    '.LDP', # Layer Pair Drill
    '.DRR', # Drill Report
}

# ==========================================
# 🚀 SCRIPT LOGIC
# ==========================================

def clean_and_copy():
    src_path = Path(SOURCE_DIR)
    dest_path = Path(OUTPUT_DIR)
    
    # 1. Check if source exists
    if not src_path.exists():
        print(f"❌ Error: Source folder '{SOURCE_DIR}' not found!")
        print("   Make sure you ran 'Fabrication Outputs' in Altium first.")
        return False

    # 2. Clean/Create Destination
    if dest_path.exists():
        shutil.rmtree(dest_path)
    dest_path.mkdir(parents=True)
    
    print(f"📂 Scanning: {src_path}")
    
    count = 0
    
    # 3. Walk through folder and copy valid files
    for file in src_path.iterdir():
        if file.is_file():
            # Check extension (case insensitive)
            if file.suffix.upper() in VALID_EXTENSIONS:
                shutil.copy2(file, dest_path / file.name)
                print(f"   ✅ Copied: {file.name}")
                count += 1
            # Special logic for "NC Drill" files if Altium didn't name them .TXT
            elif "Drill" in file.name and file.suffix.upper() in ['.GBR', '.TXT']:
                 shutil.copy2(file, dest_path / file.name)
                 print(f"   ✅ Copied Drill: {file.name}")
                 count += 1

    if count == 0:
        print("⚠️  Warning: No Gerber files found. Did you generate them?")
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

def copy_bom_file():
    src_path = Path(SOURCE_DIR)
    src_bom = src_path / "Smart_Plugs_BOM.csv"
    dest_path = Path(OUTPUT_DIR)
    
    if src_bom.exists():
        shutil.copy2(src_bom, dest_path / src_bom.name)
        print(f"📋 BOM file copied: {src_bom.name}")
    else:
        print("⚠️  Warning: BOM file not found!")

def copy_pick_and_place_file():
    src_path = Path(SOURCE_DIR)
    src_pnp = src_path / "Pick Place for Smart_Plug_PCB.csv"
    dest_path = Path(OUTPUT_DIR)
    
    if src_pnp.exists():
        shutil.copy2(src_pnp, dest_path / src_pnp.name)
        print(f"📍 Pick and Place file copied: {src_pnp.name}")
    else:
        print("⚠️  Warning: Pick and Place file not found!")

if __name__ == "__main__":
    print("--- 🦅 Altium Gerber Packager ---")
    if clean_and_copy():
        create_zip()
    
        copy_bom_file()
        copy_pick_and_place_file()
    

    print("---------------------------------")