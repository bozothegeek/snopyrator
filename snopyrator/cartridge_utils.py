import binascii
import time
import re
from rich.console import Console
from . import coms_utils as cu
from .printer import Printer
import sys

def check_initialized(func):
    def wrapper(*args, **kwargs):
        if args[0].initialized:
            return func(*args, **kwargs)
        else:
            raise Exception(
                "Reader not initialized, call initialize_reader() or initialize_reader_blocking() first"
            )

    return wrapper


def release_device(func):
    def wrapper(*args, **kwargs):
        output = func(*args, **kwargs)
        cu.release_sn_operator(args[0].gbop_device)
        return output

    return wrapper


def get_cartridge_info(func):
    def wrapper(*args, **kwargs):
        cartridge_info = cu.read_cartridge_info(args[0].gbop_device, args[0].debug)
        if cartridge_info is None:
            raise Exception(
                "Could not read cartridge info. Make sure a cartridge is inserted."
            )

        return func(*args, cartridge_info=cartridge_info, **kwargs)

    return wrapper


class CartridgeReader(object):
    def __init__(self, quiet=False, debug=False):
        self.initialized = False
        self.console = Console()
        self.quiet = quiet
        self.printer = Printer(quiet=quiet)
        self.debug = debug

    def initialize_reader(self, blocking=False, timeout=0, debug=False):
        if not blocking and timeout != 0:
            print("[WARNING] timeout is ignored when blocking is set to False",file=sys.stderr)

        with self.printer.status("Initializing reader..."):
            if blocking:
                dev = cu.find_sn_operator_blocking(timeout=timeout)
            else:
                dev = cu.find_sn_operator()

        if dev is None:
            raise ValueError(
                """
                SN Operator not found, check it is plugged in or that the appropriate udev rules are set up if you are on linux. See : https://support.epilogue.co/hc/en-us/articles/4403827118738-How-can-I-connect-my-Operator-device-on-Linux-under-a-non-root-user-
                """
            )
        else:
            self.gbop_device = cu.init_sn_operator(dev)
            self.initialized = True
            self.printer.success("[bold green]Reader initialized[/bold green]")

        return

    @check_initialized
    @release_device
    def read_cartridge_info(self):
        # with self.printer.status("Reading cartridge info..."):
        _cartridge_info = cu.read_cartridge_info(self.gbop_device, self.debug)
        return _cartridge_info

    @check_initialized
    @get_cartridge_info
    def set_cartridge_info(self, parameter, value, cartridge_info=None):
        cartridge_info[parameter] = value

    @check_initialized
    @release_device
    @get_cartridge_info
    def read_rom(self, size=None, cartridge_info=None):
        if size==None:
            num_bytes = cartridge_info["ROM_size"]
        else:
            num_bytes = size
        return cu.read_rom(self.gbop_device, num_bytes, quiet=self.quiet)

    def parse_size_to_bytes(self, size_str):
        """
        Convert a string as '4 MiB' or '128 KiB' in 'bytes' number (int).
        """
        if not size_str:
            return 0
            
        # clean string (remove space and upper case)
        size_str = size_str.upper().replace(' ', '')
        
        try:
            if "MIB" in size_str:
                number = float(size_str.replace("MIB", ""))
                return int(number * 1024 * 1024)
            elif "KIB" in size_str:
                number = float(size_str.replace("KIB", ""))
                return int(number * 1024)
            elif "MB" in size_str: # Security if the 'i' is forgotten
                number = float(size_str.replace("MB", ""))
                return int(number * 1024 * 1024)
        except ValueError:
            print(f"Error : Impossible to read size '{size_str}'")
            return 0
        
        return 0
    
    def dump_rom(self, filename, romsize=None):
        rom = self.read_rom(size=romsize)
        with open(filename, "wb") as f:
            f.write(rom)
        self.printer.success(f"ROM dumped to:\t[dark_cyan]{filename}[/dark_cyan]")

    @check_initialized
    @release_device
    @get_cartridge_info
    def read_save(self, cartridge_info=None, size=0):
        if size != 0:
            num_bytes = size
        else:
            num_bytes = cartridge_info["RAM_size"]
        
        if num_bytes == 0:
            self.printer.error("No RAM (save) detected on this cartridge.")
            return None
        else:
            if (self.debug):
                self.printer.print("RAM size (save) detected on this cartridge : " + str(num_bytes))
            if cartridge_info["cartridge_type"] == "GBA":
                return cu.read_save(self.gbop_device, num_bytes, quiet=self.quiet, debug=self.debug, rom_type="GBA")
            else:
                return cu.read_save(self.gbop_device, num_bytes, quiet=self.quiet, debug=self.debug, rom_type="GB/GBC")
    
    def dump_save(self, filename, size=0):
        save = self.read_save(size=size)
        if save is not None:
            with open(filename, "wb") as f:
                f.write(save)
            self.printer.success(f"Save dumped to:\t[dark_cyan]{filename}[/dark_cyan]")

    @check_initialized
    @release_device
    @get_cartridge_info
    def write_save(self, data, cartridge_info=None, size=0):
        if size == 0:
            num_bytes = cartridge_info["RAM_size"]
        else:
            num_bytes = size
        if num_bytes == 0:
            self.printer.error(
                "No RAM (save) detected on this cartridge. Impossible to write save."
            )
            return None
        elif num_bytes != len(data):
            self.printer.error(
                f"Save size mismatch. Expected {num_bytes} bytes, got {len(data)} bytes."
            )
            return None
        if (self.debug):
            self.printer.print("RAM size (save) for this cartridge : " + str(num_bytes))
        if cartridge_info["cartridge_type"] == "GBA":
            return cu.write_save(self.gbop_device, data, quiet=self.quiet, debug=self.debug, rom_type="GBA")
        else:
            return cu.write_save(self.gbop_device, data, quiet=self.quiet, debug=self.debug, rom_type="GB/GBC")

    def write_save_from_file(self, filename, size=0):
        with open(filename, "rb") as f:
            data = f.read()
        time.sleep(1)
        out = self.write_save(data, size=size)
        if out is not None:
            self.printer.success(
                f"Save written from:\t[dark_cyan]{filename}[/dark_cyan]"
            )

    def close(self):
        self.gbop_device.attach_kernel_driver(0)

    def get_region_info(self, region_index):
        # Mapping numeric index to (Letter, Full Name)
        region_map = {
            "0": ("J", "Japan"),
            "1": ("E", "USA"),
            "2": ("P", "Europe"),
            "3": ("D", "Germany"),
            "4": ("P", "Europe"),
            "5": ("F", "France"),
            "6": ("I", "Italy")
        }
    
        # Default to 'X' (Unknown) if index isn't found
        return region_map.get(str(region_index), ("X", "Unknown"))[0]
    
    @check_initialized
    @get_cartridge_info
    def get_epilogue_id(self, cartridge_info=None):
        if cartridge_info["cartridge_type"] == "GBA":
            epilogue_id = (
                cartridge_info["game_code"].upper()
                + self.get_region_info(cartridge_info["game_region"])
            )
        else: # for GB/GBC
            epilogue_id = (
                cartridge_info["title_first_letter"].upper()
                + "{:02x}".format(cartridge_info["header_checksum"]).upper()
                + binascii.hexlify(cartridge_info["global_checksum"]).decode().upper()
            )
        return epilogue_id

    @check_initialized
    @get_cartridge_info
    def get_rom_info_file(self, cartridge_info=None):
        if cartridge_info["cartridge_type"] == "GBA":
            return "gba_roms_info.json"
        else: # for GB/GBC
            return "gb_gbc_roms_info.json"

    @check_initialized
    @get_cartridge_info
    def get_epilogue_id_and_rom_info_file(self, cartridge_info=None):
        if cartridge_info["cartridge_type"] == "GBA":
            epilogue_id = (
                cartridge_info["game_code"].upper()
                + self.get_region_info(cartridge_info["game_region"])
            )
            rom_info_file = "gba_roms_info.json"
        else: # for GB/GBC
            epilogue_id = (
                cartridge_info["title_first_letter"].upper()
                + "{:02x}".format(cartridge_info["header_checksum"]).upper()
                + binascii.hexlify(cartridge_info["global_checksum"]).decode().upper()
            )
            rom_info_file = "gb_gbc_roms_info.json"
        return epilogue_id, rom_info_file

    def file_crc32(self, filename):
        with open(filename, "rb") as f:
            data = f.read()
        out = binascii.crc32(data) & 0xFFFFFFFF
        return hex(out)


    def bytearray_crc32(self, data):
        out = binascii.crc32(data) & 0xFFFFFFFF
        return hex(out)


    def create_crc_db(self, filename):
        with open(filename, "r") as f:
            content = f.read()
        game_regex = re.compile(
            r'game \(\n\tcomment "(.*)"\n\tpublisher "(.*)"\n\trom \( crc (.*) \)\n\)'
        )
        games = game_regex.findall(content)
        db = {}
        for game in games:
            db[game[2]] = game
        return db
