#!/usr/bin/env python3
"""
Setup NTAG 424 DNA using libOURMIFARE.so
"""
import sys
import os
from ntag424_writer import Ntag424Writer

def main():
    try:
        writer = Ntag424Writer()
        print("Waiting for card...")
        info = writer.request_card()
        print(f"✓ Found card: {info['uid']}")
        
        writer.select_application("D2760000850101")
        
        print("Authenticating (Key 0)...")
        if not writer.authenticate(key_id=0):
            print("Authentication failed!")
            return
            
        # 1. Write NDEF URL
        # https://deo.app/nfc?p=00000000000000000000000000000000&m=0000000000000000
        # p (32 chars), m (16 chars)
        url = "https://deo.app/nfc?p=00000000000000000000000000000000&m=0000000000000000"
        writer.write_ndef_url(url, uri_header=0)
        
        # 2. Configure SDM
        # Calculated Offsets:
        # FileHeader(2) + NDEFHeader(4) + Prefix(1) = 7 bytes prefix.
        # "https://deo.app/nfc?p=" is 22 chars.
        # p_offset = 7 + 22 = 29.
        # p_len = 32.
        # "&m=" is 3 chars.
        # m_offset = 29 + 32 + 3 = 64.
        
        print("Configuring SDM (Plain Mirroring)...")
        # Use EncFileData (False) for debugging
        writer.configure_sun(
            picc_offset=29, 
            mac_offset=64,
            sdm_enc_length=32,
            use_enc_file_data=False
        )
        
        print("\nDone! Please test with App.")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
