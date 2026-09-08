"""密码哈希(bcrypt)。"""
import bcrypt


def hash_password(plain: str) -> str:
    """bcrypt hash,60 字符。"""
    # bcrypt 限制 72 字节,过长密码截断或 reject?
    # 这里直接 reject(由 Pydantic Field(max_length=128) 守护,实际 72 字节内)
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(plain.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """校验密码。"""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False