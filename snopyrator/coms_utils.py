import usb.core
import time
from crccheck.crc import Crc32Mpeg2
from .constants import MBC_TYPES, RAM_TYPES, ROM_TYPES
from rich.progress import Progress
import warnings

#info from lsusb command
# ID 16d0:123e MCS SN Operator


# Endpoints definitiions for USB Bulk IN and OUT
IN_ENDPOINT = 0x81
OUT_ENDPOINT = 0x01

#IN_ENDPOINT = 0x82
#OUT_ENDPOINT = 0x02

#IN_ENDPOINT = 0x83
#OUT_ENDPOINT = 0x03

# SN Operator Vendor and Product IDs (firmware 1.X)
SN_OPERATOR_VENDOR_ID = 0x16d0
SN_OPERATOR_PRODUCT_ID = 0x123e

# TO REMOVE (legacy from GBOpyrator)
# Old SN Operator Vendor and Product IDs ( firmware pre 9.0)
OLD_SN_OPERATOR_VENDOR_ID = 0x1D50
OLD_SN_OPERATOR_PRODUCT_ID = 0x6018

# Trigger sequence
TRIGGER_CARTRIDGE_INFO = bytearray(
    [
        0x04,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
    ]
)

TRIGGER_SAVE_READ = bytearray(
    [
        0x02,
        0x01,
        0x00,
        0x00,
        0x00,
        0x01,
        0x00,
        0x02,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
    ]
)


def _craft_save_write_trigger(save_size, rom_type="GB/GBC"):
    """
    Craft a save write trigger

    Parameters
    ----------
    save_size : int

    Returns
    -------
    bytearray
    """

    save_size_bytearray = save_size.to_bytes(
        (save_size.bit_length() + 7) // 8, byteorder="little"
    )
    if(rom_type == "GB/GBC"): #GB/GBC
        #should be shorter ?! mistake to verify
        trigger_save_write =     bytearray([0x03, 0x00, 0x00, 0x00, 0x80])
    else: #GBA
        trigger_save_write = bytearray([0x03, 0x01, 0x00, 0x00, 0x80])
    
    trigger_save_write += save_size_bytearray

    # Add 0x00 to reach 60 bytes
    pad_legnth = 60 - len(trigger_save_write)
    trigger_save_write += bytearray([0x00] * pad_legnth)
    # Add CRC32
    trigger_save_write = add_crc32(trigger_save_write)
    return trigger_save_write


def _craft_rom_read_trigger(rom_size):
    """
    Craft a rom read trigger

    Parameters
    ----------
    rom_size : int

    Returns
    -------
    bytearray
    """

    rom_size_bytearray = rom_size.to_bytes(
        (rom_size.bit_length() + 7) // 8, byteorder="little"
    )
    trigger_rom_read = bytearray([0x00, 0x00])
    trigger_rom_read += rom_size_bytearray

    # Add 0x00 to reach 60 bytes
    pad_legnth = 60 - len(trigger_rom_read)
    trigger_rom_read += bytearray([0x00] * pad_legnth)
    # Add CRC32
    trigger_rom_read = add_crc32(trigger_rom_read)
    return trigger_rom_read


def _craft_save_read_trigger(save_size, rom_type="GB/GBC"):
    """
    Craft a save read trigger

    Parameters
    ----------
    save_size : int

    Returns
    -------
    bytearray
    """

    save_size_bytearray = save_size.to_bytes(
        (save_size.bit_length() + 7) // 8, byteorder="little"
    )
    
    if(rom_type == "GB/GBC"): #GB/GBC
        #should be shorter ?! mistake to verify
        #saw in usb logs: 02 00 00 00 80 00 20
        trigger_save_read = bytearray([0x02, 0x00, 0x00, 0x00, 0x80])
    else: #GBA
        trigger_save_read = bytearray([0x02, 0x01, 0x00, 0x00, 0x80])
    trigger_save_read += save_size_bytearray

    # Add 0x00 to reach 60 bytes
    pad_legnth = 60 - len(trigger_save_read)
    trigger_save_read += bytearray([0x00] * pad_legnth)
    # Add CRC32
    trigger_save_read = add_crc32(trigger_save_read)
    return trigger_save_read


def add_crc32(data):
    """
    Add CRC32 to data

    Parameters
    ----------
    data : bytearray

    Returns
    -------
    bytearray
    """
    crc = Crc32Mpeg2.calc(data)
    bytes_crc = crc.to_bytes((crc.bit_length() + 7) // 8, byteorder="little")
    return data + bytes_crc


def find_sn_operator():
    """
    Find SN Operator device

    Returns
    -------
    usb.core.Device
    """
    # Find SN Operator with vendor ID and product ID
    # Those values can be found with `lsusb`
    
    # Find device with firmware v10.0+
    found_device = usb.core.find(
        idVendor=SN_OPERATOR_VENDOR_ID, idProduct=SN_OPERATOR_PRODUCT_ID
    )
    # Find older devices 
    found_old_device = usb.core.find(
            idVendor=OLD_SN_OPERATOR_VENDOR_ID, idProduct=OLD_SN_OPERATOR_PRODUCT_ID
    )


    if (found_device is not None) and (found_old_device is not None):
        warnings.warn("Found 2 SN Operators, one of which with and old firmware. \
                      GB Opyrator will use the one with the newer firmware", category=Warning)
        return found_device
    elif found_device is not None:
        return found_device
    elif found_old_device is not None:
        warnings.warn("Found SN Operator with old firmware. Please update it with Playback from epilogue.co")
        return found_old_device



def find_sn_operator_blocking(timeout=0):
    """
    Block while SN Operator device if not found

    Parameters
    ----------
    timeout : int, optional. If timeout = 0, will nerver timeout

    Returns
    -------
    usb.core.Device
    """

    if timeout == 0:
        while True:
            gbop_device = find_sn_operator()
            if gbop_device is not None:
                return gbop_device
            time.sleep(1)
    else:
        start = time.time()
        while True:
            gbop_device = find_sn_operator()
            if gbop_device is not None:
                return gbop_device
            time.sleep(1)
            if time.time() - start > timeout:
                raise TimeoutError("Unable to find SN Operator device")


def init_sn_operator(gbop_device):
    """
    Initialize SN Operator device

    Parameters
    ----------
    gbop_device : usb.core.Device
    """

    # # Check if device is None
    # if gbop_device is None:
        # raise ValueError("Device not found, you passed a device that is None")

    # # Detack kernel driver
    # if gbop_device.is_kernel_driver_active(0):
        # gbop_device.detach_kernel_driver(0)

    # # Activate first configuration
    # gbop_device.set_configuration()

    # Check if device is None
    if gbop_device is None:
        raise ValueError("Device not found, you passed a device that is None")

    # Detach kernel driver for ALL interfaces (0 and 1)
    for interface in (0, 1, 2):
        try:
            if gbop_device.is_kernel_driver_active(interface):
                gbop_device.detach_kernel_driver(interface)
        except Exception:
            pass

    # Activate first configuration
    #gbop_device.set_configuration()

    # On essaie de configurer proprement
    try:
        gbop_device.set_configuration()
    except usb.core.USBError as e:
        # Si c'est l'erreur 16 (Busy), on vérifie si on peut s'en passer
        if e.errno == 16:
            print("[Snopyrator] Configuration occupée, mais on tente de passer outre...")
            # Souvent, l'appareil est déjà configuré par le système, on peut continuer
            pass
        else:
            raise e

    # return device
    return gbop_device


def read_bulk_in(gbop_device, num_bytes=0, with_ack=False, quiet=False):
    """
    Read data from SN Operator device

    Parameters
    ----------
    gbop_device : usb.core.Device
    num_bytes : int, optional

    Returns
    -------
    bytearray
    """
    received_data = bytearray([])

    # Read data until SN Operator stops responding
    iteration = 0

    with Progress(disable=quiet, transient=True) as progress:
        task = progress.add_task("Reading...", total=num_bytes)

        while len(received_data) < num_bytes:
            progress.update(task, advance=64)
            try:
                usbpacket_data = gbop_device.read(IN_ENDPOINT, 64)
                received_data += bytearray(usbpacket_data)
                iteration += 1
            except usb.core.USBTimeoutError:
                print("USBTimeoutError")
                return received_data
            if with_ack and (iteration % 320 == 0):
                # send ACK
                gbop_device.write(OUT_ENDPOINT, bytearray([0x00] * 64))
                # read ACK
                _ = gbop_device.read(IN_ENDPOINT, 60)
                _ = gbop_device.read(IN_ENDPOINT, 4)

    return received_data


def write_bulk_out(gbop_device, data, quiet=False):
    """
    Write data to SN Operator device

    Parameters
    ----------
    gbop_device : usb.core.Device
    data : bytearray
    """
    with Progress(disable=quiet, transient=True) as progress:
        task = progress.add_task("Writing...", total=len(data))

        # Write data to SN Operator in chunks of 64 bytes
        for sequence in range(0, len(data), 64):
            progress.update(task, advance=64)
            gbop_device.write(OUT_ENDPOINT, data[sequence : sequence + 64])
            time.sleep(0.0001)
            # Read 64 bytes from SN Operator
            _ = gbop_device.read(IN_ENDPOINT, 60)
            _ = gbop_device.read(IN_ENDPOINT, 4)


def hex_dump(data):
    print(f"{'Offset':<8} {'Hex':<48} {'ASCII'}")
    print("-" * 75)
    for i in range(0, len(data), 16):
        chunk = data[i:i+16]
        hex_str = chunk.hex(' ')
        # Replace non-printable chars with dots
        ascii_str = "".join(chr(b) if 32 <= b <= 126 else "." for b in chunk)
        print(f"{i:04x}     {hex_str:<48} {ascii_str}")

def hex_string(data, maxlen):
    chunk = data[0:0+maxlen]
    hex_str = chunk.hex(' ')
    # Replace non-printable chars with dots
    ascii_str = "  ".join(chr(b) if 32 <= b <= 126 else "." for b in chunk)
    print(f"Hexa : {hex_str}")
    print(f"Ascii: {ascii_str}")

def read_cartridge_info(gbop_device, debug=False):
    """
    Read cartridge info from SN Operator device

    Parameters
    ----------
    gbop_device : usb.core.Device

    Returns
    -------
    dict
    """

    # Send power order
    gbop_device.write(OUT_ENDPOINT, add_crc32(TRIGGER_CARTRIDGE_INFO))

    # Read card data from SN Operator (ignored - seems as header block)
    _ = read_bulk_in(gbop_device, num_bytes=512, quiet=True)
    
    # Read card data from SN Operator
    received_data = read_bulk_in(gbop_device, num_bytes=512, quiet=True)

    # Read card data from SN Operator (ignored - seems as trailer block)
    _ = read_bulk_in(gbop_device, num_bytes=512, quiet=True)

    # Prints space-separated Hex bytes for debug purposes
    if(debug):
        #hex_dump(received_data)
        print("SN Operator Header (first 32 bytes of second 512 bytes block):")
        hex_string(received_data, 32)
    
    # check if received_data is all null bytes
    if not (received_data[3] or received_data[4]):
        return None

    # Second block is the most important
    # SN Operator Header (first 32 bytes):

    # if empty (no cartridge)
    # Hexa : 01 01 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 01 00 01 02 00 00
    # Ascii: .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .

    # if not empty (killer instinct FAH)
    # Hexa : 01 01 50 00 00 17 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 01 00 01 02 00 00
    # Ascii: .  .  P  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .

    # if not empty (International superstar soccer EUR)
    # Hexa : 01 01 50 01 01 15 00 00 00 03 00 00 00 e3 1f 02 0b 53 54 41 00 00 00 00 00 00 01 00 01 02 00 00
    # Ascii: .  .  P  .  .  .  .  .  .  .  .  .  .  .  .  .  .  S  T  A  .  .  .  .  .  .  .  .  .  .  .  .

    # if not empty (Zelda - link to the past FRA)
    # Hexa : 01 01 50 01 01 14 0d 21 00 05 00 00 00 ae 65 06 0a 4c 45 ff 00 00 00 00 00 00 01 00 01 02 00 00
    # Ascii: .  .  P  .  .  .  .  !  .  .  .  .  .  .  e  .  .  L  E  .  .  .  .  .  .  .  .  .  .  .  .  .

    # if not empty (Street Fighter II FAH)
    # Hexa : 01 01 50 01 01 15 00 00 00 03 00 00 00 d0 39 02 0b 53 20 6e 00 00 00 00 00 00 01 00 01 02 00 00
    # Ascii: .  .  P  .  .  .  .  .  .  .  .  .  .  .  9  .  .  S     n  .  .  .  .  .  .  .  .  .  .  .  .

    # if not empty (Super mario kart - jap)
    # Hexa : 01 01 50 01 01 13 0b 20 00 01 00 00 00 23 8a 00 09 53 4d 00 00 00 00 00 00 00 01 00 01 02 00 00
    # Ascii: .  .  P  .  .  .  .     .  .  .  .  .  #  .  .  .  S  M  .  .  .  .  .  .  .  .  .  .  .  .  .


    if received_data[2] == 0x50: # For SuperNintendo/SuperFamicom
    
        rom_exponent = received_data[5]
        rom_size_bytes = 1 << rom_exponent
        
        ram_exponent = received_data[9]
        ram_size_kb = 1 << ram_exponent
        ram_size_bytes = ram_size_kb * 1024
        hardware_flags = received_data[6:8]
        if hardware_flags == b"\x00\x00":
            mbc_type = "LoROM Standard"
        elif hardware_flags == b"\x0d\x21":
            mbc_type = "LoROM + SRAM Avancée (Zelda Type)"
        elif hardware_flags == b"\x0b\x20":
            mbc_type = "LoROM + DSP-1 (Mario Kart Type)"
        else:
            mbc_type = f"Unknown Mapper (Flags: {hardware_flags.hex()})"
        cartridge_info = {
            "cartridge_type": "SNES",
            "ROM_size": rom_size_bytes, #confirmed
            "RAM_size": ram_size_bytes, #confirmed
            "title_first_letter": chr(received_data[17]), # it's finally the first from the 3 letters from internal name
            "MBC_type": mbc_type,
            "ROM_type": "", #unknown
            "RAM_type": "", #unknown
            "header_checksum": received_data[0], #unknown
            "global_checksum": received_data[13:14], #checksum confirmed but inversed
        }

    return cartridge_info


def read_save(gbop_device, num_bytes, quiet=False, debug=False, rom_type="GB/GBC"):
    """
    Dump save file from SN Operator device

    Parameters
    ----------
    gbop_device : usb.core.Device
    filename : str
    """
    # craft trigger bytes
    trigger_save_read = _craft_save_read_trigger(num_bytes, rom_type)

    if(debug):
        print("trigger_save_read:")
        hex_dump(trigger_save_read)

    # Send trigger_bytes
    gbop_device.write(OUT_ENDPOINT, trigger_save_read)

    # Burn the first 64 bytes
    # Burn first 64 bytes in 2 times
    _ = gbop_device.read(IN_ENDPOINT, 60)
    _ = gbop_device.read(IN_ENDPOINT, 4)

    # Read data from SN Operator
    received_data = read_bulk_in(gbop_device, num_bytes=num_bytes, quiet=quiet)

    return bytearray(received_data)


def write_save(gbop_device, bytearray_data, quiet=False, debug=False, rom_type="GB/GBC"):
    """
    Write save file to SN Operator device

    Parameters
    ----------
    gbop_device : usb.core.Device
    filename : str
    """
    # craft trigger bytes
    trigger_save_write = _craft_save_write_trigger(len(bytearray_data), rom_type)
    
    if(debug):
        print("trigger_save_write:")
        hex_dump(trigger_save_write)
    
    # Send trigger_bytes
    gbop_device.write(OUT_ENDPOINT, trigger_save_write)

    # Burn the first 64 bytes
    # Burn first 64 bytes in 2 times
    _ = gbop_device.read(IN_ENDPOINT, 60)
    _ = gbop_device.read(IN_ENDPOINT, 4)

    # Write data to SN Operator
    write_bulk_out(gbop_device, bytearray_data, quiet=quiet)

    return True


def read_rom(gbop_device, num_bytes, quiet=False):
    """
    Dump ROM from SN Operator device

    Parameters
    ----------
    gbop_device : usb.core.Device
    filename : str
    """
    # craft trigger bytes
    trigger_rom_read = _craft_rom_read_trigger(num_bytes)

    # Send trigger_bytes
    gbop_device.write(OUT_ENDPOINT, trigger_rom_read)

    # Burn first 64 bytes in 2 times
    _ = gbop_device.read(IN_ENDPOINT, 60)
    _ = gbop_device.read(IN_ENDPOINT, 4)

    # Send "ACK" to SN Operator
    gbop_device.write(OUT_ENDPOINT, bytearray([0x00] * 64))

    # Burn first 64 bytes a second time
    _ = gbop_device.read(IN_ENDPOINT, 60)
    _ = gbop_device.read(IN_ENDPOINT, 4)

    # Read data from SN Operator
    received_data = read_bulk_in(
        gbop_device, num_bytes=num_bytes, with_ack=True, quiet=quiet
    )

    return bytearray(received_data)


def release_sn_operator(gbop_device):
    """
    Release SN Operator device

    Parameters
    ----------
    gbop_device : usb.core.Device
    """
    # Release device
    usb.util.dispose_resources(gbop_device)
