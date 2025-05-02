<!-- 游戏结算弹窗 -->
<template>
  <div v-if="visible" class="game-result-modal-overlay" @click.self="handleClose">
    <div class="game-result-modal" :class="{ 'win': isWin, 'lose': !isWin }">
      <!-- 标题区域 -->
      <div class="game-result-header">
        <h2>{{ isWin ? '胜利！' : '失败！' }}</h2>
        <button class="close-button" @click="handleClose">×</button>
      </div>
      
      <!-- 结果内容 -->
      <div class="game-result-content">
        <!-- 结果图标 -->
        <div class="result-icon">
          <span v-if="isWin" class="win-icon">🏆</span>
          <span v-else class="lose-icon">😢</span>
        </div>
        
        <!-- 结果信息 -->
        <div class="result-message">
          <h3>{{ resultTitle }}</h3>
          <p>{{ resultMessage }}</p>
        </div>
        
        <!-- 游戏统计数据 -->
        <div class="game-stats">
          <div class="stat-item">
            <span class="stat-label">游戏时长：</span>
            <span class="stat-value">{{ formatTime(gameStats.duration) }}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">总回合数：</span>
            <span class="stat-value">{{ gameStats.rounds }}</span>
          </div>
        </div>

        <!-- 玩家角色列表 -->
        <div class="players-list">
          <h4>玩家角色</h4>
          <div class="players-grid">
            <div 
              v-for="player in gameStats.players" 
              :key="player.id" 
              class="player-card"
              :class="{
                'current-player': player.id === currentUserId,
                'civilian': player.role === 'civilian',
                'spy': player.role === 'spy',
                'god': player.role === 'god'
              }"
            >
              <div class="player-avatar">
                <img :src="player.avatar || '/default_avatar.jpg'" alt="玩家头像" @error="onAvatarError">
              </div>
              <div class="player-info">
                <div class="player-name">{{ player.name }}</div>
                <div class="player-role">{{ getRoleDisplay(player.role) }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <!-- 按钮区域 -->
      <div class="game-result-actions">
        <button class="result-action-btn" @click="handleClose">返回聊天室</button>
        <button class="result-action-btn" @click="$emit('prepare-next-game')">准备下一局</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue';

// 定义组件属性
const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  isWin: {
    type: Boolean,
    default: false
  },
  winningRole: {
    type: String,
    default: 'civilian' // 'civilian' 或 'spy'
  },
  currentUserId: {
    type: String,
    required: true
  },
  gameStats: {
    type: Object,
    default: () => ({
      duration: 0, // 游戏持续时间（秒）
      rounds: 0,    // 游戏回合数
      players: []   // 玩家列表，每个玩家包含 id, name, role, avatar
    })
  }
});

// 定义组件事件
const emit = defineEmits(['close', 'prepare-next-game']);

// 处理关闭弹窗
const handleClose = () => {
  emit('close');
};

// 获取结果标题
const resultTitle = computed(() => {
  if (props.winningRole === 'draw') {
    return '游戏平局！';
  } else if (props.isWin) {
    return props.winningRole === 'civilian' ? '平民阵营胜利！' : '卧底阵营胜利！';
  } else {
    return props.winningRole === 'civilian' ? '卧底阵营失败！' : '平民阵营失败！';
  }
});

// 获取结果信息
const resultMessage = computed(() => {
  if (props.winningRole === 'draw') {
    return '游戏达到最大回合数，双方未能决出胜负，游戏以平局结束！';
  } else if (props.isWin) {
    if (props.winningRole === 'civilian') {
      return '恭喜！所有卧底已被淘汰，平民取得了胜利！';
    } else {
      return '恭喜！卧底人数已与平民相等，卧底成功混入并取得胜利！';
    }
  } else {
    if (props.winningRole === 'civilian') {
      return '很遗憾！作为卧底，你们已被全部淘汰。平民取得了胜利！';
    } else {
      return '很遗憾！作为平民，无法识别出卧底。卧底成功混入并取得胜利！';
    }
  }
});

// 时间格式化函数
const formatTime = (seconds) => {
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  return `${minutes}分${remainingSeconds}秒`;
};

// 角色显示文本
const getRoleDisplay = (role) => {
  switch (role) {
    case 'civilian':
      return '平民';
    case 'spy':
      return '卧底';
    case 'god':
      return '上帝';
    default:
      return role;
  }
};

// 处理头像加载错误
const onAvatarError = (event) => {
  event.target.src = '/default_avatar.jpg';
};
</script>

<style scoped>
.game-result-modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.7);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
  backdrop-filter: blur(4px);
}

.game-result-modal {
  width: 80%;
  max-width: 800px;
  max-height: 90vh;
  background-color: #fff;
  border-radius: 12px;
  box-shadow: 0 0 30px rgba(0, 0, 0, 0.3);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  animation: modal-appear 0.5s ease-out;
  background-image: linear-gradient(135deg, rgba(255,255,255,0.9) 0%, rgba(255,255,255,0.7) 100%);
}

/* 胜利和失败的不同样式 */
.game-result-modal.win {
  border: 4px solid #ffbb00;
  box-shadow: 0 0 30px rgba(255, 187, 0, 0.5);
  background-image: linear-gradient(135deg, rgba(255, 248, 230, 0.9) 0%, rgba(255, 233, 171, 0.7) 100%);
}

.game-result-modal.lose {
  border: 4px solid #7c7c7c;
  box-shadow: 0 0 30px rgba(0, 0, 0, 0.3);
  background-image: linear-gradient(135deg, rgba(240, 240, 240, 0.9) 0%, rgba(225, 225, 225, 0.7) 100%);
}

.game-result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 15px 20px;
  border-bottom: 1px solid #eaeaea;
}

.win .game-result-header {
  background-color: rgba(255, 187, 0, 0.2);
  border-bottom: 2px solid #ffbb00;
}

.lose .game-result-header {
  background-color: rgba(120, 120, 120, 0.2);
  border-bottom: 2px solid #7c7c7c;
}

.game-result-header h2 {
  margin: 0;
  font-size: 24px;
  font-weight: bold;
}

.win .game-result-header h2 {
  color: #d18700;
}

.lose .game-result-header h2 {
  color: #505050;
}

.close-button {
  background: none;
  border: none;
  font-size: 24px;
  cursor: pointer;
  padding: 0;
  color: #666;
  transition: color 0.2s;
}

.close-button:hover {
  color: #ff4d4f;
}

.game-result-content {
  padding: 20px;
  overflow-y: auto;
  flex: 1;
}

.result-icon {
  font-size: 60px;
  text-align: center;
  margin-bottom: 20px;
}

.win-icon {
  animation: trophy-shine 2s infinite;
}

.lose-icon {
  animation: lose-shake 2s infinite;
}

.result-message {
  text-align: center;
  margin-bottom: 30px;
}

.result-message h3 {
  font-size: 22px;
  margin-bottom: 10px;
}

.win .result-message h3 {
  color: #d18700;
}

.lose .result-message h3 {
  color: #505050;
}

.result-message p {
  font-size: 16px;
  color: #666;
  line-height: 1.5;
}

.game-stats {
  background-color: rgba(255, 255, 255, 0.5);
  border-radius: 8px;
  padding: 15px;
  margin-bottom: 20px;
  display: flex;
  justify-content: space-around;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.stat-label {
  font-size: 14px;
  color: #666;
  margin-bottom: 5px;
}

.stat-value {
  font-size: 18px;
  font-weight: bold;
  color: #333;
}

.players-list {
  margin-top: 20px;
}

.players-list h4 {
  font-size: 18px;
  margin-bottom: 15px;
  text-align: center;
  position: relative;
}

.players-list h4:after {
  content: "";
  display: block;
  width: 50px;
  height: 3px;
  background-color: #d9d9d9;
  margin: 10px auto 0;
}

.win .players-list h4:after {
  background-color: #ffbb00;
}

.players-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 15px;
}

.player-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 15px;
  background-color: rgba(255, 255, 255, 0.7);
  border-radius: 8px;
  transition: transform 0.2s;
  border: 1px solid #eaeaea;
}

.player-card:hover {
  transform: translateY(-5px);
  box-shadow: 0 5px 15px rgba(0, 0, 0, 0.1);
}

.player-card.current-player {
  border: 2px solid #1890ff;
  background-color: rgba(24, 144, 255, 0.1);
}

.player-card.civilian {
  border-left: 4px solid #52c41a;
}

.player-card.spy {
  border-left: 4px solid #ff4d4f;
}

.player-card.god {
  border-left: 4px solid #722ed1;
}

.player-avatar {
  width: 50px;
  height: 50px;
  border-radius: 50%;
  overflow: hidden;
  margin-bottom: 10px;
}

.player-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.player-info {
  text-align: center;
  width: 100%;
}

.player-name {
  font-weight: bold;
  margin-bottom: 5px;
  font-size: 14px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}

.player-role {
  font-size: 12px;
  color: #666;
  padding: 2px 8px;
  border-radius: 10px;
  background-color: #f5f5f5;
}

.civilian .player-role {
  background-color: rgba(82, 196, 26, 0.1);
  color: #389e0d;
}

.spy .player-role {
  background-color: rgba(255, 77, 79, 0.1);
  color: #cf1322;
}

.god .player-role {
  background-color: rgba(114, 46, 209, 0.1);
  color: #531dab;
}

.game-result-actions {
  display: flex;
  justify-content: center;
  gap: 20px;
  padding: 20px;
  border-top: 1px solid #eaeaea;
}

.result-action-btn {
  padding: 10px 20px;
  font-size: 16px;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.3s;
  background-color: #f5f5f5;
  border: 1px solid #d9d9d9;
  color: #333;
}

.result-action-btn:hover {
  background-color: #e6f7ff;
  border-color: #1890ff;
  color: #1890ff;
}

.win .result-action-btn:hover {
  background-color: #fff7e6;
  border-color: #ffbb00;
  color: #d18700;
}

/* 动画效果 */
@keyframes modal-appear {
  0% { opacity: 0; transform: scale(0.9); }
  100% { opacity: 1; transform: scale(1); }
}

@keyframes trophy-shine {
  0% { transform: scale(1); }
  50% { transform: scale(1.1); filter: drop-shadow(0 0 10px gold); }
  100% { transform: scale(1); }
}

@keyframes lose-shake {
  0%, 100% { transform: translateX(0); }
  10%, 30%, 50%, 70%, 90% { transform: translateX(-3px); }
  20%, 40%, 60%, 80% { transform: translateX(3px); }
}

/* 响应式调整 */
@media (max-width: 768px) {
  .game-result-modal {
    width: 95%;
  }
  
  .players-grid {
    grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  }
  
  .game-stats {
    flex-direction: column;
    gap: 10px;
  }
}
</style> 