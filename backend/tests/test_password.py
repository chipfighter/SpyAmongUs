import sys
import os
import hashlib

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入User模型
from models.user import User

def test_existing_hash():
    """测试已有的盐值和密码哈希"""
    # 已有的用户数据
    salt = "XJ9KPvLZC3gMrN7T"
    stored_hash = "57816af9a301e83ccb36ddc91f38e48ae8a529c27b11df9f30a9f62604888092"
    password = "123456"
    
    # 使用User模型的验证方法
    test_user = User(
        id="test_user",
        username="test",
        password_hash=stored_hash,
        salt=salt
    )
    
    # 直接使用密码哈希算法
    computed_hash = hashlib.sha256((password + salt).encode()).hexdigest()
    
    print("===== 密码验证测试 =====")
    print(f"用户名: test")
    print(f"密码: {password}")
    print(f"盐值: {salt}")
    print(f"存储的哈希: {stored_hash}")
    print(f"计算的哈希: {computed_hash}")
    print(f"哈希匹配: {computed_hash == stored_hash}")
    print(f"User.verify_password结果: {test_user.verify_password(password)}")
    
    if computed_hash != stored_hash:
        print("\n哈希不匹配，可能的原因:")
        print("1. 密码不正确")
        print("2. 盐值不正确")
        print("3. 哈希算法不同")
        print("\n尝试其他哈希算法:")
        
        # 尝试不同的算法组合
        algorithms = [
            ("sha256(salt+password)", lambda p, s: hashlib.sha256((s + p).encode()).hexdigest()),
            ("md5(password+salt)", lambda p, s: hashlib.md5((p + s).encode()).hexdigest()),
            ("md5(salt+password)", lambda p, s: hashlib.md5((s + p).encode()).hexdigest())
        ]
        
        for name, algo_func in algorithms:
            test_hash = algo_func(password, salt)
            print(f"{name}: {test_hash}")
            print(f"匹配: {test_hash == stored_hash}")

if __name__ == "__main__":
    test_existing_hash() 