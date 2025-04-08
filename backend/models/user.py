"""
model: User
"""
from pydantic import BaseModel
from typing import Optional
import uuid
import hashlib
import secrets
import string


class User(BaseModel):
    id: str                 # 用户ID
    username: str           # 用户名
    password_hash: Optional[str] = None     # 密码哈希（存储）
    salt: Optional[str] = None              # 密码盐值
    avatar_url: Optional[str] = None        # 头像URL

    # 不返回敏感字段
    class Config:
        json_schema_extra = {
            "example": {
                "id": "user-1",
                "username": "测试用户",
                "avatar_url": None
            }
        }
        
    def dict(self, *args, **kwargs):
        """重写dict方法，排除敏感信息（盐值+密码Hash值）"""
        data = super().dict(*args, **kwargs)
        data.pop("password_hash", None)
        data.pop("salt", None)
        return data

    @classmethod
    def create_temp_user(cls, user_id: str, username: str) -> 'User':
        """创建临时用户"""
        return cls(
            id=user_id,
            username=username
        )

    @staticmethod
    def hash_password(password: str, salt: str = None) -> tuple:
        """密码和盐值设定"""
        # 如果没有提供盐值，生成一个新的
        if not salt:
            # 生成16位随机盐值
            salt = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(16))
        
        # 将密码和盐值组合后进行哈希（sha256加密）
        password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
        
        return password_hash, salt

    @classmethod
    def create_user(cls, username: str, password: str) -> 'User':
        """根据用户名+密码，创建带密码的用户"""
        # 生成12位用户ID
        user_id = f"usr_{uuid.uuid4().hex[:12]}"
        
        # 加密密码+初始化盐值
        password_hash, salt = cls.hash_password(password)
        
        return cls(
            id=user_id,
            username=username,
            password_hash=password_hash,
            salt=salt
        )

    def verify_password(self, password: str) -> bool:
        """验证密码"""
        if not self.password_hash or not self.salt:
            return False
            
        # 使用相同的盐值哈希输入的密码
        password_hash, _ = self.hash_password(password, self.salt)
        
        # 比较哈希值
        return password_hash == self.password_hash