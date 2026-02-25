from smartcard.System import readers
try:
    r = readers()
    print(f"Available readers: {r}")
except Exception as e:
    print(f"Error: {e}")
