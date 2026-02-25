#!/usr/bin/env python3
import usb.core
import usb.util
import time

def main():
    VENDOR_ID = 0x0801
    PRODUCT_ID = 0x2011
    
    dev = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
    if dev is None: return

    # Force detach and claim
    for i in [0]:
        try:
            if dev.is_kernel_driver_active(i):
                dev.detach_kernel_driver(i)
        except: pass
        
    try:
        usb.util.claim_interface(dev, 0)
    except Exception as e:
        print(f"Claim failed: {e}")

    # Find endpoints
    cfg = dev.get_active_configuration()
    intf = cfg[(0,0)]
    
    ep_out = usb.util.find_descriptor(intf, custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT)
    ep_in = usb.util.find_descriptor(intf, custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN)

    print(f"EP OUT: {hex(ep_out.bEndpointAddress)}, EP IN: {hex(ep_in.bEndpointAddress)}")

    # 0x10 command
    pkt = [0x78, 0x68, 0x01, 0x10, 0x01]
    buf = bytes(pkt + [0]*(64-len(pkt)))
    
    ep_out.write(buf)
    time.sleep(0.1)
    try:
        res = ep_in.read(64, timeout=1000)
        print(f"RES: {bytes(res).hex().upper()}")
    except Exception as e:
        print(f"Read error: {e}")

    usb.util.release_interface(dev, 0)
    usb.util.dispose_resources(dev)

if __name__ == "__main__":
    main()
