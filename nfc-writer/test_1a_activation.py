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
        time.sleep(0.05)
        try: return list(dev.read(ep_in, 64, timeout=500))
        except: return None

    # 1. Start with 0x10
    print("1. Search (0x10)")
    send(0x10)

    # 2. Try 0x1A Activation (The key for CPU cards)
    print("2. CPU Activation (0x1A)...")
    res = send(0x1A)
    if res:
        print(f"   Status: 0x{res[4]:02X}")
        if len(res) > 5:
            print(f"   ATS: {bytes(res[5:5+res[2]-1]).hex().upper()}")
            
    # 3. Try APDU
    apdu = [0x00, 0x84, 0x00, 0x00, 0x08]
    print("3. APDU (0x19)...")
    res = send(0x19, apdu)
    if res:
        print(f"   Status: 0x{res[4]:02X}")
        if res[4] == 0x00:
            print(f"   SUCCESS! Data: {bytes(res[5:]).hex().upper()}")

    usb.util.release_interface(dev, 0)
    usb.util.dispose_resources(dev)

if __name__ == "__main__":
    main()
