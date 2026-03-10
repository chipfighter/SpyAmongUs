<template>
  <div class="dialog-overlay" v-if="show" @click.self="$emit('close')">
    <div class="create-room-dialog">
      <div class="dialog-header">
        <h2>创建新房间</h2>
        <button class="close-btn" @click="$emit('close')">×</button>
      </div>
      
      <div class="dialog-body">
        <!-- 错误提示 -->
        <div class="error-message" v-if="formError">
          {{ formError }}
        </div>
        
        <div class="form-group">
          <label>房间名称</label>
          <input v-model="roomData.room_name" type="text" placeholder="输入房间名称" class="input-control">
        </div>
        
        <div class="form-group">
          <label>是否公开</label>
          <div class="toggle-switch">
            <label class="switch">
              <input type="checkbox" v-model="roomData.is_public">
              <span class="slider round"></span>
            </label>
            <span class="toggle-label">{{ roomData.is_public ? '公开' : '私密' }}</span>
          </div>
        </div>
        
        <div class="form-row">
          <div class="form-group">
            <label>总玩家数 <span class="help-text">(3-8人)</span></label>
            <input v-model.number="roomData.total_players" type="number" min="3" max="8" class="input-control">
          </div>
          
          <div class="form-group">
            <label>卧底数量 <span class="help-text">(1-3人)</span></label>
            <input v-model.number="roomData.spy_count" type="number" min="1" max="3" class="input-control">
          </div>
        </div>
        
        <div class="form-group">
          <label>最大回合数 <span class="help-text">(基础回合数：总人数-卧底数；最大回合数：≤10)</span></label>
          <input v-model.number="roomData.max_rounds" type="number" min="1" max="10" class="input-control">
        </div>
        
        <div class="form-row">
          <div class="form-group">
            <label>发言时间 <span class="help-text">(≤60秒)</span></label>
            <input v-model.number="roomData.speak_time" type="number" min="30" max="60" class="input-control">
          </div>
          
          <div class="form-group">
            <label>遗言时间 <span class="help-text">(≤60秒)</span></label>
            <input v-model.number="roomData.last_words_time" type="number" min="30" max="60" class="input-control">
          </div>
        </div>
        
        <div class="form-group">
          <label>大模型自由聊天（当前版本不支持）</label>
          <div class="toggle-switch">
            <label class="switch">
              <input type="checkbox" v-model="roomData.llm_free">
              <span class="slider round"></span>
            </label>
            <span class="toggle-label">{{ roomData.llm_free ? '允许' : '不允许' }}</span>
          </div>
        </div>
      </div>
      
      <div class="dialog-footer">
        <button class="cancel-btn" @click="$emit('close')">取消</button>
        <button class="create-btn" @click="validateAndCreate">确认创建</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  show: { type: Boolean, default: false }
})

const emit = defineEmits(['close', 'create'])

const formError = ref('')
const roomData = ref({
  room_name: '',
  is_public: true,
  total_players: 5,
  spy_count: 1,
  max_rounds: 10,
  speak_time: 60,
  last_words_time: 60,
  llm_free: false
})

function validateAndCreate() {
  formError.value = ''

  // 验证房间名称
  if (!roomData.value.room_name.trim()) {
    formError.value = '请输入房间名称'
    return
  }
  if (roomData.value.room_name.length > 20) {
    formError.value = '房间名称不能超过20个字符'
    return
  }

  // 验证玩家数量
  const totalPlayers = roomData.value.total_players
  if (totalPlayers < 3 || totalPlayers > 8) {
    formError.value = '总玩家数必须在3-8之间'
    return
  }

  // 验证卧底数量
  const spyCount = roomData.value.spy_count
  if (spyCount < 1 || spyCount > 3) {
    formError.value = '卧底数量必须在1-3之间'
    return
  }
  if (spyCount >= totalPlayers) {
    formError.value = '卧底数量必须小于总玩家数'
    return
  }

  // 验证回合数
  const baseRounds = totalPlayers - spyCount
  if (roomData.value.max_rounds < 1 || roomData.value.max_rounds > 10) {
    formError.value = '最大回合数必须在1-10之间'
    return
  }

  // 验证发言时间
  if (roomData.value.speak_time < 30 || roomData.value.speak_time > 60) {
    formError.value = '发言时间必须在30-60秒之间'
    return
  }

  // 验证遗言时间
  if (roomData.value.last_words_time < 30 || roomData.value.last_words_time > 60) {
    formError.value = '遗言时间必须在30-60秒之间'
    return
  }

  // 触发创建事件，传递数据给父组件
  emit('create', { ...roomData.value })
}
</script>

<style scoped>
.dialog-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
}

.create-room-dialog {
  background: #1e1e2e;
  border-radius: 12px;
  padding: 20px;
  width: 90%;
  max-width: 450px;
  max-height: 85vh;
  overflow-y: auto;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.5);
}

.dialog-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
}

.dialog-header h2 {
  color: #e0e0e0;
  font-size: 1.2rem;
  margin: 0;
}

.close-btn {
  background: none;
  border: none;
  color: #888;
  font-size: 1.5rem;
  cursor: pointer;
}

.close-btn:hover {
  color: #fff;
}

.dialog-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.error-message {
  background: rgba(255, 80, 80, 0.15);
  border: 1px solid rgba(255, 80, 80, 0.3);
  border-radius: 8px;
  padding: 8px 12px;
  color: #ff6b6b;
  font-size: 0.85rem;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.form-group label {
  color: #aaa;
  font-size: 0.85rem;
}

.help-text {
  color: #666;
  font-size: 0.75rem;
}

.input-control {
  background: #2a2a3e;
  border: 1px solid #3a3a4e;
  border-radius: 8px;
  padding: 8px 12px;
  color: #e0e0e0;
  font-size: 0.9rem;
}

.input-control:focus {
  border-color: #6c5ce7;
  outline: none;
}

.form-row {
  display: flex;
  gap: 12px;
}

.form-row .form-group {
  flex: 1;
}

.toggle-switch {
  display: flex;
  align-items: center;
  gap: 10px;
}

.switch {
  position: relative;
  display: inline-block;
  width: 44px;
  height: 24px;
}

.switch input {
  opacity: 0;
  width: 0;
  height: 0;
}

.slider {
  position: absolute;
  cursor: pointer;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: #3a3a4e;
  transition: .3s;
}

.slider:before {
  position: absolute;
  content: "";
  height: 18px;
  width: 18px;
  left: 3px;
  bottom: 3px;
  background-color: white;
  transition: .3s;
}

input:checked + .slider {
  background-color: #6c5ce7;
}

input:checked + .slider:before {
  transform: translateX(20px);
}

.slider.round {
  border-radius: 24px;
}

.slider.round:before {
  border-radius: 50%;
}

.toggle-label {
  color: #ccc;
  font-size: 0.85rem;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 15px;
  padding-top: 12px;
  border-top: 1px solid #2a2a3e;
}

.cancel-btn {
  padding: 8px 20px;
  background: #3a3a4e;
  border: none;
  border-radius: 8px;
  color: #ccc;
  cursor: pointer;
}

.cancel-btn:hover {
  background: #4a4a5e;
}

.create-btn {
  padding: 8px 20px;
  background: linear-gradient(135deg, #6c5ce7, #a29bfe);
  border: none;
  border-radius: 8px;
  color: white;
  cursor: pointer;
  font-weight: 500;
}

.create-btn:hover {
  opacity: 0.9;
}
</style>
