"""
services: auth_service

Notes:
    - Access Token: 访问令牌（25min刷新一次）
    - Refresh Token: 刷新令牌（7天刷新一次）
"""
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

import jwt
from jwt import PyJWTError

from config import (
    JWT_SECRET_KEY,
    JWT_ALGORITHM,
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
    JWT_REFRESH_TOKEN_EXPIRE_DAYS,
)


class AuthService:
    def __init__(self):
        self.secret_key = JWT_SECRET_KEY
        self.algorithm = JWT_ALGORITHM
        self.access_token_expire = timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
        self.refresh_token_expire = timedelta(days=JWT_REFRESH_TOKEN_EXPIRE_DAYS)

    def create_tokens(self, user_id: str, username: str) -> Tuple[str, str]:
        """
        创建访问令牌和刷新令牌
        :param user_id: 用户ID
        :param username: 用户名
        :return: (access_token, refresh_token)
        """
        access_payload = {
            "sub": user_id,
            "username": username,
            "type": "access",
            "exp": datetime.utcnow() + self.access_token_expire,
            "iat": datetime.utcnow(),
        }
        refresh_payload = {
            "sub": user_id,
            "username": username,
            "type": "refresh",
            "exp": datetime.utcnow() + self.refresh_token_expire,
            "iat": datetime.utcnow(),
        }

        access_token = jwt.encode(access_payload, self.secret_key, algorithm=self.algorithm)
        refresh_token = jwt.encode(refresh_payload, self.secret_key, algorithm=self.algorithm)

        return access_token, refresh_token

    def verify_token(self, token: str, token_type: str = "access") -> Tuple[bool, Optional[Dict]]:
        """
        验证JWT令牌的有效性
        :param token: 要验证的令牌
        :param token_type: 令牌类型 ('access' 或 'refresh')
        :return: (是否有效, 载荷字典或None)
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            if payload["type"] != token_type:
                return False, None
            return True, payload
        except PyJWTError:
            return False, None

    def refresh_access_token(self, refresh_token: str) -> Optional[str]:
        """
        使用刷新令牌获取新的访问令牌
        :param refresh_token: 有效的刷新令牌
        :return: 新的访问令牌或None(如果刷新令牌无效)
        """
        is_valid, payload = self.verify_token(refresh_token, "refresh")
        if not is_valid or not payload:
            return None

        # 创建新的访问令牌
        new_access_payload = {
            "sub": payload["sub"],
            "username": payload["username"],
            "type": "access",
            "exp": datetime.utcnow() + self.access_token_expire,
            "iat": datetime.utcnow(),
        }
        return jwt.encode(new_access_payload, self.secret_key, algorithm=self.algorithm)

    def rotate_refresh_token(self, old_refresh_token: str) -> Optional[str]:
        """
        刷新令牌轮换(获取新的刷新令牌)
        :param old_refresh_token: 旧的刷新令牌
        :return: 新的刷新令牌或None(如果旧令牌无效)
        """
        is_valid, payload = self.verify_token(old_refresh_token, "refresh")
        if not is_valid or not payload:
            return None

        # 创建新的刷新令牌
        new_refresh_payload = {
            "sub": payload["sub"],
            "username": payload["username"],
            "type": "refresh",
            "exp": datetime.utcnow() + self.refresh_token_expire,
            "iat": datetime.utcnow(),
        }
        return jwt.encode(new_refresh_payload, self.secret_key, algorithm=self.algorithm)

    def get_user_id_from_token(self, token: str, token_type: str = "access") -> Optional[str]:
        """
        从令牌中提取用户ID
        :param token: JWT令牌
        :param token_type: 令牌类型 ('access' 或 'refresh')
        :return: 用户ID或None(如果令牌无效)
        """
        is_valid, payload = self.verify_token(token, token_type)
        return payload["sub"] if is_valid else None