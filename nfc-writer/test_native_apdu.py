#!/usr/bin/env python3
import hid
import time

def xh_checksum(data):
    chk = 0
    for b in data:
        chk ^= b
    return chk

def send_xh_cmd(h, cmd_code, data=[], rid=0x00):
    pkt = [0x78, 0x68, len(data)+1, cmd_code] + data
    pkt.append(xh_checksum(pkt))
    buf = [rid] + pkt + [0]*(64-len(pkt))
    h.write(buf)
    time.sleep(0.1)
    res = h.read(64, timeout_ms=500)
    return list(res) if res else None

def main():
    h = hid.device()
    h.open(0x0801, 0x2011)
    
    # Activation
    send_xh_cmd(h, 0x10)
    send_xh_cmd(h, 0x20)
    
    # 1. Short APDU (Get Challenge - 5 bytes)
    print("Testing Short APDU (Get Challenge)...")
    apdu = [0x00, 0x84, 0x00, 0x00, 0x08]
    res = send_xh_cmd(h, 0x22, apdu)
    if res: print(f"   Status: 0x{res[4]:02X}")
    
    # 2. Native Wrapper (90 60 00 00 00 -> 60)
    print("Testing Native Command (Get Version 0x60) via 0x41...")
    res = send_xh_cmd(h, 0x41, [0x60])
    if res:
        print(f"   Status: 0x{res[4]:02X}")
        if res[4] == 0x00:
            print(f"   Data: {bytes(res[5:5+res[2]-1]).hex().upper()}")
            
    # 3. PPS (0x21) - Some cards need this
    print("Testing PPS (0x21)...")
    res = send_xh_cmd(h, 0x21, [0x00, 0x00])
    if res: print(f"   Status: 0x{res[4]:02X}")
    
    h.close()

if __name__ == "__main__":
    main()
