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
    usb.util.claim_interface(dev, 0)
    ep_out, ep_in = 0x02, 0x81

    def send(cmd_code, data=[]):
        pkt = [0x78, 0x68, len(data)+1, cmd_code] + data
        pkt.append(xh_checksum(pkt))
        dev.write(ep_out, bytes(pkt + [0]*(64-len(pkt))))
        time.sleep(0.05)
        try: return list(dev.read(ep_in, 64, timeout=500))
        except: return None

    send(0x10) # Search
    
    # 1. Try Mifare Read (0x30) via 0x22
    print("Testing Mifare Read (30 00) via Cmd 0x22...")
    res = send(0x22, [0x30, 0x00])
    if res:
        print(f"   Status: 0x{res[4]:02X}")
        if res[4] == 0x00:
            print(f"   SUCCESS! Data: {bytes(res[5:5+res[2]-1]).hex().upper()}")

    # 2. Try Mifare Read (0x30) via 0x30
    print("\nTesting Mifare Read (30 00) via Cmd 0x30...")
    res = send(0x30, [0x00])
    if res:
        print(f"   Status: 0x{res[4]:02X}")
        if res[4] == 0x00:
            print(f"   SUCCESS! Data: {bytes(res[5:5+res[2]-1]).hex().upper()}")

    usb.util.release_interface(dev, 0)
    usb.util.dispose_resources(dev)

if __name__ == "__main__":
    main()
