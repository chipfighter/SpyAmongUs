<template>
    <div class="chatroom">
      <h1>房间 {{ 聊天室 }}</h1>
      <!-- 使用v-for循环渲染messages数组中每一个消息 -->
      <div v-for="message in messages" :key="message.id" class="message">
        <!-- 展示每条信息的发送者和消息 -->
        <strong>{{ message.sender }}:</strong> {{ message.text }}
      </div>

      <!-- v-model是双向数据绑定，输入框绑定keydown，然后监听enter -->
      <input v-model="newMessage" placeholder="输入消息" @keydown.enter="sendMessage" />
    </div>
  </template>
  
<script>
import { io } from "socket.io-client"

// 定义返回数据
export default {
  data() {
    return {
      socket: null,
      messages: [],
      newMessage: "",
      roomId: "random-room-id",  // 这里用房间 ID
      userId: "random-user-id",  // 这里用用户 ID
    };
  },
  // vue的生命周期hook
  mounted() {
    // 连接 WebSocket
    this.socket = io(`ws://localhost:8000/ws/${this.roomId}/${this.userId}`);
    
    this.socket.on("message", (message) => {
      this.messages.push({ sender: "Server", text: message });
    });
  },    
  // 定义enter后的方法  
  methods: {
    sendMessage() {
    // 如果不是单纯包含空格，那么封装消息然后传给后端
      if (this.newMessage.trim() !== "") {
        const message = {
          sender: this.userId,
          text: this.newMessage,
        };

        // 发送消息到后端
        this.socket.emit("send_message", message);
        this.messages.push(message); // 临时展示在前端
        this.newMessage = ""; // 清空输入框
      }
    },
  },
};
</script>

<style scoped>
/* 聊天室样式 */
.chatroom {
  width: 400px;
  margin: 0 auto;
  padding: 20px;
  border: 1px solid #ccc;
}

/* message样式 */
.message {
  margin-bottom: 10px;
}

/* 输入框的样式 */
input {
  width: 100%;
  padding: 10px;
  margin-top: 10px;
}
</style>
