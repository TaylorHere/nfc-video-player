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
    send_xh_cmd(h, 0x20)
    
    # NTAG 424 Get Version APDU
    apdu = [0x90, 0x60, 0x00, 0x00, 0x00]
    
    print("Trying NTAG Get Version (90 60)...")
    res = send_xh_cmd(h, 0x22, apdu)
    if res:
        print(f"Res Status: 0x{res[4]:02X}")
        if len(res) > 5:
            print(f"Data: {bytes(res[5:5+res[2]-1]).hex().upper()}")

    h.close()

if __name__ == "__main__":
    main()
