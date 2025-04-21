<template>
  <div class="sidebar-container" :class="{ 'collapsed': isCollapsed, 'transitioning': isTransitioning }">
    <!-- 拉伸手柄 -->
    <div class="resize-handle" @mousedown="handleStartResize($event)"></div>
    
    <!-- 使用与右侧栏一致的头部和按钮布局 -->
    <div class="sidebar-header">
      <h3 class="sidebar-title">游戏设置</h3>
      <button class="collapse-btn" @click="toggleCollapse" title="游戏信息">
        {{ isCollapsed ? '▶' : '◀' }}
      </button>
    </div>

    <!-- 内容区域 - 使用fade过渡效果 -->
    <transition name="fade">
      <div v-show="!isCollapsed && !isTransitioning" class="sidebar-inner-content">
        <div class="sidebar-content">
          <!-- 游戏信息区域 -->
          <div class="sidebar-section">
            <div class="info-item">
              <span class="label">总玩家数:</span>
              <span class="value">{{ roomInfo.total_players || '-' }}人</span>
            </div>
            <div class="info-item">
              <span class="label">卧底数量:</span>
              <span class="value">{{ roomInfo.spy_count || '-' }}人</span>
            </div>
            <div class="info-item">
              <span class="label">最大回合数:</span>
              <span class="value">{{ roomInfo.max_rounds || '-' }}轮</span>
            </div>
            <div class="info-item">
              <span class="label">发言时间:</span>
              <span class="value">{{ roomInfo.speak_time || '-' }}秒</span>
            </div>
            <div class="info-item">
              <span class="label">遗言时间:</span>
              <span class="value">{{ roomInfo.last_words_time || '-' }}秒</span>
            </div>
          </div>

          <!-- 游戏规则区域 -->
          <div class="sidebar-section">
            <h3 class="section-title">游戏规则</h3>
            <div class="rule-placeholder">
              游戏规则说明将在后续版本添加
            </div>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, onMounted, watchEffect } from 'vue';

const props = defineProps({
  roomInfo: {
    type: Object,
    required: true,
    default: () => ({})
  },
  users: {
    type: Array,
    required: true,
    default: () => []
  },
  isCollapsed: {
    type: Boolean,
    required: false,
    default: true  // 默认收起状态
  }
});

// 调试信息，检查接收到的房间信息
watchEffect(() => {
  console.log('[RoomSidebar] 接收到房间信息:', JSON.stringify(props.roomInfo));
});

onMounted(() => {
  console.log('[RoomSidebar] 组件挂载完成，房间信息:', JSON.stringify(props.roomInfo));
});

const emit = defineEmits(['copy-invite-code', 'toggle-collapse']);

const isTransitioning = ref(false);

function toggleCollapse() {
  isTransitioning.value = true;
  
  // 延迟状态切换，让按钮先隐藏
  setTimeout(() => {
    emit('toggle-collapse');
    
    // 过渡完成后移除过渡状态
    setTimeout(() => {
      isTransitioning.value = false;
    }, 300); // 与CSS过渡时间匹配
  }, 150);
}

function handleStartResize(event) {
  if (props.isCollapsed) return;
  
  event.stopPropagation();
  event.preventDefault();
  
  const sidebarContainer = event.target.closest('.sidebar-container');
  if (!sidebarContainer) {
    console.warn("Cannot find .sidebar-container element for resizing");
    return;
  }
  
  const initialX = event.clientX;
  const initialWidth = sidebarContainer.offsetWidth;
  
  const minWidth = 200;
  const maxWidth = 400;
  
  sidebarContainer.classList.add('resizing');
  
  const handleMouseMove = (moveEvent) => {
    const deltaX = moveEvent.clientX - initialX;
    let newWidth = initialWidth + deltaX;
    if (newWidth < minWidth) newWidth = minWidth;
    if (newWidth > maxWidth) newWidth = maxWidth;
    sidebarContainer.style.width = `${newWidth}px`;
  };
  
  const handleMouseUp = () => {
    sidebarContainer.classList.remove('resizing');
    document.removeEventListener('mousemove', handleMouseMove);
    document.removeEventListener('mouseup', handleMouseUp);
  };
  
  document.addEventListener('mousemove', handleMouseMove);
  document.addEventListener('mouseup', handleMouseUp);
}
</script>

<style scoped>
.sidebar-container {
  width: 250px;
  height: 100%;
  background-color: white;
  border-right: 1px solid #e0e0e0;
  position: relative;
  transition: width 0.3s ease;
  display: flex;
  flex-direction: column;
  z-index: 10;
  overflow: hidden; /* 限制内容在容器内 */
}

.sidebar-container.resizing {
  transition: none;
}

.sidebar-container.collapsed {
  width: 60px !important; /* 与右侧栏保持一致，使用!important确保优先级 */
}

.sidebar-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 15px;
  border-bottom: 1px solid #f0f0f0;
}

.sidebar-title {
  margin: 0;
  font-size: 1.1rem;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
}

.sidebar-container.collapsed .sidebar-header h3,
.sidebar-container.collapsed .sidebar-inner-content {
  display: none;
}

/* 调整按钮与右侧栏一致 */
.collapse-btn {
  background: none;
  border: none;
  font-size: 16px;
  cursor: pointer;
  padding: 5px;
  border-radius: 4px;
  transition: opacity 0.15s ease;
  flex-shrink: 0; /* 防止按钮被挤压 */
}

.collapse-btn:hover {
  background-color: #f0f0f0;
}

.transitioning .collapse-btn {
  opacity: 0;
}

.resize-handle {
  position: absolute;
  right: 0;
  top: 0;
  width: 5px;
  height: 100%;
  cursor: e-resize;
  background-color: transparent;
  z-index: 10;
}

.resize-handle:hover {
  background-color: rgba(24, 144, 255, 0.1);
}

/* 内容容器 */
.sidebar-inner-content {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.sidebar-content {
  padding: 15px;
  overflow-y: auto;
  flex: 1;
}

.sidebar-section {
  margin-bottom: 25px;
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  color: #333;
  margin: 0 0 15px 0;
  padding-bottom: 8px;
  border-bottom: 1px solid #f0f0f0;
}

.info-item {
  margin-bottom: 10px;
  display: flex;
  align-items: center;
}

.label {
  color: #666;
  font-size: 13px;
  width: 85px;
  flex-shrink: 0;
}

.value {
  font-size: 14px;
  color: #333;
  font-weight: 500;
  flex: 1;
}

.code-container {
  display: flex;
  align-items: center;
  flex: 1;
}

.invite-code {
  font-family: monospace;
  background: #f5f5f5;
  padding: 2px 4px;
  border-radius: 3px;
  font-size: 12px;
}

.copy-btn {
  background: none;
  border: none;
  padding: 4px;
  margin-left: 5px;
  cursor: pointer;
  border-radius: 3px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.copy-btn:hover {
  background-color: #f0f0f0;
}

.copy-icon {
  font-size: 14px;
}

.rule-placeholder {
  font-size: 13px;
  color: #999;
  padding: 15px;
  background: #f9f9f9;
  border-radius: 6px;
  text-align: center;
}

/* 添加淡入淡出效果 */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

@media (max-width: 768px) {
  .sidebar-container {
    position: absolute;
    left: 0;
    top: 0;
    height: 100%;
    z-index: 20;
  }
  
  .sidebar-container:not(.collapsed) {
    box-shadow: 2px 0 10px rgba(0, 0, 0, 0.1);
  }
}
</style> 