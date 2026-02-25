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
    
    send_xh_cmd(h, 0x10)
    
    print("Testing Cmd 0x12 Payload...")
    res = send_xh_cmd(h, 0x12)
    if res:
        payload = bytes(res[5:5+res[2]-1])
        print(f"   Status: 0x{res[4]:02X}")
        print(f"   Payload: {payload.hex().upper()}")
        
    print("\nTesting Cmd 0x12 with [0x01]...")
    res = send_xh_cmd(h, 0x12, [0x01])
    if res:
        payload = bytes(res[5:5+res[2]-1])
        print(f"   Status: 0x{res[4]:02X}")
        print(f"   Payload: {payload.hex().upper()}")
        
    h.close()

if __name__ == "__main__":
    main()
