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
    if not res: return None
    return list(res)

def main():
    try:
        h = hid.device()
        h.open(0x0801, 0x2011)
        print("Device opened.")
    except Exception as e:
        print(f"Open failed: {e}")
        return
    
    cmds = [
        (0x11, [0x26], "REQA"),
        (0x11, [0x52], "WUPA"),
        (0x12, [], "Anticollision"),
        (0x20, [], "RATS"),
        (0x10, [], "Get UID/Info"),
    ]
    
    for code, data, name in cmds:
        print(f"\n--- {name} (0x{code:02X}) ---")
        res = send_xh_cmd(h, code, data)
        if res:
            print(f"Raw: {bytes(res[:16]).hex().upper()}")
            if len(res) >= 5:
                status = res[4]
                print(f"Status: 0x{status:02X}")
                if status == 0x00:
                    payload = bytes(res[5:5+res[2]-1])
                    print(f"Payload: {payload.hex().upper()}")
        else:
            print("No response")
            
    h.close()

if __name__ == "__main__":
    main()
