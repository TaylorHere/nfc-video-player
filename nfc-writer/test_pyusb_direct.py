import usb.core
import usb.util
import time

def main():
    VENDOR_ID = 0x0801
    PRODUCT_ID = 0x2011
    
    dev = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
    if dev is None:
        print("Device not found")
        return
        
    print("Device found. Detaching kernel driver...")
    try:
        if dev.is_kernel_driver_active(0):
            dev.detach_kernel_driver(0)
    except Exception as e:
        print(f"Detach error: {e}")
        
    dev.set_configuration()
    
    # Endpoint addresses
    EP_IN = 0x81
    EP_OUT = 0x02
    
    # Send Search Command (0x10)
    # Header: 78 68, Len: 01, Cmd: 10, Sum: 78^68^01^10 = 01
    cmd = [0x78, 0x68, 0x01, 0x10, 0x01]
    buf = bytes(cmd + [0]*(64-len(cmd)))
    
    print(f"Sending Search: {buf[:8].hex().upper()}")
    dev.write(EP_OUT, buf)
    
    print("Reading response...")
    try:
        res = dev.read(EP_IN, 64, timeout=1000)
        print(f"Response: {bytes(res).hex().upper()}")
    except Exception as e:
        print(f"Read error: {e}")
        
    usb.util.dispose_resources(dev)

if __name__ == "__main__":
    main()
