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
        h.set_nonblocking(False)
        
        # Command: Request Card (ISO14443A)
        # Format: 78 68 [Len] [Cmd] [Sum]
        cmd = [0x78, 0x68, 0x01, 0x11]
        cmd.append(xh_checksum(cmd))
        
        # Wrap in HID Report 1
        buf = [0] * 65
        buf[0] = 0x01
        for i, b in enumerate(cmd):
            buf[i+1] = b
            
        print(f"Sending Request Card: {bytes(cmd).hex()}")
        h.write(buf)
        
        # Wait for response
        # Most NFC readers take some time to scan
        res = h.read(64, timeout_ms=1000)
        if res:
            print(f"Response: {bytes(res).hex()}")
        else:
            print("No response. Please put a card on the reader.")
            
        h.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
