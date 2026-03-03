from ntag424_writer import Ntag424Writer, Ntag424Error
import sys

def main():
    print("Testing SUN Configuration with Ntag424Writer (DLL)...")
    try:
        writer = Ntag424Writer()
        
        # Check Reader Connection
        print("Checking Reader Connection...")
        try:
            serial = writer.get_device_serial()
            print(f"Reader Serial: {serial}")
        except Exception as e:
            print(f"Reader Check Failed: {e}")
            return

        # Connect
        print("Requesting Card...")
        writer.request_card()
        writer.select_application("D2760000850101")
        
        # Auth Key 0
        print("Authenticating with Key 0...")
        if not writer.authenticate(bytes(16), 0):
            print("Auth failed!")
            return
        
        # Configure SUN
        # Mode: Plain UID + CMAC (use_enc_file_data=False)
        print("Configuring SUN (Plain UID + CMAC)...")
        # picc_offset will be used for UID position since EncFile is OFF.
        # mac_offset for MAC.
        # MAC Input Offset = 0 (Start of file? Or after NDEF header?)
        # Let's set MAC Input Offset = 0 for now (or maybe start of NDEF record?)
        # But for Mirroring, MAC is usually over the URI string?
        # If MAC Input Offset is 0, it MACs from byte 0 of file?
        
        success = writer.configure_sun(
            picc_offset=42, 
            mac_offset=109, 
            sdm_mac_input_offset=0, # Start MAC from file beginning?
            use_enc_file_data=False
        )
        
        if success:
            print("✅ SUN Configuration SUCCESS!")
        else:
            print("❌ SUN Configuration FAILED.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()