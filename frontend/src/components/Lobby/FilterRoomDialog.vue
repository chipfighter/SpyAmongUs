<template>
  <div class="dialog-overlay" v-if="show" @click.self="$emit('close')">
    <div class="filter-room-dialog">
      <div class="dialog-header">
        <h2>筛选房间</h2>
        <button class="close-btn" @click="$emit('close')">×</button>
      </div>
      <div class="dialog-body">
        <!-- 按房间名筛选 -->
        <div class="form-group">
          <label>房间名称</label>
          <div class="filter-options">
            <label class="filter-option">
              <input type="checkbox" v-model="localOptions.roomName">
              <span>包含</span>
              <input 
                type="text" 
                v-model="localOptions.roomNameValue" 
                class="text-input"
                :disabled="!localOptions.roomName"
                placeholder="输入房间名关键词"
              >
            </label>
          </div>
        </div>
        
        <!-- 按房主用户名筛选 -->
        <div class="form-group">
          <label>房主用户名</label>
          <div class="filter-options">
            <label class="filter-option">
              <input type="checkbox" v-model="localOptions.hostName">
              <span>包含</span>
              <input 
                type="text" 
                v-model="localOptions.hostNameValue" 
                class="text-input"
                :disabled="!localOptions.hostName"
                placeholder="输入房主用户名关键词"
              >
            </label>
          </div>
        </div>
        
        <!-- 按用户ID筛选 -->
        <div class="form-group">
          <label>用户ID</label>
          <div class="filter-options">
            <label class="filter-option">
              <input type="checkbox" v-model="localOptions.userId">
              <span>精确匹配</span>
              <input 
                type="text" 
                v-model="localOptions.userIdValue" 
                class="text-input"
                :disabled="!localOptions.userId"
                placeholder="输入完整用户ID"
              >
            </label>
          </div>
        </div>
        
        <div class="form-group">
          <label>房间状态</label>
          <div class="filter-options">
            <label class="filter-option">
              <input type="checkbox" v-model="localOptions.waitingOnly">
              <span>仅等待中</span>
            </label>
          </div>
        </div>
        
        <div class="form-group">
          <label>玩家数量</label>
          <div class="filter-options">
            <label class="filter-option">
              <input type="checkbox" v-model="localOptions.minPlayers">
              <span>至少有 </span>
              <input 
                type="number" 
                v-model.number="localOptions.minPlayersCount" 
                min="1" 
                max="8" 
                class="small-input"
                :disabled="!localOptions.minPlayers"
              >
              <span> 名玩家</span>
            </label>
          </div>
        </div>
        
        <div class="form-group">
          <label>卧底数量</label>
          <div class="filter-options">
            <label class="filter-option">
              <input type="checkbox" v-model="localOptions.spyCount">
              <span>卧底数量为 </span>
              <input 
                type="number" 
                v-model.number="localOptions.spyCountValue" 
                min="1" 
                max="3" 
                class="small-input"
                :disabled="!localOptions.spyCount"
              >
            </label>
          </div>
        </div>
      </div>
      <div class="dialog-footer">
        <button class="cancel-btn" @click="handleReset">重置</button>
        <button class="create-btn" @click="handleApply">应用筛选</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  show: { type: Boolean, default: false }
})

const emit = defineEmits(['close', 'apply', 'reset'])

const defaultOptions = () => ({
  waitingOnly: false,
  minPlayers: false,
  minPlayersCount: 3,
  spyCount: false,
  spyCountValue: 1,
  roomName: false,
  roomNameValue: '',
  hostName: false,
  hostNameValue: '',
  userId: false,
  userIdValue: ''
})

const localOptions = ref(defaultOptions())

function handleReset() {
  localOptions.value = defaultOptions()
  emit('reset')
}

function handleApply() {
  emit('apply', { ...localOptions.value })
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

.filter-room-dialog {
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

.form-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.form-group label {
  color: #aaa;
  font-size: 0.85rem;
}

.filter-options {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.filter-option {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #ccc;
  font-size: 0.85rem;
}

.filter-option input[type="checkbox"] {
  accent-color: #6c5ce7;
}

.text-input {
  background: #2a2a3e;
  border: 1px solid #3a3a4e;
  border-radius: 6px;
  padding: 4px 8px;
  color: #e0e0e0;
  font-size: 0.85rem;
  flex: 1;
}

.text-input:disabled {
  opacity: 0.5;
}

.small-input {
  background: #2a2a3e;
  border: 1px solid #3a3a4e;
  border-radius: 6px;
  padding: 4px 8px;
  color: #e0e0e0;
  font-size: 0.85rem;
  width: 60px;
}

.small-input:disabled {
  opacity: 0.5;
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
