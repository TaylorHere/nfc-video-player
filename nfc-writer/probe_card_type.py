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
    return h.read(64, timeout_ms=500)

def main():
    h = hid.device()
    h.open(0x0801, 0x2011)
    
    print("--- Card Type Probe ---")
    
    # 1. Request (REQA)
    res = send_xh_cmd(h, 0x11, [0x26])
    if res and res[4] == 0x00:
        atqa = bytes(res[5:7])
        print(f"ATQA: {atqa.hex().upper()}")
    else:
        print(f"REQA failed or no card: status 0x{res[4]:02X if res else 0}")
        
    # 2. Anticollision/Select
    res = send_xh_cmd(h, 0x12) # Usually anticollision
    if res and res[4] == 0x00:
        uid = bytes(res[5:5+res[2]-1])
        print(f"UID/Anticoll: {uid.hex().upper()}")
        
    # 3. RATS (ISO14443-4)
    res = send_xh_cmd(h, 0x20)
    if res and res[4] == 0x00:
        ats = bytes(res[5:5+res[2]-1])
        print(f"ATS: {ats.hex().upper()}")
        print("This card supports ISO14443-4 (likely NTAG 424 DNA)")
    else:
        print(f"RATS failed: status 0x{res[4]:02X if res else 0}")

    h.close()

if __name__ == "__main__":
    main()
