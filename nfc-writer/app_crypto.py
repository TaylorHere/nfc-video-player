
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import binascii

# Configuration from main.dart
# final _encKey = enc.Key.fromUtf8('12345678901234567890123456789012');
# final _encIV = enc.IV.fromUtf8('1234567890123456');

KEY = b'12345678901234567890123456789012'
IV = b'1234567890123456'

def encrypt_url_for_app(plain_url):
    """
    Encrypts a URL using AES-CBC-PKCS7 to match the Flutter app's expectation.
    Returns format: myenc://<hex_string>
    """
    cipher = AES.new(KEY, AES.MODE_CBC, IV)
    padded_data = pad(plain_url.encode('utf-8'), AES.block_size)
    encrypted_bytes = cipher.encrypt(padded_data)
    hex_data = binascii.hexlify(encrypted_bytes).decode('utf-8')
    return f"myenc://{hex_data}"

if __name__ == "__main__":
    # Test with a sample video
    sample_video = "https://flutter.github.io/assets-for-api-docs/assets/videos/bee.mp4"
    encrypted = encrypt_url_for_app(sample_video)
    print(f"Original: {sample_video}")
    print(f"Encrypted: {encrypted}")
