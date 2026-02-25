import hid
import time

def main():
    VENDOR_ID = 0x0801
    PRODUCT_ID = 0x2011
    
    try:
        h = hid.device()
        h.open(VENDOR_ID, PRODUCT_ID)
        h.set_nonblocking(True)
        
        for cmd in range(0x00, 0x30): # Scan first 48 commands
            pkt = [0x78, 0x68, 0x01, cmd]
            chk = 0
            for b in pkt: chk ^= b
            pkt.append(chk)
            
            buf = [0] * 65
            buf[0] = 0x01
            for i, b in enumerate(pkt):
                buf[i+1] = b
            
            h.write(buf)
            time.sleep(0.05)
            res = h.read(64)
            if res:
                print(f"Cmd {hex(cmd)} -> {bytes(res).hex()}")
                
        h.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
