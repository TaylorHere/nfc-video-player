#!/usr/bin/env python3
import usb.core
import usb.util
import time

def main():
    VENDOR_ID = 0x0801
    PRODUCT_ID = 0x2011
    
    dev = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
    if dev is None:
        print("Device not found")
        return
        
    print("Direct USB mode active.")
    
    # Configuration
    try:
        dev.set_configuration()
    except: pass

    # 1. Search Card (0x10)
    # 78 68 01 10 01
    pkt = [0x78, 0x68, 0x01, 0x10, 0x01]
    buf = bytes(pkt + [0]*(64-len(pkt)))
    
    print("Searching for card...")
    dev.write(0x02, buf)
    
    time.sleep(0.1)
    try:
        res = dev.read(0x81, 64, timeout=500)
        print(f"Response (0x10): {bytes(res).hex().upper()}")
        uid = bytes(res[5:12]).hex().upper()
        print(f"UID found: {uid}")
    except Exception as e:
        print(f"No card or error: {e}")
        return

    # 2. Try Beep (0x01)
    pkt = [0x78, 0x68, 0x01, 0x01, 0x10]
    buf = bytes(pkt + [0]*(64-len(pkt)))
    print("Sending Beep...")
    dev.write(0x02, buf)
    
    usb.util.dispose_resources(dev)

if __name__ == "__main__":
    main()
