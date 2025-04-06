import { defineStore } from 'pinia'
import websocketService from '../services/websocket'

// 初始化WebSocket事件处理
function initWebSocketHandlers() {
  // 房间创建成功处理
  websocketService.registerHandler('room_created', (data) => {
    console.log('收到房间创建成功事件:', data);
    const room = data.room || data;
    const store = useRoomStore();
    
    // 更新当前房间
    store.$state.currentRoom = room;
    store.$state.error = null;
    
    // 优先使用服务器返回的用户列表
    if (data.users && Array.isArray(data.users)) {
      console.log('使用服务器返回的用户列表:', data.users);
      store.users[room.id] = data.users;
      return;
    }
    
    // 如果服务器没有返回用户列表，则手动构造
    // 获取当前用户信息
    let userId, username;
    try {
      const userStr = localStorage.getItem('user');
      if (userStr) {
        const user = JSON.parse(userStr);
        userId = user.id;
        username = user.username;
      } else {
        userId = localStorage.getItem('userId');
        username = localStorage.getItem('username');
      }
      
      // 将当前用户添加到房间用户列表
      if (userId && username && room.id) {
        const currentUser = { 
          id: userId, 
          username: username,
          status: '在线',
          is_host: userId === room.host_id
        };
        
        // 确保用户列表已初始化
        if (!store.users[room.id]) {
          store.users[room.id] = [];
        }
        
        // 检查用户是否已存在于列表中
        const userExists = store.users[room.id].some(u => u.id === userId);
        if (!userExists) {
          store.users[room.id].push(currentUser);
          console.log('已将当前用户添加到房间用户列表:', currentUser);
        }
      }
    } catch (e) {
      console.error('处理房间创建事件时出错:', e);
    }
  });
  
  // 加入房间成功处理
  websocketService.registerHandler('room_joined', (data) => {
    console.log('收到房间加入成功事件:', data);
    
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
      console.log('收到房间用户列表:', room.users);
      store.users[room.id] = room.users;
    }
    
    store.$state.error = null;
  });
  
  // 错误处理
  websocketService.registerHandler('error', (data) => {
    console.error('收到错误事件:', data);
    if (data.action === 'create_room') {
      useRoomStore().$state.error = `操作失败: ${data.error}${data.details ? ` (${data.details})` : ''}`;
    }
  });
  
  // 其他事件处理器...
  console.log('已注册WebSocket事件处理器');
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
    error: null
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
    // 创建新房间
    async createRoom(roomName, isPublic = true, settings = {}) {
      try {
        console.log('准备创建房间:', roomName, isPublic, settings)
        this.loading = true
        this.error = null

        // 获取用户信息
        let userId, username
        
        // 首先从本地存储的用户对象中获取
        const userStr = localStorage.getItem('user')
        if (userStr) {
          try {
            const user = JSON.parse(userStr)
            userId = user.id
            username = user.username
          } catch (e) {
            console.error('解析用户信息失败:', e)
          }
        }
        
        // 如果上面方法获取失败，尝试分别获取
        if (!userId) userId = localStorage.getItem('userId')
        if (!username) username = localStorage.getItem('username')
        
        if (!userId || !username) {
          this.error = '用户信息不完整，无法创建房间'
          console.error(this.error)
          return
        }

        console.log('使用用户ID创建房间:', userId)

        // 检查WebSocket连接
        if (!websocketService.isConnected || 
            !websocketService.socket || 
            websocketService.socket.readyState !== WebSocket.OPEN) {
          
          console.warn('WebSocket未连接，尝试连接...')
          
          try {
            await websocketService.connect(userId)
            console.log('WebSocket重新连接成功')
            
            // 给连接稳定一点时间
            await new Promise(resolve => setTimeout(resolve, 1000))
          } catch (err) {
            console.error('WebSocket连接失败:', err)
            
            // 提示用户可能是防火墙问题
            console.log('提示：WebSocket连接失败可能是由于防火墙阻止。请检查防火墙设置或尝试关闭防火墙。')
            console.log('正在创建本地房间（离线模式）...')
            
            // 创建一个离线模式的房间
            const offlineRoom = {
              id: 'local-' + Date.now(),
              name: roomName,
              host_id: userId,
              is_public: isPublic,
              invitation_code: Math.random().toString(36).substring(2, 8).toUpperCase(),
              offline_mode: true,
              users: [{ id: userId, username: username }],
              created_at: new Date().toISOString(),
              ...settings
            }
            
            this.currentRoom = offlineRoom
            
            // 将用户添加到房间
            if (!this.users[offlineRoom.id]) {
              this.users[offlineRoom.id] = []
            }
            this.users[offlineRoom.id].push({ id: userId, username })
            
            // 添加系统消息
            if (!this.messages[offlineRoom.id]) {
              this.messages[offlineRoom.id] = []
            }
            this.messages[offlineRoom.id].push({
              type: 'system',
              content: '创建了离线模式房间。部分功能可能不可用。',
              timestamp: Date.now()
            })
            
            console.log('离线模式房间创建成功:', offlineRoom)
            this.loading = false
            return offlineRoom
          }
        }

        // 确保使用的用户ID与WebSocket连接中使用的一致
        if (websocketService.lastUserId && userId !== websocketService.lastUserId) {
          console.warn(`用户ID不匹配，WebSocket使用: ${websocketService.lastUserId}, 当前使用: ${userId}`)
          console.log('重新使用WebSocket中的用户ID')
          userId = websocketService.lastUserId
        }

        // 准备创建房间的消息
        const message = {
          type: 'create_room',
          room_name: roomName,
          user_id: userId,
          username: username,
          is_public: isPublic,
          ...settings // 包含其他房间设置，如玩家数、卧底数等
        }

        // 发送创建房间请求
        console.log('发送创建房间请求:', message)
        await websocketService.sendMessage(message)
        console.log('创建房间请求已发送')
        
        // 由于响应是异步的，这里不返回任何值
        // 房间创建成功后会通过WebSocket事件处理器更新状态
      } catch (err) {
        this.error = `创建房间失败: ${err.message || '未知错误'}`
        console.error('创建房间过程中出现错误:', err)
      } finally {
        this.loading = false
      }
    },
    
    // 加入房间
    async joinRoom(roomId, userInfo = {}) {
      this.loading = true
      this.error = null
      
      try {
        // 获取用户信息
        const userId = userInfo.user_id || localStorage.getItem('userId') || JSON.parse(localStorage.getItem('user'))?.id
        const username = userInfo.username || localStorage.getItem('username') || JSON.parse(localStorage.getItem('user'))?.username
        const avatar = userInfo.avatar || JSON.parse(localStorage.getItem('user'))?.avatar || ''
        
        if (!userId || !username) {
          this.error = '用户信息不完整，无法加入房间'
          console.error(this.error)
          this.loading = false
          return
        }
        
        // 检查WebSocket连接
        if (!websocketService.isConnected) {
          console.warn('WebSocket未连接，尝试连接...')
          
          try {
            await websocketService.connect(userId)
            console.log('WebSocket重新连接成功')
            
            // 给连接稳定一点时间
            await new Promise(resolve => setTimeout(resolve, 1000))
          } catch (err) {
            console.error('WebSocket连接失败，无法加入房间:', err)
            this.error = '网络连接失败，请检查防火墙设置或网络连接'
            this.loading = false
            return
          }
        }
        
        // 准备加入房间的消息
        const message = {
          type: 'join_room',
          data: {
            room_id: roomId,
            user_id: userId,
            username: username,
            avatar: avatar
          }
        }
        
        console.log('发送加入房间请求:', message)
        
        // 发送加入房间请求
        await websocketService.sendMessage(message)
        
      } catch (error) {
        this.error = `加入房间失败: ${error.message}`
        console.error(this.error, error)
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
        const username = localStorage.getItem('username') || JSON.parse(localStorage.getItem('user')).username
        
        if (!websocketService.isConnected) {
          console.error('WebSocket未连接，无法离开房间')
          this.error = '网络连接断开，请刷新页面重试'
          this.loading = false
          return
        }
        
        if (!userId || !username) {
          console.error('用户信息不完整，无法离开房间')
          this.error = '用户信息不完整，请重新登录'
          this.loading = false
          return
        }
        
        const message = {
          type: 'leave_room',
          data: {
            room_id: roomId,
            username: username,
            user_id: userId
          }
        }
        
        console.log('发送离开房间请求:', message)
        await websocketService.sendMessage(message)
        
        // 注意：离开房间的结果会通过WebSocket回调处理
      } catch (error) {
        this.error = `离开房间失败: ${error.message}`
        console.error(this.error, error)
      } finally {
        this.loading = false
      }
    },
    
    // 发送消息
    async sendMessage(roomId, content) {
      try {
        const userId = localStorage.getItem('userId') || JSON.parse(localStorage.getItem('user')).id
        const username = localStorage.getItem('username') || JSON.parse(localStorage.getItem('user')).username
        
        if (!userId || !username) {
          console.error('用户信息不完整，无法发送消息')
          return false
        }
        
        // 检查WebSocket连接
        if (!websocketService.isConnected || 
            !websocketService.socket || 
            websocketService.socket.readyState !== WebSocket.OPEN) {
          
          console.warn('WebSocket未连接，尝试连接...')
          
          try {
            await websocketService.connect(userId)
            console.log('WebSocket重新连接成功')
            
            // 给连接稳定一点时间
            await new Promise(resolve => setTimeout(resolve, 1000))
          } catch (err) {
            console.error('WebSocket连接失败:', err)
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
            username: username
          }
        }
        
        // 发送消息
        console.log('发送聊天消息:', message)
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
        console.error('发送消息失败:', err)
        return false
      }
    },
    
    // 获取公开房间列表
    async fetchPublicRooms() {
      this.loading = true
      this.error = null
      
      try {
        await websocketService.sendMessage({
          type: 'get_public_rooms',
          data: {}
        })
        
        // 注意：房间列表会通过WebSocket回调获取
      } catch (error) {
        this.error = `获取房间列表失败: ${error.message}`
        console.error(this.error)
      } finally {
        this.loading = false
      }
    },
    
    // 设置当前房间（用于UI更新）
    setCurrentRoom(room) {
      this.currentRoom = room
    },
    
    // 更新公开房间列表（由WebSocket回调调用）
    updatePublicRooms(data) {
      // 检查是否存在rooms字段
      if (data && data.rooms) {
        this.publicRooms = data.rooms;
      } else if (Array.isArray(data)) {
        // 直接是数组形式
        this.publicRooms = data;
      } else {
        console.error('无效的房间列表数据格式:', data);
        this.publicRooms = [];
      }
    },
    
    // 添加消息到特定房间（由WebSocket回调调用）
    addMessage(roomId, message) {
      if (!this.messages[roomId]) {
        this.messages[roomId] = []
      }
      this.messages[roomId].push(message)
    },
    
    // 设置房间消息历史（由WebSocket回调调用）
    setMessageHistory(roomId, messages) {
      this.messages[roomId] = messages
    },
    
    // 添加用户到房间
    addUserToRoom(roomId, user) {
      if (!this.users[roomId]) {
        this.users[roomId] = []
      }
      
      // 检查用户是否已经存在
      const userExists = this.users[roomId].some(u => u.id === user.id)
      if (!userExists) {
        this.users[roomId].push(user)
      }
    },
    
    // 设置房间用户列表
    setRoomUsers(roomId, users) {
      this.users[roomId] = users
    },
    
    // 清除特定房间的数据（离开房间时调用）
    clearRoomData(roomId) {
      if (this.currentRoom && this.currentRoom.id === roomId) {
        this.currentRoom = null
      }
      delete this.messages[roomId]
      delete this.users[roomId]
    },
    
    // 注册WebSocket事件处理
    setupWebSocketHandlers() {
      // 由于我们已经在文件开始处初始化了处理器
      // 这个方法现在主要用于确保在某些特定情况下处理器已被注册
      console.log('检查WebSocket事件处理器')
    },
    
    // 解散房间（仅房主可调用）
    async disbandRoom(roomId) {
      this.loading = true
      this.error = null
      
      try {
        const userId = localStorage.getItem('userId') || JSON.parse(localStorage.getItem('user')).id
        const username = localStorage.getItem('username') || JSON.parse(localStorage.getItem('user')).username
        
        if (!websocketService.isConnected) {
          console.error('WebSocket未连接，无法解散房间')
          this.error = '网络连接断开，请刷新页面重试'
          this.loading = false
          return
        }
        
        if (!userId || !username) {
          console.error('用户信息不完整，无法解散房间')
          this.error = '用户信息不完整，请重新登录'
          this.loading = false
          return
        }
        
        const message = {
          type: 'disband_room',  // 注意：后端需要支持这个消息类型
          data: {
            room_id: roomId,
            username: username,
            user_id: userId
          }
        }
        
        console.log('发送解散房间请求:', message)
        
        // 如果后端尚未实现解散房间功能，可以先使用leaveRoom代替
        // 后续可以等后端实现了再修改
        await websocketService.sendMessage({
          type: 'leave_room',
          data: {
            room_id: roomId,
            username: username,
            user_id: userId
          }
        })
        
        // 清除本地房间数据
        this.clearRoomData(roomId)
        
      } catch (error) {
        this.error = `解散房间失败: ${error.message}`
        console.error(this.error, error)
      } finally {
        this.loading = false
      }
    },
  }
}) 