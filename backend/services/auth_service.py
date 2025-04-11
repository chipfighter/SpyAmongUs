"""
services: auth_service

Description:
    JWT的鉴权相关的操作，实现双token机制

Notes:
    - Access Token: 用于API访问
    - Refresh Token: 用于刷新Access Token
"""

from datetime import datetime, timedelta
import jwt
from typing import Optional, Tuple, Dict

from config import (
    JWT_SECRET_KEY, JWT_ALGORITHM,
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
    JWT_REFRESH_TOKEN_EXPIRE_DAYS
)
from utils import logger_utils

logger = logger_utils.get_logger(__name__)

class AuthService:
    def __init__(self):
        self.algorithm = JWT_ALGORITHM
        self.access_token_expire_minutes = JWT_ACCESS_TOKEN_EXPIRE_MINUTES
        self.refresh_token_expire_days = JWT_REFRESH_TOKEN_EXPIRE_DAYS
        self.secret_key = JWT_SECRET_KEY
        logger.info("JWT服务已初始化")

    def create_tokens(self, user_id: str, username: str) -> Tuple[str, str]:
        """
        创建访问令牌和刷新令牌

        Returns:
             (access_token, refresh_token)
        """
        # 创建访问令牌
        access_expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        access_token = jwt.encode(
            {
                "sub": user_id,
                "username": username,
                "exp": access_expire,
                "type": "access"
            },
            self.secret_key,
            algorithm=self.algorithm
        )

        # 创建刷新令牌
        refresh_expire = datetime.utcnow() + timedelta(days=self.refresh_token_expire_days)
        refresh_token = jwt.encode(
            {
                "sub": user_id,
                "username": username,
                "exp": refresh_expire,
                "type": "refresh"
            },
            self.secret_key,
            algorithm=self.algorithm
        )

        return access_token, refresh_token

    def verify_token(self, token: str, token_type: str = "access") -> Tuple[bool, Optional[Dict]]:
        """
        验证令牌

        Args:
            token: JWT令牌
            token_type: 令牌类型 ("access" 或 "refresh")

        Returns:
             (是否有效, 载荷数据)
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            # 验证令牌类型
            if payload.get("type") != token_type:
                return False, None
            return True, payload
        except jwt.ExpiredSignatureError:
            return False, None
        except jwt.InvalidTokenError:
            return False, None

    def refresh_access_token(self, refresh_token: str) -> Optional[str]:
        """使用刷新令牌获取新的访问令牌"""
        is_valid, payload = self.verify_token(refresh_token, "refresh")
        if not is_valid or not payload:
            return None

        # 创建新的访问令牌
        return self.create_tokens(payload["sub"], payload["username"])[0]

    def get_user_id_from_token(self, token: str, token_type: str = "access") -> Optional[str]:
        """从令牌中获取用户ID"""
        is_valid, payload = self.verify_token(token, token_type)
        if is_valid and payload:
            return payload.get("sub")
        return None