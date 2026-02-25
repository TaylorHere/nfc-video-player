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
    time.sleep(0.05)
    res = h.read(64, timeout_ms=500)
    return list(res) if res else None

def main():
    h = hid.device()
    h.open(0x0801, 0x2011)
    
    # 1. Get UID
    res = send_xh_cmd(h, 0x10)
    if not res: return
    uid = res[5:12] # 04 77 65 02 A8 22 90
    print(f"UID: {bytes(uid).hex().upper()}")
    
    # 2. Try APDU with UID prefix
    apdu = [0x00, 0xA4, 0x04, 0x00, 0x07, 0xD2, 0x76, 0x00, 0x00, 0x85, 0x01, 0x01]
    # Format: [UID_LEN] + [UID] + [APDU]
    print("Trying APDU with [UID_LEN] + [UID] prefix...")
    res = send_xh_cmd(h, 0x22, [0x07] + list(uid) + apdu)
    if res:
        print(f"Status: 0x{res[4]:02X}")
        if res[4] == 0x00: print("SUCCESS!")
    
    # Format: [UID] + [APDU]
    print("Trying APDU with [UID] prefix...")
    res = send_xh_cmd(h, 0x22, list(uid) + apdu)
    if res:
        print(f"Status: 0x{res[4]:02X}")
        if res[4] == 0x00: print("SUCCESS!")
        
    h.close()

if __name__ == "__main__":
    main()
