"""
认证相关 API 路由

包含: 注册、登录、登出、获取用户信息、刷新Token、轮换Token
迁移自 main.py 第 672-931 行
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from typing import Dict
from utils.logger_utils import get_logger
from dependencies import user_service, auth_service, redis_client

logger = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["auth"])


@router.post("/register")
async def register(user_data: Dict[str, str]):
    """用户注册API"""
    try:
        result = await user_service.register(user_data["username"], user_data["password"])
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except Exception as e:
        logger.error(f"用户注册失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/login")
async def login(user_data: Dict[str, str]):
    """用户登录API"""
    try:
        result = await user_service.login(user_data["username"], user_data["password"])
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except Exception as e:
        logger.error(f"用户登录失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/logout")
async def logout(request: Request):
    """用户登出API"""
    try:
        # 从请求状态中获取用户ID（中间件已验证）
        user_id = request.state.user_id

        result = await user_service.logout(user_id)
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except AttributeError as ae:
        # 处理request.state.user_id不存在的情况
        logger.error(f"登出时属性错误: {str(ae)}")
        raise HTTPException(status_code=401, detail="未授权，请重新登录")
    except Exception as e:
        logger.error(f"用户登出失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/user/{user_id}")
async def get_user_info(user_id: str, request: Request):
    """获取用户信息API"""
    try:
        logger.debug(f"获取用户信息请求: 目标用户ID={user_id}, 请求用户ID={getattr(request.state, 'user_id', 'unknown')}")
        
        # 检查当前登录用户是否有权限访问此信息
        if not hasattr(request.state, 'user_id'):
            logger.warning(f"尝试访问用户信息但未经身份验证: 目标={user_id}")
            raise HTTPException(status_code=401, detail="未授权，请重新登录")
            
        if request.state.user_id != user_id:
            logger.warning(f"用户尝试访问其他用户信息: 请求用户={request.state.user_id}, 目标用户={user_id}")
            raise HTTPException(status_code=403, detail="无权访问此用户信息")
            
        result = await user_service.get_user_info(user_id)
        if not result["success"]:
            logger.warning(f"获取用户信息失败: {result['message']}")
            raise HTTPException(status_code=404, detail=result["message"])
            
        logger.debug(f"成功获取用户信息: {user_id}")
        return result
    except HTTPException:
        # 重新抛出HTTP异常
        raise
    except Exception as e:
        logger.error(f"获取用户信息发生错误: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/token/refresh")
async def refresh_token(request: Request):
    """刷新访问令牌API

    从refresh_token获取新的access_token，保持用户登录状态
    """
    try:
        # 1. 获取refresh_token
        refresh_token = None

        # 尝试从请求体JSON中获取
        try:
            body = await request.json()
            refresh_token = body.get("refresh_token")
            if refresh_token:
                logger.debug("成功从JSON请求体获取refresh_token")
        except:
            logger.debug("请求体不是有效的JSON格式")

        # 如果未从JSON获取到，尝试从表单中获取
        if not refresh_token:
            try:
                form = await request.form()
                refresh_token = form.get("refresh_token")
                if refresh_token:
                    logger.debug("成功从表单获取refresh_token")
            except:
                logger.debug("请求体不是有效的表单格式")

        # 最后尝试从查询参数获取
        if not refresh_token:
            refresh_token = request.query_params.get("refresh_token")
            if refresh_token:
                logger.debug("成功从查询参数获取refresh_token")

        # 2. 验证是否获取到refresh_token
        if not refresh_token:
            logger.warning("刷新令牌请求缺少refresh_token参数")
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": "缺少refresh_token参数"
                }
            )

        # 3. 使用auth_service刷新访问令牌
        new_access_token = auth_service.refresh_access_token(refresh_token)

        # 4. 检查返回结果
        if not new_access_token:
            logger.warning("无效的刷新令牌")
            return JSONResponse(
                status_code=401,
                content={
                    "success": False,
                    "message": "无效的刷新令牌"
                }
            )

        # 5. 返回新的访问令牌
        logger.info("访问令牌刷新成功")
        return {
            "success": True,
            "message": "访问令牌刷新成功",
            "data": {
                "access_token": new_access_token
            }
        }

    except Exception as e:
        logger.error(f"刷新访问令牌过程中发生错误: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"刷新访问令牌失败: {str(e)}"
            }
        )

@router.post("/token/rotate")
async def rotate_token(request: Request):
    """轮换令牌API

    在安全事件发生时，同时刷新访问令牌和刷新令牌
    """
    try:
        # 1. 获取refresh_token
        refresh_token = None

        # 尝试从请求体JSON中获取
        try:
            body = await request.json()
            refresh_token = body.get("refresh_token")
            if refresh_token:
                logger.debug("成功从JSON请求体获取refresh_token")
        except:
            logger.debug("请求体不是有效的JSON格式")

        # 如果未从JSON获取到，尝试从表单中获取
        if not refresh_token:
            try:
                form = await request.form()
                refresh_token = form.get("refresh_token")
                if refresh_token:
                    logger.debug("成功从表单获取refresh_token")
            except:
                logger.debug("请求体不是有效的表单格式")

        # 最后尝试从查询参数获取
        if not refresh_token:
            refresh_token = request.query_params.get("refresh_token")
            if refresh_token:
                logger.debug("成功从查询参数获取refresh_token")

        # 2. 验证是否获取到refresh_token
        if not refresh_token:
            logger.warning("令牌轮换请求缺少refresh_token参数")
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": "缺少refresh_token参数"
                }
            )

        # 3. 从令牌中提取用户ID
        user_id = auth_service.get_user_id_from_token(refresh_token, "refresh")
        if not user_id:
            logger.warning("无法从刷新令牌中提取用户ID")
            return JSONResponse(
                status_code=401,
                content={
                    "success": False,
                    "message": "无效的刷新令牌"
                }
            )

        # 4. 获取用户信息，用于创建新令牌
        user_data = await redis_client.get_user(user_id)
        if not user_data or "username" not in user_data:
            logger.warning(f"用户信息不存在或已过期: {user_id}")
            return JSONResponse(
                status_code=404,
                content={
                    "success": False,
                    "message": "用户信息不存在或已过期"
                }
            )

        username = user_data.get("username")

        # 5. 轮换刷新令牌
        new_refresh_token = auth_service.rotate_refresh_token(refresh_token)
        if not new_refresh_token:
            logger.warning("轮换刷新令牌失败")
            return JSONResponse(
                status_code=401,
                content={
                    "success": False,
                    "message": "无效的刷新令牌"
                }
            )

        # 6. 创建新的访问令牌
        access_token, _ = auth_service.create_tokens(user_id, username)

        # 7. 返回新的令牌对
        logger.info(f"用户 {user_id} 令牌轮换成功")
        return {
            "success": True,
            "message": "令牌已完全更新",
            "data": {
                "access_token": access_token,
                "refresh_token": new_refresh_token
            }
        }

    except Exception as e:
        logger.error(f"轮换令牌过程中发生错误: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"轮换令牌失败: {str(e)}"
            }
        )
