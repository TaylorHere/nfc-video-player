import hid
import time

def main():
    VENDOR_ID = 0x0801
    PRODUCT_ID = 0x2011
    
    try:
        h = hid.device()
        h.open(VENDOR_ID, PRODUCT_ID)
        
        # Cmd 0x02: Get Device Info
        pkt = [0x78, 0x68, 0x01, 0x02, 0x13]
        buf = [0x01] + pkt + [0]*(64-len(pkt))
        
        print(f"Sending Get Info: {bytes(pkt).hex()}")
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
