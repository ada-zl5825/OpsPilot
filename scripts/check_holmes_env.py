import os

print("KEY_LEN", len(os.environ.get("AZURE_API_KEY", "")))
print("BASE_LEN", len(os.environ.get("AZURE_API_BASE", "")))
print("MODEL", os.environ.get("HOLMES_MODEL", ""))
print("VER", os.environ.get("AZURE_API_VERSION", ""))
