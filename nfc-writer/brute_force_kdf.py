from Crypto.Cipher import AES
from Crypto.Hash import CMAC
from binascii import unhexlify

# Test Data from Log
RndA = unhexlify("b3106d325100f98272827fafae0ef23a")
RndB = unhexlify("cddb8365fba8560123f24a5f993d4b01")
EncResp = unhexlify("10a937a903fb144e970c24b02cb82fc86d5ed2be7ad52ddb18d3a93f107e4f83")
ExpRndA_Prime = unhexlify("106d325100f98272827fafae0ef23ab3")
Key = bytes(16) # Key 0 (Zeros)

def rotate_left(data):
    return data[1:] + data[:1]

RndB_Prime = rotate_left(RndB)

def xor(a, b):
    return bytes([x ^ y for x, y in zip(a, b)])

def test_kdf(sv_prefix, rnd_a_ver, rnd_b_ver, suffix_mode=0):
    # Construct SV
    if suffix_mode == 0:
        # Standard EV2 Suffix
        # RndA[0:2] + (RndA[2:8] ^ RndB[0:6]) + RndB[12:16] + RndA[12:16]
        sv_suffix = rnd_a_ver[0:2] + xor(rnd_a_ver[2:8], rnd_b_ver[0:6]) + rnd_b_ver[12:16] + rnd_a_ver[12:16]
    elif suffix_mode == 1:
        # Simple concat
        sv_suffix = rnd_a_ver + rnd_b_ver
    elif suffix_mode == 2:
        # 01 54 49 logic (using TI)
        # Try different TI values
        if isinstance(rnd_a_ver, bytes) and len(rnd_a_ver) == 4:
             ti = rnd_a_ver
        else:
             ti = bytes(4) # Default 00 00 00 00
             
        # Logic: TI + (RndA[14]^RndB[14]) + (RndA[15]^RndB[15]) + Zeros(7)
        # Note: RndA/RndB here are full 16 bytes passed in rnd_a_ver/rnd_b_ver
        # If rnd_a_ver is 4 bytes (TI), we need full RndA/RndB.
        # We need to restructure test_kdf to accept TI.
        return None

def test_kdf_ti(sv_prefix, rnd_a, rnd_b, ti_val):
    # Logic 01 54 49
    b1 = rnd_a[14] ^ rnd_b[14]
    b2 = rnd_a[15] ^ rnd_b[15]
    sv_suffix = ti_val + bytes([b1, b2]) + b'\x00' * 7
    sv = sv_prefix + sv_suffix
    
    # Derive Key
    c = CMAC.new(Key, ciphermod=AES)
    c.update(sv)
    key_enc = c.digest()
    
    # Decrypt
    iv = bytes(16)
    cipher = AES.new(key_enc, AES.MODE_CBC, iv)
    try:
        decrypted = cipher.decrypt(EncResp)
        if ExpRndA_Prime in decrypted:
            print(f"FOUND! Prefix={sv_prefix.hex()}, TI={ti_val.hex()}")
            print(f"KeyEnc: {key_enc.hex()}")
            print(f"Decrypted: {decrypted.hex()}")
            return key_enc
    except:
        pass
    return None

# ... (Previous loops) ...

# Try TI variations
ti_vars = [
    bytes(4), # 00000000
    EncResp[:4], # First 4 bytes of EncResp
    RndA[:4],
    RndB[:4],
    RndA[12:16],
    RndB[12:16]
]

print("Starting Brute Force (TI)...")
prefix_ti = bytes.fromhex("015445") # Try ENC constant? 45?
# Also try 015482
prefixes_ti = [bytes.fromhex("015445"), bytes.fromhex("015482"), bytes.fromhex("015449")]

for p in prefixes_ti:
    for ti in ti_vars:
        test_kdf_ti(p, RndA, RndB, ti)
        test_kdf_ti(p, RndA, RndB_Prime, ti) # Try RndB' too

print("Done.")