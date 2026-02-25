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
    h.set_nonblocking(True)
    
    # Send 0x10
    pkt = [0x78, 0x68, 0x01, 0x10, 0x01 ^ 0x10 ^ 0x78 ^ 0x68]
    h.write([0x00] + pkt + [0]*60)
    
    print("Listening for 2 seconds...")
    start = time.time()
    while time.time() - start < 2.0:
        res = h.read(64)
        if res:
            print(f"[{time.time()-start:.3f}] {bytes(res).hex().upper()}")
        time.sleep(0.01)
        
    h.close()

if __name__ == "__main__":
    main()
