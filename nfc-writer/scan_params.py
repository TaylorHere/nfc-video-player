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
    res = h.read(64, timeout_ms=100)
    return list(res) if res else None

def main():
    h = hid.device()
    h.open(0x0801, 0x2011)
    
    print("Scanning parameters for Cmd 0x02 (Version)...")
    for p in range(256):
        res = send_xh_cmd(h, 0x02, [p])
        if res and res[4] != 0x1C:
            print(f"  Param 0x{p:02X} -> Status 0x{res[4]:02X}")
            if res[4] == 0x00:
                print("  Found working version command!")
                break
    
    print("\nScanning parameters for Cmd 0x01 (Beep)...")
    for p in range(256):
        res = send_xh_cmd(h, 0x01, [p])
        if res and res[4] != 0x1C:
            print(f"  Param 0x{p:02X} -> Status 0x{res[4]:02X}")
            if res[4] == 0x00:
                print("  Found working beep command!")
                break
                
    h.close()

if __name__ == "__main__":
    main()
