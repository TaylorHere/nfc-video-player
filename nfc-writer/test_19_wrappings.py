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
    
    # Try different 0x19 wrappings
    apdu = [0x00, 0xA4, 0x04, 0x00, 0x07, 0xD2, 0x76, 0x00, 0x00, 0x85, 0x01, 0x01]
    
    print("Wrapping 1: Cmd 0x19 + APDU")
    res = send(0x19, apdu)
    if res: print(f"   Status: 0x{res[4]:02X}")
    
    print("Wrapping 2: Cmd 0x19 + [Len] + APDU")
    res = send(0x19, [len(apdu)] + apdu)
    if res: print(f"   Status: 0x{res[4]:02X}")
    
    print("Wrapping 3: Cmd 0x19 + [0x00] + APDU")
    res = send(0x19, [0x00] + apdu)
    if res: print(f"   Status: 0x{res[4]:02X}")

    usb.util.release_interface(dev, 0)
    usb.util.dispose_resources(dev)

if __name__ == "__main__":
    main()
