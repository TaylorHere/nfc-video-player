#!/usr/bin/env python3
import usb.core
import usb.util
import time

def xh_checksum(data):
    chk = 0
    for b in data:
        chk ^= b
    return chk

def main():
    dev = usb.core.find(idVendor=0x0801, idProduct=0x2011)
    if dev is None: return
    try:
        if dev.is_kernel_driver_active(0): dev.detach_kernel_driver(0)
    except: pass
    usb.util.claim_interface(dev, 0)
    ep_out, ep_in = 0x02, 0x81

    def send(cmd_code, data=[]):
        pkt = [0x78, 0x68, len(data)+1, cmd_code] + data
        pkt.append(xh_checksum(pkt))
        dev.write(ep_out, bytes(pkt + [0]*(64-len(pkt))))
        time.sleep(0.1)
        try: return list(dev.read(ep_in, 64, timeout=500))
        except: return None

    # 1. Activation
    print("1. Activation (0x10)")
    send(0x10)
    
    # 2. Try Reset combinations
    print("2. Trying CPU Reset (0x1B)")
    res = send(0x1B)
    if res: print(f"   Status: 0x{res[4]:02X}")
    
    # 3. Select NDEF
    apdu = [0x00, 0xA4, 0x04, 0x00, 0x07, 0xD2, 0x76, 0x00, 0x00, 0x85, 0x01, 0x01]
    print("3. Select NDEF (0x22)")
    res = send(0x22, apdu)
    if res:
        print(f"   Status: 0x{res[4]:02X}")
        if res[4] == 0x00: print("   SUCCESS!")

    usb.util.release_interface(dev, 0)
    usb.util.dispose_resources(dev)

if __name__ == "__main__":
    main()
