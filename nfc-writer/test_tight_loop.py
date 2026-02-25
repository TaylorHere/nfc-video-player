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
    # 缩短等待时间
    time.sleep(0.02)
    res = h.read(64, timeout_ms=200)
    return list(res) if res else None

def main():
    h = hid.device()
    h.open(0x0801, 0x2011)
    
    # 强制排空接收缓冲区
    h.set_nonblocking(True)
    while h.read(64): pass
    h.set_nonblocking(False)
    
    print("1. Activating Card (0x10)...")
    res = send_xh_cmd(h, 0x10)
    if not res or res[4] != 0x00:
        print("Activation failed")
        h.close()
        return
    print(f"   UID: {bytes(res[5:5+7]).hex().upper()}")
    
    print("2. Sending RATS (0x20)...")
    res = send_xh_cmd(h, 0x20)
    if res: print(f"   Status: 0x{res[4]:02X}")
    
    # Select NDEF APDU
    apdu = [0x00, 0xA4, 0x04, 0x00, 0x07, 0xD2, 0x76, 0x00, 0x00, 0x85, 0x01, 0x01]
    print("3. Sending Select NDEF APDU (0x22)...")
    res = send_xh_cmd(h, 0x22, apdu)
    if res:
        print(f"   Status: 0x{res[4]:02X}")
        if res[4] == 0x00:
            print("   SUCCESS! NDEF Selected.")
        else:
            print(f"   Failed. Response: {bytes(res[:16]).hex().upper()}")
            
    h.close()

if __name__ == "__main__":
    main()
