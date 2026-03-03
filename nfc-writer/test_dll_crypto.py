import ctypes
import os
import sys
from binascii import unhexlify

# Load DLL
dll_name = os.path.abspath('OUR_MIFARE.dll')
if not os.path.exists(dll_name):
    print(f"Error: {dll_name} not found")
    sys.exit(1)

try:
    # Use AddDllDirectory for dependencies if needed (Python 3.8+)
    if hasattr(os, 'add_dll_directory'):
        os.add_dll_directory(os.path.dirname(dll_name))
    lib = ctypes.cdll.LoadLibrary(dll_name)
    print(f"Loaded {dll_name}")
except Exception as e:
    print(f"Failed to load DLL: {e}")
    sys.exit(1)

# Define Function Signatures based on Module1.bas
# Public Declare Sub cpucalcexauthkey Lib "OUR_MIFARE.dll" (ByRef randdata As Byte, ByRef key As Byte, ByVal keylen As Byte, ByRef result As Byte)
# randdata: Likely RndA + RndB? (32 bytes?)
# key: Master Key (16 bytes)
# keylen: 16
# result: Session Key? (16 bytes? Or 32 bytes for ENC+MAC?)

# Test Data from Run 8
RndA = unhexlify("b3106d325100f98272827fafae0ef23a")
RndB = unhexlify("cddb8365fba8560123f24a5f993d4b01")
EncResp = unhexlify("10a937a903fb144e970c24b02cb82fc86d5ed2be7ad52ddb18d3a93f107e4f83")
ExpRndA_Prime = unhexlify("106d325100f98272827fafae0ef23ab3")
Key = bytes(16) # Key 0

# Buffer types
Byte16 = ctypes.c_ubyte * 16
Byte32 = ctypes.c_ubyte * 32
Byte64 = ctypes.c_ubyte * 64

def test_kdf_dll(rnd_a, rnd_b):
    print("\nTesting DLL KDF...")
    
    # Prepare Inputs
    # randdata: Try RndA + RndB (32 bytes)
    randdata = Byte32(*list(rnd_a + rnd_b))
    key_buf = Byte16(*list(Key))
    key_len = 16
    result_buf = Byte32() # Maybe it returns both keys? Or 16 bytes?
    
    try:
        # Call cpucalcexauthkey
        # Note: Module1.bas says Sub, so no return value.
        # Arguments are ByRef.
        lib.cpucalcexauthkey(ctypes.byref(randdata), ctypes.byref(key_buf), key_len, ctypes.byref(result_buf))
        
        # Result
        res_bytes = bytes(result_buf)
        print(f"DLL Result: {res_bytes.hex()}")
        
        # Split into KeyEnc and KeyMac?
        key_enc = res_bytes[:16]
        key_mac = res_bytes[16:]
        
        print(f"KeyEnc: {key_enc.hex()}")
        
        # Try to decrypt EncResp
        from Crypto.Cipher import AES
        iv = bytes(16)
        cipher = AES.new(key_enc, AES.MODE_CBC, iv)
        decrypted = cipher.decrypt(EncResp)
        print(f"Decrypted: {decrypted.hex()}")
        
        if ExpRndA_Prime in decrypted:
            print("✅ SUCCESS! DLL Key matches RndA'!")
            return key_enc
        else:
            print("❌ Mismatch.")
            
            # Try other combinations
            # Maybe KeyMac is first?
            cipher = AES.new(key_mac, AES.MODE_CBC, iv)
            decrypted = cipher.decrypt(EncResp)
            if ExpRndA_Prime in decrypted:
                print("✅ SUCCESS! DLL Key (2nd part) matches RndA'!")
                return key_mac
                
    except Exception as e:
        print(f"DLL Call Failed: {e}")

if __name__ == "__main__":
    test_kdf_dll(RndA, RndB)
    # Also try RndB + RndA?
    test_kdf_dll(RndB, RndA)