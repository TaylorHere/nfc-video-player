import hid
import time

def main():
    VENDOR_ID = 0x0801
    PRODUCT_ID = 0x2011
    
    try:
        h = hid.device()
        h.open(VENDOR_ID, PRODUCT_ID)
        
        # XH Beep Command: 78 68 01 01 10
        # RID 1
        buf = [0] * 65
        buf[0] = 0x01
        buf[1] = 0x78
        buf[2] = 0x68
        buf[3] = 0x01
        buf[4] = 0x01
        buf[5] = 0x10
        
        print("Sending Beep...")
        h.write(buf)
        time.sleep(0.1)
        res = h.read(64, timeout_ms=500)
        if res:
            print(f"Response: {bytes(res).hex()}")
            
        h.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
