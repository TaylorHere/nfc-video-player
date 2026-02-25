# NTAG 424 DNA Security Keys

Generated on: 2026-02-08

## Keys (AES-128)
- **K0 (Master Key)**: `D5A60346701B67C6A28B894B725DC23B` (Used for full access/config)
- **K1 (Meta Read)**: `2821CFC894E49B6ADEFD597A5FD4E9A0` (Used for UID/Counter mirroring)
- **K2 (File Read)**: `404FBDF5713ADB12F9416584494D4F9E` (Used for encrypted file data)
- **K3 (MAC/CMAC)**: `404FBDF5713ADB12F9416584494D4F9E` (Reusing K2 for simplicity in this demo)

## SDM Configuration
- **File ID**: 2 (NDEF File)
- **Communication Mode**: Plain (00) for URL, but with Encrypted Mirrored Data.
- **Protocol**: `myenc://sun?p=...&m=...`
