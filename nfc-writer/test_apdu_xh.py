import hid
import time

def xh_checksum(data):
    chk = 0
    for b in data:
        chk ^= b
    return chk

def main():
    VENDOR_ID = 0x0801
    PRODUCT_ID = 0x2011
    
    try:
        h = hid.device()
        h.open(VENDOR_ID, PRODUCT_ID)
        
        # Select NDEF APDU
        apdu = [0x00, 0xA4, 0x04, 0x00, 0x07, 0xD2, 0x76, 0x00, 0x00, 0x85, 0x01, 0x01]
        
        # XH Protocol wrapping: 78 68 [Len] [Cmd 0x05] [APDU...] [Sum]
        cmd_code = 0x05
        pkt = [0x78, 0x68, len(apdu)+1, cmd_code] + apdu
        pkt.append(xh_checksum(pkt))
        
        buf = [0x01] + pkt + [0]*(64-len(pkt))
        print(f"Sending Select NDEF (XH): {bytes(pkt).hex()}")
        h.write(buf)
        
        time.sleep(0.2)
        res = h.read(64, timeout_ms=500)
        if res:
            print(f"Response: {bytes(res).hex()}")
        else:
            print("No response")
            
        h.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
