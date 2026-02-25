#!/usr/bin/env python3
import usb.core
import usb.util
import time

def xh_checksum(data):
    chk = 0
    for b in data: chk ^= b
    return chk

def crc16(data):
    # ISO14443-3 / ISO14443-4 CRC-B calculation
    crc = 0xFFFF
    for b in data:
        b ^= (crc & 0xFF)
        b ^= (b << 4) & 0xFF
        crc = (crc >> 8) ^ (b << 8) ^ (b << 3) ^ (b >> 4)
    return (~crc & 0xFFFF)

def main():
    dev = usb.core.find(idVendor=0x0801, idProduct=0x2011)
    if dev is None: return
    try:
        if dev.is_kernel_driver_active(0): dev.detach_kernel_driver(0)
    except: pass
    usb.util.claim_interface(dev, 0)
    ep_out, ep_in = 0x02, 0x81

    def send_cmd(code, data=[]):
        pkt = [0x78, 0x68, len(data)+1, code] + data
        pkt.append(xh_checksum(pkt))
        dev.write(ep_out, bytes(pkt + [0]*(64-len(pkt))))
        time.sleep(0.05)
        try: return list(dev.read(ep_in, 64, timeout=200))
        except: return None

    print("--- Brute Force Passthrough with CRC Variants ---")
    # Activate
    send_cmd(0x10)
    send_cmd(0x1B) # CPU Reset
    
    # Get Challenge APDU
    apdu = [0x00, 0x84, 0x00, 0x00, 0x08]
    
    # APDU with CRC16 (Some non-standard readers require it)
    crc = crc16(apdu)
    apdu_crc = apdu + [crc & 0xFF, (crc >> 8) & 0xFF]

    test_codes = [0x05, 0x15, 0x19, 0x22, 0x41]
    for code in test_codes:
        print(f"Testing Code 0x{code:02X}...")
        
        # Try raw
        res = send_cmd(code, apdu)
        if res and res[4] == 0x00:
            print(f"!!! SUCCESS with 0x{code:02X} RAW !!!")
            break
            
        # Try with CRC
        res = send_cmd(code, apdu_crc)
        if res and res[4] == 0x00:
            print(f"!!! SUCCESS with 0x{code:02X} CRC !!!")
            break
            
    usb.util.release_interface(dev, 0)
    usb.util.dispose_resources(dev)

if __name__ == "__main__":
    main()
