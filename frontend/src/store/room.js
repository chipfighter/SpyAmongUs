import { defineStore } from 'pinia'
import websocketService from '../services/websocket'
import { useRouter } from 'vue-router'

// 初始化WebSocket事件处理
function initWebSocketHandlers() {
  const LOG_PREFIX = "[RoomStore]";
  
  // 房间创建成功处理
  websocketService.registerHandler('room_created', (data) => {
    console.log(`${LOG_PREFIX} 收到房间创建成功事件:`, data);
    const room = data.room || data;
    const store = useRoomStore();
    
    // 更新当前房间
    store.$state.currentRoom = room;
    store.$state.error = null;
    
    // 优先使用服务器返回的用户列表
    if (data.users && Array.isArray(data.users)) {
      console.log(`${LOG_PREFIX} 使用服务器返回的用户列表:`, data.users);
      store.users[room.id] = data.users;
      return;
    }
    
    // 如果服务器没有返回用户列表，则手动构造
    // 获取当前用户信息
    let userId, username, avatar;
    try {
      const userStr = localStorage.getItem('user');
      if (userStr) {
        const user = JSON.parse(userStr);
        userId = user.id;
        username = user.username;
        avatar = user.avatar || '/default_avatar.jpg';
      } else {
        userId = localStorage.getItem('userId');
        username = localStorage.getItem('username');
        avatar = '/default_avatar.jpg';
      }
      
      // 将当前用户添加到房间用户列表
      if (userId && username && room.id) {
        const currentUser = { 
          id: userId, 
          username: username.trim(),  // 确保用户名没有前后空格
          status: '在线',
          is_host: userId === room.host_id,
          avatar: avatar
        };
        
        // 确保用户列表已初始化
        if (!store.users[room.id]) {
          store.users[room.id] = [];
        }
        
        // 检查用户是否已存在于列表中
        const userExists = store.users[room.id].some(u => u.id === userId);
        if (!userExists) {
          store.users[room.id].push(currentUser);
          console.log(`${LOG_PREFIX} 已将当前用户添加到房间用户列表:`, currentUser);
        }
      }
    } catch (e) {
      console.error(`${LOG_PREFIX} 处理房间创建事件时出错:`, e);
    }
  });
  
  // 加入房间成功处理
  websocketService.registerHandler('room_joined', (data) => {
    console.log(`${LOG_PREFIX} 收到房间加入成功事件:`, data);
    
    const store = useRoomStore();
    const room = data.data || data;
    
    // 更新当前房间
    store.$state.currentRoom = {
      id: room.id,
      name: room.name,
      host_id: room.host_id,
      is_public: room.is_public,
      invitation_code: room.invitation_code
    };
    
    // 处理房间用户列表
    if (room.users && Array.isArray(room.users)) {
      console.log(`${LOG_PREFIX} 收到房间用户列表:`, room.users);
      // 确保所有用户名没有前后空格
      const trimmedUsers = room.users.map(user => {
        if (user.username) {
          return { ...user, username: user.username.trim() };
        }
        return user;
      });
      store.users[room.id] = trimmedUsers;
    }
    
    store.$state.error = null;
  });
  
  // 错误处理
  websocketService.registerHandler('error', (data) => {
    console.error(`${LOG_PREFIX} 收到错误事件:`, data);
    const store = useRoomStore();
    
    // 提取错误信息
    let errorMessage = '';
    
    // 处理不同格式的错误消息
    if (data.error) {
      // 新格式错误
      errorMessage = data.error;
      if (data.details) {
        errorMessage += `: ${data.details}`;
      }
    } else if (data.data && data.data.message) {
      // 旧格式错误
      errorMessage = data.data.message;
    } else {
      // 未知格式
      errorMessage = '操作失败，请稍后重试';
    }
    
    // 记录详细日志
    console.error(`${LOG_PREFIX} 错误类型: ${data.action || '未知'}, 错误信息: ${errorMessage}`);
    
    // 设置错误状态
    store.error = errorMessage;
    store.loading = false;
    
    // 移除弹窗提示，只使用页面上的红色错误框显示
  });
  
  // 其他事件处理器...
  console.log(`${LOG_PREFIX} 已注册WebSocket事件处理器`);
}

// 立即初始化事件处理器
initWebSocketHandlers();

export const useRoomStore = defineStore('room', {
  state: () => ({
    currentRoom: null,
    publicRooms: [],
    messages: {},  // 按房间ID存储消息
    users: {},     // 按房间ID存储用户列表
    loading: false,
    error: null,
    debugMode: true,  // 调试模式开关
    LOG_PREFIX: "[RoomStore]"  // 日志前缀
  }),
  
  getters: {
    getCurrentRoom: (state) => state.currentRoom,
    getPublicRooms: (state) => state.publicRooms,
    getRoomMessages: (state) => (roomId) => state.messages[roomId] || [],
    getRoomUsers: (state) => (roomId) => state.users[roomId] || [],
    getOfflineRoom: (state) => (roomId) => {
      if (state.currentRoom && state.currentRoom.id === roomId && state.currentRoom.offline_mode) {
        return state.currentRoom;
      }
      return null;
    }
  },
  
  actions: {
    // 日志函数
    log(...args) {
      if (this.debugMode) {
        console.log(this.LOG_PREFIX, ...args);
      }
    },
    
    // 错误日志函数
    logError(...args) {
      console.error(this.LOG_PREFIX, ...args);
    },
    
    // 创建新房间
    async createRoom(roomName, isPublic = true, settings = {}) {
      try {
        this.log('准备创建房间:', roomName, isPublic, settings)
        this.loading = true
        this.error = null

        // 获取用户信息
        let userId, username, avatar
        
        // 首先从本地存储的用户对象中获取
        const userStr = localStorage.getItem('user')
        if (userStr) {
          try {
            const user = JSON.parse(userStr)
            userId = user.id
            username = user.username.trim() // 确保用户名没有前后空格
            avatar = user.avatar || '/default_avatar.jpg'
          } catch (e) {
            this.logError('解析用户信息失败:', e)
          }
        }
        
        // 如果上面方法获取失败，尝试分别获取
        if (!userId) userId = localStorage.getItem('userId')
        if (!username) username = localStorage.getItem('username')
        if (!avatar) avatar = '/default_avatar.jpg'
        
        if (!userId || !username) {
          this.error = '用户信息不完整，无法创建房间'
          this.logError(this.error)
          return
        }
        
        // 检查用户是否已在房间中
        if (this.currentRoom) {
          this.error = '您已在房间中，请先离开当前房间再创建新房间'
          this.logError(this.error)
          this.loading = false
          
          // 可选：自动跳转到当前房间
          const router = useRouter()
          if (this.currentRoom.id) {
            router.push(`/room/${this.currentRoom.id}`)
          }
          
          return
        }

        this.log('使用用户ID创建房间:', userId)

        // 检查WebSocket连接
        if (!websocketService.isConnected || 
            !websocketService.socket || 
            websocketService.socket.readyState !== WebSocket.OPEN) {
          
          this.log('WebSocket未连接，尝试连接...')
          
          try {
            await websocketService.connect(userId)
            this.log('WebSocket重新连接成功')
            
            // 给连接稳定一点时间
            await new Promise(resolve => setTimeout(resolve, 1000))
          } catch (err) {
            this.logError('WebSocket连接失败:', err)
            
            // 返回连接错误
            this.error = '无法连接到服务器，请检查网络连接和防火墙设置'
            this.loading = false
            return null
          }
        }

        // 确保使用的用户ID与WebSocket连接中使用的一致
        if (websocketService.lastUserId && userId !== websocketService.lastUserId) {
          this.log(`用户ID不匹配，WebSocket使用: ${websocketService.lastUserId}, 当前使用: ${userId}`)
          this.log('重新使用WebSocket中的用户ID')
          userId = websocketService.lastUserId
        }

        // 准备创建房间的消息
        const message = {
          type: 'create_room',
          room_name: roomName,
          user_id: userId,
          username: username.trim(), // 确保移除用户名前后空格
          avatar: avatar,
          is_public: isPublic,
          ...settings // 包含其他房间设置，如玩家数、卧底数等
        }
        
        this.log('发送创建房间请求:', message)
        
        // 发送创建房间请求
        await websocketService.sendMessage(message)
        
        // 等待room_created事件响应，设置超时
        const timeoutDuration = 5000; // 5秒超时
        const creationTimeout = setTimeout(() => {
          if (!this.currentRoom) {
            this.logError('创建房间响应超时');
            this.error = '服务器响应超时，请重试';
            this.loading = false;
          }
        }, timeoutDuration);
        
        // 等待一小段时间，确保WebSocket事件有时间处理
        await new Promise(resolve => setTimeout(resolve, 1000));
        
        clearTimeout(creationTimeout);
        
        // 始终添加当前用户到房间，无论是否收到服务器响应
        if (this.currentRoom) {
          this.log('房间创建成功，确保用户列表包含当前用户');
          
          const roomId = this.currentRoom.id;
          
          // 创建当前用户对象
          const currentUser = {
            id: userId,
            username: username.trim(), // 确保移除用户名前后空格
            avatar: avatar,
            status: '在线',
            is_host: true
          };
          
          if (!this.users[roomId]) {
            this.users[roomId] = [];
          }
          
          // 检查用户是否已在列表中
          const userExists = this.users[roomId].some(u => u.id === currentUser.id);
          
          // 如果用户不在列表中，添加用户
          if (!userExists) {
            // 将用户添加到房间
            this.users[roomId].push(currentUser);
            this.log('已直接添加当前用户到房间:', currentUser);
          } else {
            this.log('用户已存在于房间列表中:', currentUser);
            
            // 强制触发响应式更新
            this.users[roomId] = [...this.users[roomId]];
          }
        }
        
        this.log('房间创建流程完成，当前房间:', this.currentRoom);
        this.log('房间用户列表:', this.users[this.currentRoom?.id || '']);
        
        return this.currentRoom
      } catch (error) {
        this.error = `创建房间失败: ${error.message}`
        this.logError(this.error, error)
      } finally {
        this.loading = false
      }
    },
    
    // 加入房间
    async joinRoom(roomId, invitationCode = null) {
      try {
        this.loading = true
        this.error = null
        
        // 检查用户是否已在房间中
        if (this.currentRoom) {
          this.error = '您已在房间中，请先离开当前房间再加入新房间'
          this.logError(this.error)
          this.loading = false
          
          // 可选：自动跳转到当前房间
          const router = useRouter()
          if (this.currentRoom.id) {
            router.push(`/room/${this.currentRoom.id}`)
          }
          
          return
        }
        
        // 获取用户信息
        let userId, username, avatar
        
        // 首先从本地存储的用户对象中获取
        const userStr = localStorage.getItem('user')
        if (userStr) {
          try {
            const user = JSON.parse(userStr)
            userId = user.id
            username = user.username.trim() // 确保用户名没有前后空格
            avatar = user.avatar || '/default_avatar.jpg'
          } catch (e) {
            this.logError('解析用户信息失败:', e)
          }
        }
        
        // 如果上面方法获取失败，尝试分别获取
        if (!userId) userId = localStorage.getItem('userId')
        if (!username) username = localStorage.getItem('username')
        if (!avatar) avatar = '/default_avatar.jpg'
        
        if (!userId || !username) {
          this.error = '用户信息不完整，无法加入房间'
          this.logError(this.error)
          this.loading = false
          return
        }
        
        // 检查WebSocket连接
        if (!websocketService.isConnected || 
            !websocketService.socket || 
            websocketService.socket.readyState !== WebSocket.OPEN) {
          
          this.log('WebSocket未连接，尝试连接...')
          
          try {
            await websocketService.connect(userId)
            this.log('WebSocket连接成功，现在加入房间')
          } catch (error) {
            this.logError('WebSocket连接失败:', error)
            this.error = `无法连接到服务器: ${error.message || '未知错误'}`
            this.loading = false
            return
          }
        }
        
        // 根据传入的参数判断是通过房间ID还是邀请码加入
        let data = {
          type: "join_room",
          data: {
            user_id: userId,
            username,
            avatar
          }
        }
        
        // 添加房间ID或邀请码到请求中
        if (roomId) {
          data.data.room_id = roomId
        } else if (invitationCode) {
          data.data.invitation_code = invitationCode
        } else {
          this.error = '需要提供房间ID或邀请码'
          this.loading = false
          return
        }
        
        this.log('发送加入房间请求:', data)
        websocketService.send(data)
        
        // 等待响应
        setTimeout(() => {
          if (this.loading) {
            this.loading = false
            this.error = '加入房间超时，请重试'
          }
        }, 10000)
        
      } catch (error) {
        this.error = `加入房间失败: ${error.message}`
        this.logError(this.error, error)
      } finally {
        this.loading = false
      }
    },
    
    // 离开房间
    async leaveRoom(roomId) {
      this.loading = true
      this.error = null
      
      try {
        const userId = localStorage.getItem('userId') || JSON.parse(localStorage.getItem('user')).id
        let username = localStorage.getItem('username') || JSON.parse(localStorage.getItem('user')).username
        
        // 确保用户名没有前后空格
        if (username) {
          username = username.trim()
        }
        
        if (!websocketService.isConnected) {
          this.logError('WebSocket未连接，无法离开房间')
          this.error = '网络连接断开，请刷新页面重试'
          this.loading = false
          return
        }
        
        if (!userId || !username) {
          this.logError('用户信息不完整，无法离开房间')
          this.error = '用户信息不完整，请重新登录'
          this.loading = false
          return
        }
        
        const message = {
          type: 'leave_room',
          data: {
            room_id: roomId,
            username: username, // 已确保移除前后空格
            user_id: userId
          }
        }
        
        this.log('发送离开房间请求:', message)
        await websocketService.sendMessage(message)
        
        // 注意：离开房间的结果会通过WebSocket回调处理
      } catch (error) {
        this.error = `离开房间失败: ${error.message}`
        this.logError(this.error, error)
      } finally {
        this.loading = false
      }
    },
    
    // 发送消息
    async sendMessage(roomId, content) {
      try {
        const userId = localStorage.getItem('userId') || JSON.parse(localStorage.getItem('user')).id
        let username = localStorage.getItem('username') || JSON.parse(localStorage.getItem('user')).username
        
        // 确保用户名没有前后空格
        if (username) {
          username = username.trim()
        }
        
        if (!userId || !username) {
          this.logError('用户信息不完整，无法发送消息')
          return false
        }
        
        // 检查是否离线房间
        if (this.currentRoom && this.currentRoom.offline_mode) {
          this.log('在离线房间发送消息:', content)
          
          // 直接添加消息到本地显示
          this.addMessage(roomId, {
            id: `offline_${Date.now()}`,
            room_id: roomId,
            user_id: userId,
            username: username,
            content: content,
            timestamp: Date.now(),
            is_self: true
          })
          
          return true
        }
        
        // 检查WebSocket连接
        if (!websocketService.isConnected || 
            !websocketService.socket || 
            websocketService.socket.readyState !== WebSocket.OPEN) {
          
          this.log('WebSocket未连接，尝试连接...')
          
          try {
            await websocketService.connect(userId)
            this.log('WebSocket重新连接成功')
            
            // 给连接稳定一点时间
            await new Promise(resolve => setTimeout(resolve, 1000))
          } catch (err) {
            this.logError('WebSocket连接失败:', err)
            return false
          }
        }
        
        // 准备消息对象
        const message = {
          type: 'message',
          data: {
            room_id: roomId,
            content: content,
            user_id: userId,
            username: username // 已确保移除前后空格
          }
        }
        
        // 发送消息
        this.log('发送聊天消息:', message)
        await websocketService.sendMessage(message)
        
        // 将自己发送的消息添加到本地显示（不等待服务器回传）
        this.addMessage(roomId, {
          id: `local_${Date.now()}`,
          room_id: roomId,
          user_id: userId,
          username: username,
          content: content,
          timestamp: Date.now(),
          is_self: true // 标记为自己发送的消息
        })
        
        return true
      } catch (err) {
        this.logError('发送消息失败:', err)
        return false
      }
    },
    
    // 获取公开房间列表
    async fetchPublicRooms() {
      this.loading = true
      this.error = null
      
      try {
        // 检查WebSocket连接
        let userId = JSON.parse(localStorage.getItem('user'))?.id || localStorage.getItem('userId')
        
        if (!websocketService.isConnected && userId) {
          this.log('WebSocket未连接，尝试连接...')
          
          try {
            await websocketService.connect(userId)
            this.log('WebSocket重新连接成功，获取房间列表')
            
            await websocketService.sendMessage({
              type: 'get_public_rooms',
              data: {}
            })
            
            // 注意：房间列表会通过WebSocket回调获取
          } catch (err) {
            this.logError('WebSocket连接失败，无法获取房间列表:', err)
            this.error = '网络连接失败，无法获取最新房间列表。请检查网络连接或防火墙设置。'
          }
        } else if (websocketService.isConnected) {
          this.log('发送获取公开房间列表请求')
          await websocketService.sendMessage({
            type: 'get_public_rooms',
            data: {}
          })
        } else {
          this.logError('WebSocket未连接，且无用户ID，无法获取房间列表')
          this.error = '网络连接失败，无法获取房间列表。请登录后重试。'
        }
      } catch (error) {
        this.error = `获取房间列表失败: ${error.message}`
        this.logError(this.error)
      } finally {
        this.loading = false
      }
    },
    
    // 设置当前房间（用于UI更新）
    setCurrentRoom(room) {
      this.currentRoom = room
      this.log('设置当前房间:', room)
    },
    
    // 更新公开房间列表（由WebSocket回调调用）
    updatePublicRooms(data) {
      // 检查是否存在rooms字段
      if (data && data.rooms) {
        this.publicRooms = data.rooms;
        this.log(`更新公开房间列表，共 ${data.rooms.length} 个房间`)
      } else if (Array.isArray(data)) {
        // 直接是数组形式
        this.publicRooms = data;
        this.log(`更新公开房间列表，共 ${data.length} 个房间`)
      } else {
        this.logError('无效的房间列表数据格式:', data);
        this.publicRooms = [];
      }
    },
    
    // 添加消息到特定房间（由WebSocket回调调用）
    addMessage(roomId, message) {
      if (!this.messages[roomId]) {
        this.messages[roomId] = []
      }
      
      // 确保消息中的用户名没有前后空格
      if (message.username) {
        message.username = message.username.trim()
      }
      
      this.messages[roomId].push(message)
      this.log(`添加消息到房间 ${roomId}:`, message)
    },
    
    // 设置房间消息历史（由WebSocket回调调用）
    setMessageHistory(roomId, messages) {
      // 确保所有消息中的用户名没有前后空格
      const trimmedMessages = messages.map(msg => {
        if (msg.username) {
          return { ...msg, username: msg.username.trim() };
        }
        return msg;
      });
      
      this.messages[roomId] = trimmedMessages
      this.log(`设置房间 ${roomId} 消息历史，共 ${trimmedMessages.length} 条消息`)
    },
    
    // 添加用户到房间
    addUserToRoom(roomId, user) {
      this.log('添加用户到房间:', roomId, user);
      
      if (!this.users[roomId]) {
        this.users[roomId] = []
      }
      
      // 确保用户名没有前后空格
      if (user.username) {
        user.username = user.username.trim();
      }
      
      // 检查用户是否已经存在
      const userExists = this.users[roomId].some(u => u.id === user.id)
      if (!userExists) {
        this.users[roomId].push(user)
        this.log(`成功添加用户 ${user.username} 到房间 ${roomId}, 当前用户数: ${this.users[roomId].length}`);
      } else {
        this.log(`用户 ${user.username} 已存在于房间 ${roomId} 中`);
        // 强制触发响应式更新
        this.users[roomId] = [...this.users[roomId]];
      }
    },
    
    // 设置房间用户列表
    setRoomUsers(roomId, users) {
      this.log('设置房间用户列表:', roomId, users);
      
      // 确保所有用户名没有前后空格
      const trimmedUsers = users.map(user => {
        if (user.username) {
          return { ...user, username: user.username.trim() };
        }
        return user;
      });
      
      this.users[roomId] = trimmedUsers;
      this.log(`房间 ${roomId} 用户列表已设置, 当前用户数: ${this.users[roomId].length}`);
    },
    
    // 清除特定房间的数据（离开房间时调用）
    clearRoomData(roomId) {
      if (this.currentRoom && this.currentRoom.id === roomId) {
        this.currentRoom = null
        this.log(`清除当前房间: ${roomId}`)
      }
      delete this.messages[roomId]
      delete this.users[roomId]
      this.log(`清除房间 ${roomId} 的消息和用户数据`)
    },
    
    // 注册WebSocket事件处理
    setupWebSocketHandlers() {
      // 由于我们已经在文件开始处初始化了处理器
      // 这个方法现在主要用于确保在某些特定情况下处理器已被注册
      this.log('检查WebSocket事件处理器')
    },
    
    // 解散房间（仅房主可调用）
    async disbandRoom(roomId) {
      this.loading = true
      this.error = null
      
      try {
        const userId = localStorage.getItem('userId') || JSON.parse(localStorage.getItem('user')).id
        let username = localStorage.getItem('username') || JSON.parse(localStorage.getItem('user')).username
        
        // 确保用户名没有前后空格
        if (username) {
          username = username.trim()
        }
        
        if (!websocketService.isConnected) {
          this.logError('WebSocket未连接，无法解散房间')
          this.error = '网络连接断开，请刷新页面重试'
          this.loading = false
          return
        }
        
        if (!userId || !username) {
          this.logError('用户信息不完整，无法解散房间')
          this.error = '用户信息不完整，请重新登录'
          this.loading = false
          return
        }
        
        const message = {
          type: 'disband_room',  // 注意：后端需要支持这个消息类型
          data: {
            room_id: roomId,
            username: username, // 已确保移除前后空格
            user_id: userId
          }
        }
        
        this.log('发送解散房间请求:', message)
        
        // 如果后端尚未实现解散房间功能，可以先使用leaveRoom代替
        // 后续可以等后端实现了再修改
        await websocketService.sendMessage({
          type: 'leave_room',
          data: {
            room_id: roomId,
            username: username, // 已确保移除前后空格
            user_id: userId
          }
        })
        
        // 清除本地房间数据
        this.clearRoomData(roomId)
        
      } catch (error) {
        this.error = `解散房间失败: ${error.message}`
        this.logError(this.error, error)
      } finally {
        this.loading = false
      }
    },
  }
}) 