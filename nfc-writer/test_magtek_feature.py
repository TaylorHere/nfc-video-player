import hid
import time

def main():
    VENDOR_ID = 0x0801
    PRODUCT_ID = 0x2011
    
    try:
        h = hid.device()
        h.open(VENDOR_ID, PRODUCT_ID)
        
        # MagTek Feature Report Command for Beep
        # Usually Report ID 0x01
        cmd = [0x01, 0x01, 0x03] # RID 1, Cmd 1, Beep 3?
        buf = [0] * 65
        for i, b in enumerate(cmd):
            buf[i] = b
            
        print("Sending Beep via Feature Report...")
        h.send_feature_report(buf)
        
        time.sleep(0.1)
        res = h.get_feature_report(0x01, 64)
        if res:
            print(f"Feature Report Response: {bytes(res).hex()}")
            
        h.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
