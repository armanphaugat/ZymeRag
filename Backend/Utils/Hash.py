from argon2 import PasswordHasher
ph=PasswordHasher()

async def hash_password(password: str) -> str:
    try:
        hashed_password = ph.hash(password)
        return hashed_password
    except Exception as e:
        print( f"Error occurred while hashing password: {e}")

async def verify_password(password: str, hashed_password: str) -> bool:
    try:
        return ph.verify(hashed_password, password)
    except Exception as e:
        print(f"Error occurred while verifying password: {e}")
        return False