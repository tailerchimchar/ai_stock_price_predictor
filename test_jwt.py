"""
Quick test to verify JWT validation is working.
Run this after starting the backend with: uvicorn app.main:app --reload
"""
import os
from dotenv import load_dotenv
from jose import jwt
import datetime

load_dotenv()

SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")

# Create a test JWT (simulating Supabase)
test_payload = {
    "sub": "12345678-1234-1234-1234-123456789012",  # Fake user UUID
    "email": "test@example.com",
    "iat": datetime.datetime.now(datetime.timezone.utc),
    "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1),
}

# Sign the token
test_token = jwt.encode(test_payload, SUPABASE_JWT_SECRET, algorithm="HS256")

print("=" * 60)
print("JWT Validation Test")
print("=" * 60)
print(f"\n✓ JWT Secret loaded: {SUPABASE_JWT_SECRET[:20]}...")
print(f"\n✓ Test Token Generated:")
print(f"  {test_token[:50]}...")
print(f"\n✓ Test User ID: {test_payload['sub']}")
print(f"\n✓ Test Email: {test_payload['email']}")

# Try to decode it
try:
    decoded = jwt.decode(test_token, SUPABASE_JWT_SECRET, algorithms=["HS256"])
    print(f"\n✅ Token validation SUCCESS!")
    print(f"   Extracted user_id: {decoded['sub']}")
except Exception as e:
    print(f"\n❌ Token validation FAILED: {e}")

print("\n" + "=" * 60)
print("Next Steps:")
print("=" * 60)
print("1. Start backend: uvicorn app.main:app --reload")
print("2. Start frontend: cd web && npm run dev")
print("3. Visit http://localhost:3000/auth")
print("4. Sign up with a real email")
print("5. Confirm email and sign in")
print("6. Try running an analysis")
print("=" * 60)
