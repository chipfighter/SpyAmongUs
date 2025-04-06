/**
 * WebSocket通信服务
 */

// API和WebSocket基础URL
const API_BASE_URL = 'http://localhost:8000';
const WS_URL = 'ws://localhost:8000/ws';

// 定义websocket服务类
class WebSocketService {
  constructor() {
    this.socket = null; // 保存WebSocket实例
    this.isConnected = false; // 连接状态
    this.reconnectAttempts = 0; // 重连次数
    this.maxReconnectAttempts = 5; // 最大重连次数
    this.reconnectDelay = 2000; // 2秒重连延迟
    this.messageHandlers = {}; // 消息处理器
    this.connecting = false; // 防止重复连接请求
    this.connectionPromise = null;  // 管理连接过程中的 Promise，确保不重复发起连接请求。
    this.lastUserId = null; // 记录最后连接的用户ID
  }

  /**
   * 连接到WebSocket服务器
   * @param {string} userId 用户ID
   * @returns {Promise} 连接成功的Promise
   */
  connect(userId) {
    // 保存用户ID
    this.lastUserId = userId;
    
    // 如果已经连接或正在连接中，返回已经连接得到的Promise（避免重复连接）
    if (this.isConnected && this.socket && this.socket.readyState === WebSocket.OPEN) {
      return Promise.resolve();
    }

    if (this.connecting && this.connectionPromise) {
      return this.connectionPromise;
    }
    
    this.connecting = true;
    
    return this.connectionPromise = new Promise((resolve, reject) => {
      try {
        // 构建WebSocket URL
        const wsUrl = `${WS_URL}?user_id=${encodeURIComponent(userId)}`;
        
        // 创建WebSocket连接
        this.socket = new WebSocket(wsUrl);
        
        // 设置连接超时（调整参数以后返回报错）
        const timeout = setTimeout(() => {
          if (!this.isConnected) {
            this.socket.close();
            this.connecting = false;
            reject(new Error('连接超时 (5秒)'));
          }
        }, 5000);
        
        this.socket.onopen = () => {
          this.isConnected = true;
          this.reconnectAttempts = 0;
          this.connecting = false;
          clearTimeout(timeout);
          resolve();
        };
        
        this.socket.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            const msgType = data.type || 'unknown';
            
            // 处理特定类型的消息
            if (data.type in this.messageHandlers) {
              this.messageHandlers[data.type].forEach(handler => {
                try {
                  handler(data.data || data);
                } catch (handlerError) {
                  console.error(`消息处理器错误:`, handlerError);
                }
              });
            }
          } catch (error) {
            console.error('解析WebSocket消息时出错:', error);
          }
        };
        
        this.socket.onclose = (event) => {
          this.isConnected = false;
          this.connecting = false;
          
          // 自动重连逻辑
          if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.attemptReconnect(userId);
          }
        };
        
        this.socket.onerror = (error) => {
          this.connecting = false;
          reject(error);
        };
      } catch (error) {
        this.connecting = false;
        reject(error);
      }
    }).catch(error => {
      // 连接失败时依然返回Promise，但不设置连接状态
      return Promise.resolve();
    });
  }

  /**
   * 发送消息到服务器
   * @param {Object} message 消息对象
   * @returns {Promise} 发送消息的Promise
   */
  sendMessage(message) {
    return new Promise((resolve, reject) => {
      if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
        reject(new Error('WebSocket未连接'));
        return;
      }
      
      try {
        const messageStr = JSON.stringify(message);
        this.socket.send(messageStr);
        resolve();
      } catch (error) {
        reject(error);
      }
    });
  }

  /**
   * 发送特定类型的消息（便捷方法）
   * @param {string} type 消息类型
   * @param {Object} data 消息数据
   * @returns {Promise} 发送消息的Promise
   */
  send(type, data = {}) {
    const message = { 
      type, 
      ...data 
    };
    return this.sendMessage(message);
  }

  /**
   * 尝试重新连接
   * @param {string} userId 用户ID
   */
  attemptReconnect(userId) {
    this.reconnectAttempts++;
    
    setTimeout(() => {
      this.connect(userId).catch(() => {
        // 重连失败，静默处理
      });
    }, this.reconnectDelay * this.reconnectAttempts);
  }

  /**
   * 注册消息处理器
   * @param {string} messageType 消息类型
   * @param {Function} handler 消息处理器
   */
  registerHandler(messageType, handler) {
    if (!this.messageHandlers[messageType]) {
      this.messageHandlers[messageType] = [];
    }
    this.messageHandlers[messageType].push(handler);
  }

  /**
   * 注销消息处理器
   * @param {string} messageType 消息类型
   * @param {Function} handler 消息处理器
   */
  unregisterHandler(messageType, handler) {
    if (this.messageHandlers[messageType]) {
      this.messageHandlers[messageType] = this.messageHandlers[messageType].filter(h => h !== handler);
    }
  }

  /**
   * 关闭WebSocket连接
   */
  disconnect() {
    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }
    this.isConnected = false;
  }
}

// 创建单例实例
const websocketService = new WebSocketService();
export default websocketService;
