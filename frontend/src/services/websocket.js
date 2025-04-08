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

    // 调试日志前缀
    this.LOG_PREFIX = "[WebSocket]";
  }

  /**
   * 连接到WebSocket服务器
   * @param {string} userId 用户ID
   * @returns {Promise} 连接成功的Promise
   */
  connect(userId) {
    // 保存用户ID
    this.lastUserId = userId;
    
    console.log(`${this.LOG_PREFIX} 尝试连接，用户ID: ${userId}`);
    
    // 如果已经连接或正在连接中，返回已经连接得到的Promise（避免重复连接）
    if (this.isConnected && this.socket && this.socket.readyState === WebSocket.OPEN) {
      console.log(`${this.LOG_PREFIX} 已经连接，无需重新连接`);
      return Promise.resolve();
    }

    if (this.connecting && this.connectionPromise) {
      console.log(`${this.LOG_PREFIX} 连接已在进行中，等待完成`);
      return this.connectionPromise;
    }
    
    this.connecting = true;
    console.log(`${this.LOG_PREFIX} 开始建立新连接`);
    
    return this.connectionPromise = new Promise((resolve, reject) => {
      try {
        // 构建WebSocket URL
        const wsUrl = `${WS_URL}?user_id=${encodeURIComponent(userId)}`;
        console.log(`${this.LOG_PREFIX} 连接URL: ${wsUrl}`);
        
        // 创建WebSocket连接
        this.socket = new WebSocket(wsUrl);
        
        // 设置连接超时（调整参数以后返回报错）
        const timeout = setTimeout(() => {
          if (!this.isConnected) {
            console.error(`${this.LOG_PREFIX} 连接超时 (5秒)`);
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
          console.log(`${this.LOG_PREFIX} 连接成功建立`);
          resolve();
        };
        
        this.socket.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            const msgType = data.type || 'unknown';
            
            console.log(`${this.LOG_PREFIX} 收到消息:`, { type: msgType, data: data });
            
            // 处理特定类型的消息
            if (data.type in this.messageHandlers) {
              console.log(`${this.LOG_PREFIX} 找到消息处理器，执行类型:`, msgType);
              this.messageHandlers[data.type].forEach(handler => {
                try {
                  handler(data.data || data);
                } catch (handlerError) {
                  console.error(`${this.LOG_PREFIX} 消息处理器错误:`, handlerError);
                }
              });
            } else {
              console.log(`${this.LOG_PREFIX} 没有处理器处理消息类型:`, msgType);
            }
          } catch (error) {
            console.error(`${this.LOG_PREFIX} 解析WebSocket消息时出错:`, error);
          }
        };
        
        this.socket.onclose = (event) => {
          this.isConnected = false;
          this.connecting = false;
          console.log(`${this.LOG_PREFIX} 连接关闭，代码:`, event.code, "原因:", event.reason);
          
          // 自动重连逻辑
          if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.attemptReconnect(userId);
          } else {
            console.log(`${this.LOG_PREFIX} 达到最大重连次数(${this.maxReconnectAttempts})，停止重连`);
          }
        };
        
        this.socket.onerror = (error) => {
          this.connecting = false;
          console.error(`${this.LOG_PREFIX} 连接错误:`, error);
          reject(error);
        };
      } catch (error) {
        this.connecting = false;
        console.error(`${this.LOG_PREFIX} 创建WebSocket实例出错:`, error);
        reject(error);
      }
    }).catch(error => {
      // 连接失败时依然返回Promise，但不设置连接状态
      console.error(`${this.LOG_PREFIX} 连接失败，错误:`, error);
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
        console.error(`${this.LOG_PREFIX} 发送消息失败: WebSocket未连接, 状态:`, this.socket?.readyState);
        reject(new Error('WebSocket未连接'));
        return;
      }
      
      try {
        const messageStr = JSON.stringify(message);
        console.log(`${this.LOG_PREFIX} 发送消息:`, message);
        this.socket.send(messageStr);
        resolve();
      } catch (error) {
        console.error(`${this.LOG_PREFIX} 发送消息出错:`, error);
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
    const delay = this.reconnectDelay * this.reconnectAttempts;
    
    console.log(`${this.LOG_PREFIX} 尝试重连 (${this.reconnectAttempts}/${this.maxReconnectAttempts})，延迟: ${delay}ms`);
    
    setTimeout(() => {
      console.log(`${this.LOG_PREFIX} 开始重连...`);
      this.connect(userId).catch(() => {
        // 重连失败，静默处理
        console.error(`${this.LOG_PREFIX} 重连尝试失败`);
      });
    }, delay);
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
    console.log(`${this.LOG_PREFIX} 已注册处理器，消息类型:`, messageType, `当前处理器数:`, this.messageHandlers[messageType].length);
  }

  /**
   * 处理特定消息(注册临时处理器)
   * @param {string} messageType 消息类型
   * @param {Function} handler 消息处理器
   */
  onMessage(messageType, handler) {
    this.registerHandler(messageType, handler);
    console.log(`${this.LOG_PREFIX} 已添加临时消息处理器，类型:`, messageType);
  }

  /**
   * 注销消息处理器
   * @param {string} messageType 消息类型
   * @param {Function} handler 消息处理器
   */
  unregisterHandler(messageType, handler) {
    if (this.messageHandlers[messageType]) {
      const initialLength = this.messageHandlers[messageType].length;
      this.messageHandlers[messageType] = this.messageHandlers[messageType].filter(h => h !== handler);
      console.log(`${this.LOG_PREFIX} 注销处理器，类型:`, messageType, 
        `移除前:`, initialLength, `移除后:`, this.messageHandlers[messageType].length);
    }
  }

  /**
   * 返回注册的处理器数量（用于调试）
   */
  getHandlerCounts() {
    const counts = {};
    for (const type in this.messageHandlers) {
      counts[type] = this.messageHandlers[type].length;
    }
    return counts;
  }

  /**
   * 关闭WebSocket连接
   */
  disconnect() {
    if (this.socket) {
      console.log(`${this.LOG_PREFIX} 主动断开连接`);
      this.socket.close();
      this.socket = null;
    }
    this.isConnected = false;
  }
}

// 创建单例实例
const websocketService = new WebSocketService();
export default websocketService;
