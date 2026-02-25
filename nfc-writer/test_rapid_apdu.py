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
    
    # 0x10
    pkt = [0x78, 0x68, 0x01, 0x10, 0x01 ^ 0x10 ^ 0x78 ^ 0x68]
    h.write([0x00] + pkt + [0]*60)
    h.read(64)
    
    # 0x20
    pkt = [0x78, 0x68, 0x01, 0x20, 0x01 ^ 0x20 ^ 0x78 ^ 0x68]
    h.write([0x00] + pkt + [0]*60)
    h.read(64)
    
    # 0x22
    apdu = [0x00, 0xA4, 0x04, 0x00, 0x07, 0xD2, 0x76, 0x00, 0x00, 0x85, 0x01, 0x01]
    pkt = [0x78, 0x68, len(apdu)+1, 0x22] + apdu
    pkt.append(xh_checksum(pkt))
    h.write([0x00] + pkt + [0]*(64-len(pkt)))
    
    res = h.read(64, timeout_ms=500)
    if res:
        print(f"Final Res: {bytes(res[:8]).hex().upper()}")
        
    h.close()

if __name__ == "__main__":
    main()
