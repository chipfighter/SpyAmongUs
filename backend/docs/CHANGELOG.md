### v0.0.12

- 暂时不知道（简单检查优化一下就是MVP了）

### v0.0.11

- 秘密聊天室

### v0.0.10

- 游戏结算+用户评定

### v0.0.9

- 游戏进行（投票相关）

### v0.0.8 

- 游戏初始化相关
- 修复了加入/离开房间存在的用户同步问题
- 修复了部分小bug

### v0.0.7

- 自由聊天
- 加入/退出房间

### v0.0.6

- 调整AI功能并加入正常聊天

### v0.0.5

- 房主聊天
- 创建房间
- 删除房间
- 调整了前后端用户检测的功能

### v0.0.4

- 完全调整了数据存储和交互方式
- 重新调整部分功能
  - 注册
  - 登陆


### v0.0.3

- 房间聊天调整
  - 创建房间后可以正常查看用户列表
- 加入部分浏览器调试信息（之后stable版本删除）
- 调整用户注册信息记录（MongoDB中信息调整）

### v0.0.2

- 创建房间
- 正常聊天

### v0.0.1

- 登陆功能
- 注册功能
- 大厅界面





```mermaid
erDiagram
    USERS {
        string id PK "用户ID (usr_xxx)"
        string username "用户名"
        string password_hash "密码哈希"
        string salt "密码盐值"
        string avatar_url "头像URL"
        string status "用户状态"
        string current_room "当前房间"
        boolean is_admin "是否管理员"
        int register_time "注册时间"
        int points "用户积分"
        boolean is_muted "是否禁言"
        int mute_until "禁言截止时间"
        boolean is_banned "是否封禁"
        int ban_until "封禁截止时间"
        object statistics "游戏统计"
        object style_profile "用户画像"
    }

    USER_STATISTICS {
        int total_games "总游戏次数"
        int win_count "总胜利次数"
        float win_rate "总胜率"
        int civilian_games "平民游戏次数"
        int civilian_wins "平民胜利次数"
        float civilian_win_rate "平民胜率"
        int spy_games "卧底游戏次数"
        int spy_wins "卧底胜利次数"
        float spy_win_rate "卧底胜率"
        object win_rates "胜率字典"
    }

    USER_STYLE_PROFILE {
        string summary "风格说明"
        set tags "标签集合"
        object vectors "性格向量"
    }

    FEEDBACK {
        string id PK "反馈ID"
        string user_id FK "用户ID"
        string type "反馈类型"
        string content "反馈内容"
        string status "处理状态"
        int created_at "创建时间"
        int updated_at "更新时间"
        string admin_response "管理员回复"
        int priority "优先级"
    }

    USERS ||--|| USER_STATISTICS : "包含"
    USERS ||--|| USER_STYLE_PROFILE : "包含"
    USERS ||--o{ FEEDBACK : "提交"
```

