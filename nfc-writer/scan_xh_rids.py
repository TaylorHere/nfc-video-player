import hid
import time

def main():
    VENDOR_ID = 0x0801
    PRODUCT_ID = 0x2011
    
    try:
        h = hid.device()
        h.open(VENDOR_ID, PRODUCT_ID)
        h.set_nonblocking(True)
        
        for rid in [0x00, 0x01, 0x02, 0x03, 0x04]:
            print(f"Testing Report ID {hex(rid)}...")
            pkt = [0x78, 0x68, 0x01, 0x02] # Get Version
            chk = 0
            for b in pkt: chk ^= b
            pkt.append(chk)
            
            buf = [0] * 65
            buf[0] = rid
            for i, b in enumerate(pkt):
                if i < 64: buf[i+1] = b
            
            h.write(buf)
            time.sleep(0.1)
            res = h.read(64)
            if res:
                print(f"Response (RID {hex(rid)}): {bytes(res).hex()}")
                
        h.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
