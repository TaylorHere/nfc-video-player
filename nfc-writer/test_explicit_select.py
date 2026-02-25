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
    
    # 1. Search
    print("1. Searching (0x10)...")
    res = send_xh_cmd(h, 0x10)
    if not res or res[4] != 0x00:
        print("No card found")
        h.close()
        return
    uid = res[6:6+res[5]]
    print(f"   UID: {bytes(uid).hex().upper()}")
    
    # 2. Select (0x13) - Try to select the card explicitly
    print(f"2. Explicit Select (0x13) with UID...")
    res = send_xh_cmd(h, 0x13, list(uid))
    if res:
        print(f"   Status: 0x{res[4]:02X}")
        
    # 3. RATS (0x20)
    print("3. RATS (0x20)...")
    res = send_xh_cmd(h, 0x20)
    if res:
        print(f"   Status: 0x{res[4]:02X}")
        
    # 4. APDU (0x22)
    apdu = [0x00, 0xA4, 0x04, 0x00, 0x07, 0xD2, 0x76, 0x00, 0x00, 0x85, 0x01, 0x01]
    print("4. Select NDEF APDU (0x22)...")
    res = send_xh_cmd(h, 0x22, apdu)
    if res:
        print(f"   Status: 0x{res[4]:02X}")
        if res[4] == 0x00:
            payload = bytes(res[5:5+res[2]-1])
            print(f"   SUCCESS! Data: {payload.hex().upper()}")
        else:
            print(f"   Failed. Response: {bytes(res[:16]).hex().upper()}")
            
    h.close()

if __name__ == "__main__":
    main()
