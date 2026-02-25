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
    
    print("Testing Beep variants...")
    # Try different command codes for Beep: 0x01, 0x06, 0x09
    for cmd in [0x01, 0x06, 0x09]:
        for param in [0x01, 0x05, 0x10, 0x32]:
            print(f"Trying Cmd 0x{cmd:02X} with Param 0x{param:02X}")
            res = send_xh_cmd(h, cmd, [param])
            if res:
                print(f"  Res: {bytes(res[:8]).hex().upper()}")
                if res[4] == 0x00:
                    print(f"  SUCCESS! Cmd 0x{cmd:02X} is Beep.")
                    h.close()
                    return
            time.sleep(0.2)
            
    h.close()

if __name__ == "__main__":
    main()
