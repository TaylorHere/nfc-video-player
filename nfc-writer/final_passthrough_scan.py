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
        time.sleep(0.02)
        try: return list(dev.read(ep_in, 64, timeout=200))
        except: return None

    # Get Challenge APDU
    apdu = [0x00, 0x84, 0x00, 0x00, 0x08]
    
    print("Starting All-Cmd Scan for APDU Passthrough...")
    for code in range(0x01, 0x41):
        # Only try common codes to save time
        if code in [0x05, 0x15, 0x19, 0x22, 0x41]:
            print(f"Checking Cmd 0x{code:02X}...")
            res = send(code, apdu)
            if res and res[4] == 0x00:
                print(f"!!! FOUND PASSTHROUGH CMD: 0x{code:02X} !!!")
                print(f"Data: {bytes(res[5:]).hex().upper()}")
                break
        
    usb.util.release_interface(dev, 0)
    usb.util.dispose_resources(dev)

if __name__ == "__main__":
    main()
