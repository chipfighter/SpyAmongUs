"""
services: auth_service

Description:
    JWT的鉴权相关的操作，实现双token机制

Notes:
    - Access Token: 用于API访问
    - Refresh Token: 用于刷新Access Token

    创建双tokens、验证token、刷新access_token、轮换refresh_token、从token中得到用户id
"""

from datetime import datetime, timedelta
import jwt
from typing import Optional, Tuple, Dict
from uuid import uuid4

from config import (
    JWT_SECRET_KEY, JWT_ALGORITHM,
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
    JWT_REFRESH_TOKEN_EXPIRE_DAYS
)
from utils import logger_utils

logger = logger_utils.get_logger(__name__)

class AuthService:
    """
    services: auth_service

    Description:
        提供JWT令牌的创建、验证和刷新功能
    """
    def __init__(self):
        self.algorithm = JWT_ALGORITHM
        self.access_token_expire_minutes = JWT_ACCESS_TOKEN_EXPIRE_MINUTES
        self.refresh_token_expire_days = JWT_REFRESH_TOKEN_EXPIRE_DAYS
        self.secret_key = JWT_SECRET_KEY
        logger.info("JWT服务已初始化")

    def create_tokens(self, user_id: str, username: str) -> Tuple[str, str]:
        """
        Description:
            创建访问令牌和刷新令牌

        Args:
            user_id: 用户唯一标识
            username: 用户名

        Returns:
            Tuple[str, str]: (access_token, refresh_token)
        """
        now = datetime.utcnow()

        # 创建访问令牌
        access_payload = {
            "jti": str(uuid4()),
            "sub": user_id,
            "username": username,
            "exp": int((now + timedelta(minutes=self.access_token_expire_minutes)).timestamp()),
            "type": "access",
            "iat": int(now.timestamp())
        }
        access_token = jwt.encode(access_payload, self.secret_key, algorithm=self.algorithm)

        # 创建刷新令牌
        refresh_payload = {
            "jti": str(uuid4()),
            "sub": user_id,
            "username": username,
            "exp": int((now + timedelta(days=self.refresh_token_expire_days)).timestamp()),
            "type": "refresh",
            "iat": int(now.timestamp()),
            "parent_jti": access_payload["jti"]
        }
        refresh_token = jwt.encode(refresh_payload, self.secret_key, algorithm=self.algorithm)

        return access_token, refresh_token

    def verify_token(self, token: str, token_type: str = "access") -> Tuple[bool, Optional[Dict]]:
        """
        Description:
            验证JWT令牌有效性

        Args:
            token: 待验证的JWT令牌
            token_type: 令牌类型 ("access"或"refresh")

        Returns:
            Tuple[bool, Optional[Dict]]: (是否有效, 解码后的payload)
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            if payload.get("type") != token_type:
                return False, None
            return True, payload
        except jwt.ExpiredSignatureError:
            return False, None
        except jwt.InvalidTokenError:
            return False, None

    def refresh_access_token(self, refresh_token: str) -> Optional[str]:
        """仅返回新的Access Token，保持原Refresh Token不变"""
        is_valid, payload = self.verify_token(refresh_token, "refresh")
        if not is_valid or not payload:
            return None

        # 仅生成新Access Token（复用原Refresh Token的payload数据）
        new_access_token = jwt.encode(
            {
                "jti": str(uuid4()),  # 新的JTI
                "sub": payload["sub"],
                "username": payload["username"],
                "exp": int((datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)).timestamp()),
                "type": "access",
                "iat": int(datetime.utcnow().timestamp())
            },
            self.secret_key,
            algorithm=self.algorithm
        )
        return new_access_token

    def rotate_refresh_token(self, old_refresh_token: str) -> Optional[str]:
        """安全事件发生时强制刷新Refresh Token"""
        is_valid, payload = self.verify_token(old_refresh_token, "refresh")
        if not is_valid:
            return None

        new_refresh_token = jwt.encode(
            {
                "jti": str(uuid4()),
                "sub": payload["sub"],
                "exp": int((datetime.utcnow() + timedelta(days=self.refresh_token_expire_days)).timestamp()),
                "type": "refresh",
                "iat": int(datetime.utcnow().timestamp())
            },
            self.secret_key,
            algorithm=self.algorithm
        )
        return new_refresh_token

    def get_user_id_from_token(self, token: str, token_type: str = "access") -> Optional[str]:
        """
        Description:
            从令牌中提取用户ID

        Args:
            token: JWT令牌
            token_type: 令牌类型 ("access"或"refresh")

        Returns:
            Optional[str]: 用户ID或None(令牌无效时)
        """
        is_valid, payload = self.verify_token(token, token_type)
        return payload.get("sub") if is_valid else None