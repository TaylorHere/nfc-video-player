#!/usr/bin/env python3
import hid
import time

def main():
    h = hid.device()
    h.open(0x0801, 0x2011)
    
    # Send 0x10
    h.write([0x00, 0x78, 0x68, 0x01, 0x10, 0x01 ^ 0x10 ^ 0x78 ^ 0x68] + [0]*60)
    time.sleep(0.1)
    res = list(h.read(64))
    
    if res and res[0] == 0x78:
        payload = res[5:5+res[2]-1]
        print("Index | Hex | Dec")
        print("------------------")
        for i, b in enumerate(payload):
            print(f" {i:4} | {b:02X}  | {b}")
            
    h.close()

if __name__ == "__main__":
    main()
