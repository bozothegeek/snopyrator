import re
import json
import requests

def convert_combined_databases(dat_url, gamedb_url):
    print("Fetching databases...")
    fg_response = requests.get(gamedb_url)
    gd_data = fg_response.json()
    
    dat_response = requests.get(dat_url)
    dat_content = dat_response.text
    
    # We use a dictionary of lists to group by "First Letters" + CHECKSUM for filtering (
    grouped_entries = {}

    def add_entry(game_id, entry):
        existing_entry = None
        
        # --- STEP 1: Find if the checksum already exists ---
        if not game_id:
            # If game_id is empty, search across ALL groups for the checksum
            for gid, entries in grouped_entries.items():
                found = next((e for e in entries if e['global_checksum'] == entry['global_checksum']), None)
                if found:
                    #print("found : " + found['global_checksum'])
                    existing_entry = found
                    target_game_id = gid  # Keep track of where we found it
                    break
        else:
            # If game_id is provided, look only inside its specific group
            target_game_id = game_id
            if target_game_id in grouped_entries:
                existing_entry = next(
                    (e for e in grouped_entries[target_game_id] if e['global_checksum'] == entry['global_checksum']), 
                    None
                )

        # --- STEP 2: Update or Insert ---
        if existing_entry:
            # TARGET FOUND: This updates the entry inside grouped_entries with the new values
            for key, value in entry.items():
                if value is not None:
                    # print("key : " + value)
                    existing_entry[key] = value
        else:
            # NOT FOUND: Create a new entry
            if not game_id:
                target_game_id = "UNKNOWN"  # Fallback if it's completely new and has no ID
                
            if target_game_id not in grouped_entries:
                grouped_entries[target_game_id] = []
                
            grouped_entries[target_game_id].append(entry)
        
    # --- PHASE 1: Process GameDB ---
    print("PHASE 1: Process GameDB...")
    for outer_id, info in gd_data.items():
        full_title = info.get("release_name")
        if not full_title: 
            continue
        full_title = full_title.strip()
        # print("full_title : " +  full_title)
        
        checksum = info.get("checksum")
        if (not checksum) or (checksum == "0x0000"): 
            continue
        checksum = checksum.strip()
        checksum = checksum[:2] + checksum[2:].upper()
        # print("checksum : " +  checksum)
        
        crc_hex = info.get("crc32")
        if not crc_hex:
            crc_hex = f"0x{outer_id.upper()}"
            if not crc_hex:
                continue
        else:
            crc_hex = crc_hex.strip()
            crc_hex = crc_hex[:2] + crc_hex[2:].upper()
        # print("crc_hex : " +  crc_hex)
        
        # 1. Get the hex string and strip the "0x" prefix
        hex_str = info.get("internal_title")
        if (not hex_str) or (hex_str == "0x000000000000000000000000000000000000000000"): 
            continue
        hex_str = hex_str.strip()[2:]
        # print("hex_str : " +  hex_str)
        # 2. Convert the hex string into a readable ASCII string ("Hu SUPER BOMBERMAN 3 ")
        clean_title = bytes.fromhex(hex_str).decode('ascii', errors='ignore')
        
        # --- SECURE CLEANING ---
        # Remove any leading/trailing whitespaces or raw newline characters first
        clean_title = clean_title.strip()

        if clean_title:
            first_char = clean_title[0]
            # If the first character is not alphanumeric (e.g., \n, \x00, [, #), replace it with a space
            if not first_char.isalnum():
                first_char = " "
        else:
            # Fallback default if the string is completely empty after stripping
            first_char = " "

        # 3. Extract the first character and concatenate with the checksum slice
        game_id = (first_char + checksum[2:6]).upper()
        if not game_id: 
            continue
        else:
            # Force escape any backslash
            game_id = game_id.replace('\\', '\\\\').upper()
        
        full_title = info.get("release_name").strip()
        title = info.get("title").strip()
        
        cartridge_type = info.get("fast_slow_rom").strip() + " " + info.get("rom_type").strip()
        
        region = info.get("region")
        if region: 
            region = region.strip()
            # print("region : " +  region)
        hardware = info.get("hardware")
        hasBattery = "0"
        hasRam = "0"
        if hardware: 
           hardware = hardware.strip()
           # print("hardware : " +  hardware)
           hasBattery = "1" if "Battery" in hardware else "0"
           hasRam = "1" if "RAM" in hardware else "0"
        
        extension = ".sfc"
        
        rom_version = info.get("rom_version").strip()
        entry = {
            "full_title": f"{full_title}{extension}",
            "title": f"{title}",
            "cartridge_type": cartridge_type,
            "ROM_size": "",
            "has_RAM": hasRam,
            "has_Battery": hasBattery,
            "destination": region,
            "ROM_version": rom_version,
            "header_checksum": checksum,
            "global_checksum": crc_hex
        }
        add_entry(game_id, entry)

    # --- PHASE 2: Process Libretro DAT ---
    print("PHASE 2: Process Libretro DAT...")
    game_blocks = dat_content.split('game (')[1:]
    for block in game_blocks:
        crc_match = re.search(r'crc\s+([0-9A-F]{8})', block, re.IGNORECASE)
        if not crc_match: 
            continue

        crc_hex = f"0x{crc_match.group(1).upper()}"
        crc_hex = crc_hex[:2] + crc_hex[2:].upper()
        name_match = re.search(r'name\s+"(.*?)"', block)
        dat_full_title = f"{name_match.group(1)}.sfc"
        

        # Fixed: Move regex search and calculation outside the f-string
        size_match = re.search(r'size\s+(\d+)', block)
        size_bytes = int(size_match.group(1)) if size_match else 0
        if((size_bytes / 1024) >= 1024):
            rom_size_mib = f"{size_bytes // (1024*1024)} MiB"
        else:
            rom_size_mib = f"{size_bytes // (1024)} KiB"
        
        reg_match = re.search(r'region\s+"(.*?)"', block)
        destination = reg_match.group(1) if reg_match else "Unknown"

        entry = {
            "full_title": dat_full_title,
            "title": dat_full_title.replace('.sfc', '').split('(')[0].strip().upper(),
            "cartridge_type": None,
            "ROM_size": rom_size_mib,
            "has_RAM": None,
            "has_Battery": None,
            "destination": destination,
            "ROM_version": None,
            "header_checksum": None,
            "global_checksum": crc_hex
        }
        add_entry(None, entry)

    # --- Configuration Checklist ---
    # Add any patterns here that you want to filter out IF a final version exists
    EXCLUSION_PATTERNS = ["(Beta", "(Proto", "(Demo", "(Sample", "NES Conversion", "Virtual Console", "Switch Online"]

    # --- PHASE 3: Filter and Flatten ---
    print("PHASE 3: Filter and Flatten...")
    final_list = []
    for game_id, entries in grouped_entries.items():
        for e in entries:
            # Check if the title matches any exclusion pattern
            is_trash_version = any(pattern.strip().lower() in e["full_title"].lower() for pattern in EXCLUSION_PATTERNS)
            
            # Hard drop: If it matches an exclusion pattern, throw it away completely
            if is_trash_version:
                continue
                
            final_list.append((game_id, e))

    # --- MANUAL STRING WRITING WITH 8-SPACE INDENTATION ---
    print(f"Writing {len(final_list)} entries to file...")
    with open('snes_roms_info.json', 'w', encoding='utf-8') as f:
        f.write("{\n")
        for i, (game_code, data) in enumerate(final_list):
            raw_json = json.dumps(data, indent=4, ensure_ascii=False)
            lines = raw_json.splitlines()
            
            f.write(f'    "{game_code}":\n')
            for j, line in enumerate(lines):
                if j == 0:
                    f.write('        {\n')
                elif j == len(lines) - 1:
                    f.write('        }')
                else:
                    # Content indented with 12 spaces (8 base + 4 nested)
                    f.write('            ' + line.strip() + '\n')
            
            if i < len(final_list) - 1:
                f.write(",\n")
            else:
                f.write("\n")
        f.write("}")

# Run
url_dat = "https://raw.githubusercontent.com/libretro/libretro-database/master/metadat/no-intro/Nintendo%20-%20Super%20Nintendo%20Entertainment%20System.dat"
url_gamedb = "https://github.com/niemasd/GameDB-SNES/releases/latest/download/SNES.data.json"

convert_combined_databases(url_dat, url_gamedb)
print("Processing complete! Output saved to snes_roms_info.json")
