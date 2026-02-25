#!/usr/bin/env python3
import hid
import time

def main():
    h = hid.device()
    h.open(0x0801, 0x2011)
    h.set_nonblocking(True)
    
    print("Listening WITHOUT sending anything...")
    start = time.time()
    while time.time() - start < 2.0:
        res = h.read(64)
        if res:
            print(f"[{time.time()-start:.3f}] {bytes(res).hex().upper()}")
        time.sleep(0.01)
        
    h.close()

if __name__ == "__main__":
    main()
