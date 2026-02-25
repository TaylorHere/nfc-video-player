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
    
    # 1. Search
    print("Searching card...")
    send_xh_cmd(h, 0x10)
    
    # 2. RATS
    print("RATS...")
    send_xh_cmd(h, 0x20)
    
    # 3. APDU Loop
    apdu = [0x00, 0xA4, 0x04, 0x00, 0x07, 0xD2, 0x76, 0x00, 0x00, 0x85, 0x01, 0x01]
    print("Sending Select NDEF APDU (retrying 5 times)...")
    for i in range(5):
        res = send_xh_cmd(h, 0x22, apdu)
        if res:
            status = res[4]
            print(f"  Attempt {i+1}: Status 0x{status:02X}")
            if status == 0x00:
                print("  SUCCESS!")
                break
        else:
            print(f"  Attempt {i+1}: No response")
        time.sleep(0.2)
        
    h.close()

if __name__ == "__main__":
    main()
