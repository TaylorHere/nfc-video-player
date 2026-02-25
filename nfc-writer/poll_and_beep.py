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
    res = h.read(64, timeout_ms=200)
    return list(res) if res else None

def main():
    try:
        h = hid.device()
        h.open(0x0801, 0x2011)
        print("Device opened. Polling for card...")
    except:
        print("Failed to open device.")
        return

    while True:
        res = send_xh_cmd(h, 0x10)
        if res and res[4] == 0x00:
            uid = bytes(res[5:12]).hex().upper()
            print(f"Card Detected! UID: {uid}")
            
            # Try to Beep
            print("Sending Beep...")
            # Try both variants: [0x01] and [0x01, 0x10]
            send_xh_cmd(h, 0x01, [0x10])
            
            time.sleep(1) # Wait after beep
        time.sleep(0.5)

if __name__ == "__main__":
    main()
