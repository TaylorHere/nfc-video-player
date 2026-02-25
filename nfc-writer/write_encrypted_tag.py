import sys
import os
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from ntag424_writer import Ntag424Writer

# Config
KEY = b'12345678901234567890123456789012' # 32 bytes (AES-256)
IV = b'1234567890123456'  # 16 bytes
TARGET_URL = 'https://investigator-image.oss-cn-shanghai.aliyuncs.com/eightnong/video/1.mp4'
LIB_PATH = '/media/deo/2680-1FFD/extra_docs/Python_Ntag424DNA_Win_Linux/libOURMIFARE.so'

def encrypt_url(url):
    cipher = AES.new(KEY, AES.MODE_CBC, IV)
    ct_bytes = cipher.encrypt(pad(url.encode('utf-8'), AES.block_size))
    return ct_bytes.hex().upper()

def main():
    print(f"Target URL: {TARGET_URL}")
    encrypted_payload = encrypt_url(TARGET_URL)
    full_scheme = f"myenc://{encrypted_payload}"
    print(f"Encrypted Scheme: {full_scheme}")
    
    try:
        writer = Ntag424Writer(lib_path=LIB_PATH)
        print("Waiting for card...")
        info = writer.request_card()
        print(f"Found card: {info['uid']} ({info['card_type']})")
        
        writer.select_application("D2760000850101")
        print("Authenticating...")
        if not writer.authenticate():
            print("Auth failed (using default key). Is the card initialized?")
            # Try to proceed anyway or fail? NDEF writing usually requires auth if configured
            # But default cards are usually 00 key.
            # If failed, maybe try to change key back to 00? No, unsafe.
            pass 
        
        print("Writing NDEF...")
        # uri_header=0 means "No Prefix", so we write the full custom scheme
        writer.write_ndef_url(full_scheme, title="Encrypted Video", uri_header=0)
        
        print("Done!")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    main()
