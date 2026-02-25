import usb.core
import usb.util

def reset_device():
    VENDOR_ID = 0x0801
    PRODUCT_ID = 0x2011
    
    dev = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
    if dev:
        print("Resetting device...")
        dev.reset()
        print("Done.")
    else:
        print("Device not found")

if __name__ == "__main__":
    reset_device()
