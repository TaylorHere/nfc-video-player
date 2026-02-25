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
    
    print("--- APDU Brute Force ---")
    
    # 1. Search card
    print("Searching card (0x10)...")
    res = send_xh_cmd(h, 0x10)
    if not res or res[4] != 0x00:
        print("No card found.")
        h.close()
        return
    print(f"Card found: {bytes(res[5:5+res[2]-1]).hex().upper()}")
    
    # 2. Try RATS (0x20)
    print("Sending RATS (0x20)...")
    res = send_xh_cmd(h, 0x20)
    if res:
        print(f"RATS Res: 0x{res[4]:02X}")
    
    # 3. Try APDU (Select NDEF) with different command codes
    apdu = [0x00, 0xA4, 0x04, 0x00, 0x07, 0xD2, 0x76, 0x00, 0x00, 0x85, 0x01, 0x01]
    for cmd in [0x05, 0x18, 0x22, 0x41]:
        print(f"Trying APDU with Cmd 0x{cmd:02X}...")
        res = send_xh_cmd(h, cmd, apdu)
        if res:
            status = res[4]
            print(f"  Status: 0x{status:02X}")
            if status == 0x00:
                payload = bytes(res[5:5+res[2]-1])
                print(f"  SUCCESS! APDU Payload: {payload.hex().upper()}")
                # If success, we found the APDU command!
    
    h.close()

if __name__ == "__main__":
    main()
