#!/usr/bin/env python3
import hid
import time

def xh_checksum(data):
    chk = 0
    for b in data:
        chk ^= b
    return chk

def main():
    h = hid.device()
    h.open(0x0801, 0x2011)
    
    # Search & RATS
    h.write([0x00, 0x78, 0x68, 0x01, 0x10, 0x01 ^ 0x10 ^ 0x78 ^ 0x68] + [0]*60)
    time.sleep(0.1)
    h.read(64)
    
    h.write([0x00, 0x78, 0x68, 0x01, 0x20, 0x01 ^ 0x20 ^ 0x78 ^ 0x68] + [0]*60)
    time.sleep(0.1)
    h.read(64)
    
    # APDU Get Version
    apdu = [0x90, 0x60, 0x00, 0x00, 0x00]
    cmd = [0x78, 0x68, len(apdu)+1, 0x22] + apdu
    cmd.append(xh_checksum(cmd))
    
    buf = [0x00] + cmd + [0]*(64-len(cmd))
    print(f"Sending APDU: {bytes(cmd).hex().upper()}")
    h.write(buf)
    
    print("Reading responses...")
    for _ in range(5):
        res = h.read(64, timeout_ms=200)
        if res:
            print(f"Res: {bytes(res[:16]).hex().upper()}")
        else:
            print("No more data.")
            break
            
    h.close()

if __name__ == "__main__":
    main()
