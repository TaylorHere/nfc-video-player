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

    def send_only(cmd_code, data=[]):
        pkt = [0x78, 0x68, len(data)+1, cmd_code] + data
        pkt.append(xh_checksum(pkt))
        dev.write(ep_out, bytes(pkt + [0]*(64-len(pkt))))

    def read_multi(count=5):
        for i in range(count):
            try:
                res = dev.read(ep_in, 64, timeout=200)
                print(f"Read {i}: {bytes(res[:16]).hex().upper()}")
            except:
                print(f"Read {i}: Timeout")

    print("1. Search (0x10)")
    send_only(0x10)
    read_multi(1)
    
    print("\n2. Sending APDU (0x22) and multi-reading...")
    apdu = [0x00, 0xA4, 0x04, 0x00, 0x07, 0xD2, 0x76, 0x00, 0x00, 0x85, 0x01, 0x01]
    send_only(0x22, apdu)
    read_multi(10)

    usb.util.release_interface(dev, 0)
    usb.util.dispose_resources(dev)

if __name__ == "__main__":
    main()
