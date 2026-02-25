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
    
    print("1. Search (0x10)")
    send_xh_cmd(h, 0x10)
    
    print("2. Activate CPU Card (0x12)...")
    res = send_xh_cmd(h, 0x12)
    if res:
        print(f"   Status: 0x{res[4]:02X}")
        
    print("3. Testing APDU (Select NDEF)...")
    apdu = [0x00, 0xA4, 0x04, 0x00, 0x07, 0xD2, 0x76, 0x00, 0x00, 0x85, 0x01, 0x01]
    res = send_xh_cmd(h, 0x22, apdu)
    if res:
        print(f"   Status: 0x{res[4]:02X}")
        if res[4] == 0x00: print("   SUCCESS!")
            
    h.close()

if __name__ == "__main__":
    main()
