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
    
    # Beep: 78 68 02 01 32 [chk]
    dur = 0x32 # 50ms
    pkt = [0x78, 0x68, 0x02, 0x01, dur]
    pkt.append(xh_checksum(pkt))
    
    print(f"Sending Beep: {bytes(pkt).hex().upper()}")
    h.write([0x00] + pkt + [0]*58)
    
    time.sleep(0.5)
    res = h.read(64, timeout_ms=500)
    if res:
        print(f"Res: {bytes(res[:8]).hex().upper()}")
        
    h.close()

if __name__ == "__main__":
    main()
