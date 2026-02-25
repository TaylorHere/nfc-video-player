#!/usr/bin/env python3
"""
MagTek IC-02 UID Dump & APDU Test
"""
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
    return res

def main():
    VENDOR_ID = 0x0801
    PRODUCT_ID = 0x2011
    
    try:
        h = hid.device()
        h.open(VENDOR_ID, PRODUCT_ID)
        print("Device opened.")
        
        # 1. Get UID/Info (Cmd 0x10)
        print("\n--- Getting UID/Info (Cmd 0x10) ---")
        res = send_xh_cmd(h, 0x10)
        if res:
            print(f"Full Response (hex): {bytes(res).hex()}")
            if res[0] == 0x78 and res[1] == 0x68:
                rlen = res[2]
                status = res[4]
                if status == 0x00:
                    uid_len = res[5]
                    uid = bytes(res[6:6+uid_len])
                    print(f"Status: Success (0x00)")
                    print(f"UID Length: {uid_len}")
                    print(f"UID: {uid.hex().upper()}")
                    
                    # Also print the rest of the response
                    extra = bytes(res[6+uid_len:6+rlen-1])
                    print(f"Extra Data: {extra.hex().upper()}")
        
        # 2. Select NDEF APDU (Cmd 0x22)
        print("\n--- Selecting NDEF Application (Cmd 0x22) ---")
        apdu = [0x00, 0xA4, 0x04, 0x00, 0x07, 0xD2, 0x76, 0x00, 0x00, 0x85, 0x01, 0x01]
        res = send_xh_cmd(h, 0x22, apdu)
        if res:
            print(f"APDU Response (hex): {bytes(res).hex()}")
            if res[0] == 0x78 and res[1] == 0x68:
                rlen = res[2]
                # XH response: [Header][Header][Len][Cmd][Status][Data...][Sum]
                status = res[4]
                data = res[5:5+rlen-1]
                print(f"XH Status: 0x{status:02X}")
                print(f"APDU Data: {data.hex().upper()}")
        
        h.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
