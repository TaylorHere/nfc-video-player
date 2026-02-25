#!/usr/bin/env python3
import usb.core
import usb.util
import time

def main():
    VENDOR_ID = 0x0801
    PRODUCT_ID = 0x2011
    
    dev = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
    if dev is None: return

    try:
        if dev.is_kernel_driver_active(0):
            dev.detach_kernel_driver(0)
    except: pass

    dev.set_configuration()
    
    # Select NDEF APDU
    apdu = [0x00, 0xA4, 0x04, 0x00, 0x07, 0xD2, 0x76, 0x00, 0x00, 0x85, 0x01, 0x01]
    
    print("Trying RAW APDU via PyUSB (No Preamble)...")
    # EP2 is OUT
    dev.write(0x02, bytes(apdu + [0]*(64-len(apdu))))
    
    time.sleep(0.2)
    try:
        # EP1 is IN
        res = dev.read(0x81, 64, timeout=500)
        print(f"Response: {bytes(res).hex().upper()}")
    except Exception as e:
        print(f"Read error: {e}")
        
    # Re-try WITH XH Preamble but via RAW USB
    print("\nTrying XH Preamble via PyUSB...")
    cmd = [0x78, 0x68, len(apdu)+1, 0x22] + apdu
    chk = 0
    for b in cmd: chk ^= b
    cmd.append(chk)
    dev.write(0x02, bytes(cmd + [0]*(64-len(cmd))))
    
    time.sleep(0.2)
    try:
        res = dev.read(0x81, 64, timeout=500)
        print(f"Response: {bytes(res).hex().upper()}")
    except Exception as e:
        print(f"Read error: {e}")

    usb.util.dispose_resources(dev)

if __name__ == "__main__":
    main()
