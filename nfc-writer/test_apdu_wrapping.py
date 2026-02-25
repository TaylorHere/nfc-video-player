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
    
    # 1. Search & RATS
    send_xh_cmd(h, 0x10)
    send_xh_cmd(h, 0x20)
    
    # Simple APDU: Get Challenge (8 bytes)
    apdu = [0x00, 0x84, 0x00, 0x00, 0x08]
    
    print("Testing APDU wrappings for Cmd 0x22...")
    
    # Wrapping 1: Raw
    print("Wrapping 1: Raw APDU")
    res = send_xh_cmd(h, 0x22, apdu)
    if res: print(f"  Res: 0x{res[4]:02X}")
    
    # Wrapping 2: Len prefix (1 byte)
    print("Wrapping 2: Len prefix (1 byte)")
    res = send_xh_cmd(h, 0x22, [len(apdu)] + apdu)
    if res: print(f"  Res: 0x{res[4]:02X}")
    
    # Wrapping 3: 0x00 prefix (common in some readers)
    print("Wrapping 3: 0x00 prefix")
    res = send_xh_cmd(h, 0x22, [0x00] + apdu)
    if res: print(f"  Res: 0x{res[4]:02X}")
    
    h.close()

if __name__ == "__main__":
    main()
