import usb.core
import usb.util
import time
import sys

def test_pyusb():
    VENDOR_ID = 0x0801
    PRODUCT_ID = 0x2011
    
    dev = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
    if dev is None:
        print("Device not found")
        return

    # Detach all interfaces
    for intf_num in [0, 1]: # Usually just 0
        try:
            if dev.is_kernel_driver_active(intf_num):
                dev.detach_kernel_driver(intf_num)
                print(f"Detached interface {intf_num}")
        except:
            pass

    try:
        dev.set_configuration()
        usb.util.claim_interface(dev, 0)
    except Exception as e:
        print(f"Claim error: {e}")
        # Try to continue if already set
        pass

    cfg = dev.get_active_configuration()
    intf = cfg[(0,0)]
    
    ep_out = usb.util.find_descriptor(
        intf,
        custom_match = lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT
    )
    ep_in = usb.util.find_descriptor(
        intf,
        custom_match = lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN
    )
    
    print(f"EP OUT: {ep_out.bEndpointAddress if ep_out else 'None'}")
    print(f"EP IN: {ep_in.bEndpointAddress if ep_in else 'None'}")
    
    if ep_out and ep_in:
        # Get Version: 78 68 01 02 13
        cmd = [0x78, 0x68, 0x01, 0x02, 0x13]
        print(f"Sending: {bytes(cmd).hex()}")
        ep_out.write(cmd)
        
        try:
            data = ep_in.read(64, timeout=1000)
            print(f"Received: {bytes(data).hex()}")
        except Exception as e:
            print(f"Read error: {e}")

if __name__ == "__main__":
    test_pyusb()
