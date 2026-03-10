<template>
  <div class="users-container" :class="{ 'collapsed': isCollapsed, 'transitioning': isTransitioning }">
    <div class="resize-handle" @mousedown="emit('start-resize', $event)"></div>
    <div class="users-header">
      <button class="collapse-btn" @click="handleToggleCollapse">
        {{ isCollapsed ? '◀' : '▶' }}
      </button>
      <h3>玩家列表 ({{ users.length }}/{{ totalPlayers || 8 }})</h3>
    </div>
    
    <div class="users-list">
      <!-- 所有用户（包括真实用户和AI玩家） -->
      <div v-for="user in users" :key="user.id" class="user-item" 
           :class="{
             'selected': selectedUserId === user.id,
             'current': user.id === currentUserId, 
             'ai-player': isAiPlayer(user.id),
             'spy-teammate': spyTeammates.includes(user.id) && currentRole === 'spy',
             'speaking': user.id === currentSpeakerId,
             'eliminated': user.eliminated,
             [`user-${user.id}`]: true // 添加包含用户ID的类名，作为后备查找方式
           }"
           :data-user-id="user.id"
           @click="toggleActionButtons(user.id)">
        <div class="user-item-content">
          <!-- 用户基本信息 -->
          <div class="user-avatar" :class="{ 'eliminated': user.eliminated }">
            <img :src="user.avatar_url || '/default_avatar.jpg'" alt="用户头像" @error="onAvatarError">
            <div v-if="readyUsers.includes(user.id) && !gameStarted" class="ready-mark">✓</div>
            <div v-if="isHost && user.id === hostId" class="host-mark">🏠</div>
            <div v-if="spyTeammates.includes(user.id) && currentRole === 'spy'" class="spy-mark">🕵️</div>
            <span v-if="user.id === hostId" class="host-badge">房主</span>
            <span v-if="isAiPlayer(user.id)" class="ai-badge">AI</span>
            <!-- 添加被淘汰标记 -->
            <div v-if="user.eliminated" class="eliminated-mark">✗</div>
          </div>
          <div class="user-info">
            <div class="user-name">{{ getDisplayUsername(user) }}</div>
            <!-- 修改淘汰状态显示，包含角色信息 -->
            <div v-if="user.eliminated" class="eliminated-status">
              已淘汰 - {{ getRoleName(user.id) }}
            </div>
          </div>
          
          <!-- 准备状态牌 - 在游戏未开始并且已准备时显示 -->
          <div v-if="!gameStarted && readyUsers.includes(user.id)" class="user-status-badge ready-status">
            已准备
          </div>
          
          <!-- 角色身份牌 - 在游戏开始后显示 -->
          <div v-if="gameStarted && shouldShowRole(user.id)" class="user-role" :class="getRoleClass(user.id)">
            <span class="role-name">{{ getRoleName(user.id) }}</span>
          </div>
          
          <!-- 投票计数显示 - 在投票阶段显示，对所有玩家都显示票数 -->
          <div v-if="roomStore.gamePhase === 'voting'" class="vote-count" :class="{'has-votes': getVoteCount(user.id) > 0}" :title="getVotersTooltip(user.id)">
            <span class="vote-number">{{ getVoteCount(user.id) }}</span>
            <span class="vote-text">票</span>
          </div>
          <!-- 添加调试输出 -->
          <div v-if="debug && roomStore.gamePhase === 'voting'" class="debug-votes">
            [userId: {{user.id}}, votes: {{JSON.stringify(roomStore.voteCount)}}]
          </div>
          
          <!-- 当前用户已进行投票的全局提示（仅在投票阶段显示） -->
          <div v-if="roomStore.gamePhase === 'voting' && 
                    Object.keys(roomStore.votedPlayers).includes(currentUserId) && 
                    user.id === currentUserId" 
               class="user-voting-status">
            你已投给:
            <span class="voted-target">{{ getVotedTargetName() }}</span>
          </div>
          
          <!-- 发言指示器和倒计时 -->
          <div v-if="user.id === currentSpeakerId" class="speaking-indicator">
            <!-- 添加明显的倒计时数字 -->
            <div class="countdown-number">{{ countdownSeconds }}秒</div>
            
            <!-- 移除波形动画，不保留任何指示器 -->
            
            <div class="countdown-wrapper">
              <div class="countdown-bar" :style="{ width: `${countdownPercentage}%` }"></div>
            </div>
          </div>
        </div>
        
        <!-- 用户操作按钮组 - 只对非当前用户且非AI用户显示 -->
        <div v-if="selectedUserId === user.id && user.id !== currentUserId && !isAiPlayer(user.id) && !gameStarted" class="user-actions">
          <button class="action-btn" title="添加好友" @click.stop="emit('add-friend', user.id)">
            <i class="action-icon">👥</i>
            <span class="action-text">添加好友</span>
          </button>
          <button class="action-btn" title="用户详情" @click.stop="emit('view-user-details', user.id)">
            <i class="action-icon">ℹ️</i>
            <span class="action-text">用户详情</span>
          </button>
          <button class="action-btn" title="私信" @click.stop="emit('private-message', user.id)">
            <i class="action-icon">✉️</i>
            <span class="action-text">发送私信</span>
          </button>
          <!-- 房主可见的踢出按钮 -->
          <button v-if="isHost && user.id !== currentUserId" class="action-btn kick-btn" title="踢出房间" @click.stop="emit('kick-user', user.id)">
            <i class="action-icon">🚫</i>
            <span class="action-text">踢出房间</span>
          </button>
        </div>
      </div>
    </div>
    
    <!-- AI助理分割线和头像 - 仅在游戏未开始时显示 -->
    <div v-if="!gameStarted" class="ai-assistant-container">
      <div class="divider"></div>
      <div class="ai-assistant-item">
        <div class="user-avatar ai-assistant-avatar">
          <img src="/default_room_robot_avatar.jpg" alt="AI助理头像" @error="onAvatarError">
        </div>
        <div class="user-info">
          <div class="user-name">AI助理</div>
          <div class="ai-assistant-tip">可以通过聊天框@AI助理</div>
        </div>
      </div>
    </div>
    
    <!-- 准备按钮区域 - 仅在游戏未开始时显示 -->
    <div v-if="!gameStarted" class="ready-button-container">
      <button 
        class="ready-button" 
        :class="{ 'ready-active': isReady }"
        @click="emit('toggle-ready')"
      >
        {{ isReady ? '取消准备' : '准备游戏' }}
      </button>
    </div>
    
    <!-- 按钮区域 -->
    <div class="user-action-buttons" v-if="gameStarted">
      <!-- 投票按钮 - 始终显示但在非投票阶段禁用 -->
      <button 
        class="vote-button" 
        @click="handleVoteClick"
        :disabled="roomStore.gamePhase !== 'voting' || !selectedUserId || hasVoted"
        :title="getVoteButtonTitle()"
        @mouseenter="logVoteButtonStatus"
        :class="{'voted': hasVoted}"
      >
        <span v-if="roomStore.gamePhase !== 'voting'">等待投票</span>
        <span v-else-if="hasVoted">✓</span>
        <span v-else>{{ selectedUserId ? '确认投票' : '投票' }}</span>
      </button>
      
      <!-- 秘密聊天按钮 - 仅对卧底显示，在投票阶段可用 -->
      <button 
        v-if="currentRole === 'spy'"
        class="secret-chat-button" 
        :disabled="roomStore.gamePhase !== 'voting'"
        @click="emit('toggle-secret-chat')"
      >
        秘密聊天
      </button>
    </div>
    
    <!-- 投票统计面板 - 仅在投票阶段显示 -->
    <div v-if="roomStore.gamePhase === 'voting'" class="vote-summary-panel">
      <div class="vote-summary-header">
        <span class="vote-summary-title">投票统计</span>
        <span class="vote-summary-count">{{ Object.keys(getVotingUsers()).length }}/{{ getAlivePlayersCount() }}</span>
      </div>
      <div class="vote-summary-content">
        <div v-for="(voteCount, userId) in roomStore.voteCount" :key="userId" class="vote-summary-item" v-if="Number(voteCount) > 0">
          <span class="vote-summary-name">{{ getUsernameById(userId) }}</span>
          <span class="vote-summary-votes">{{ voteCount }} 票</span>
        </div>
        <div v-if="Object.keys(roomStore.voteCount).length === 0" class="vote-summary-empty">
          暂无投票
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted, onBeforeUnmount } from 'vue';
import { useRoomStore } from '../../stores/room';
import { useUserStore } from '../../stores/userStore';

const props = defineProps({
  users: {
    type: Array,
    required: true,
    default: () => []
  },
  hostId: {
    type: String,
    required: true,
    default: ''
  },
  totalPlayers: {
    type: Number,
    required: true,
    default: 8
  },
  currentUserId: { 
    type: String,
    required: true,
    default: ''
  },
  readyUsers: {
    type: Array,
    required: true,
    default: () => []
  },
  gameStarted: {
    type: Boolean,
    required: true,
    default: false
  },
  isReady: {
    type: Boolean,
    required: true,
    default: false
  },
  isCollapsed: {
    type: Boolean,
    required: true,
    default: false
  },
  isHost: {
    type: Boolean,
    required: true
  },
  isGodPolling: {
    type: Boolean,
    default: false
  },
  roles: {
    type: Object,
    default: null
  },
  currentRole: {
    type: String,
    default: ''
  },
  spyTeammates: {
    type: Array,
    default: () => []
  },
  // 添加发言相关的props
  currentSpeakerId: {
    type: String,
    default: ''
  },
  speakTimeoutSeconds: {
    type: Number,
    default: 0
  }
});

const emit = defineEmits([
  'toggle-collapse', 
  'toggle-ready', 
  'toggle-secret-chat',
  'start-resize',
  'add-friend',
  'view-user-details',
  'private-message',
  'kick-user',
  'vote'
]);

// 添加倒计时状态
const countdownSeconds = ref(0);
let countdownTimer = null;

// 添加调试模式开关
const debug = ref(false);

// 选中的用户
const selectedUserId = ref(null);

// 计算倒计时百分比
const countdownPercentage = computed(() => {
  if (props.speakTimeoutSeconds <= 0) return 100;
  return (countdownSeconds.value / props.speakTimeoutSeconds) * 100;
});

// 监听当前发言者的变化
watch(() => props.currentSpeakerId, (newSpeakerId, oldSpeakerId) => {
  // 清除旧的倒计时
  if (countdownTimer) {
    clearInterval(countdownTimer);
    countdownTimer = null;
  }
  
  // 如果有新的发言者且有超时时间，开始倒计时
  if (newSpeakerId && props.speakTimeoutSeconds > 0) {
    countdownSeconds.value = props.speakTimeoutSeconds;
    countdownTimer = setInterval(() => {
      if (countdownSeconds.value > 0) {
        countdownSeconds.value -= 1;
      } else {
        // 倒计时结束
        clearInterval(countdownTimer);
        countdownTimer = null;
      }
    }, 1000);
  }
}, { immediate: true });

// 监听超时时间的变化
watch(() => props.speakTimeoutSeconds, (newTimeout) => {
  if (props.currentSpeakerId && newTimeout > 0) {
    // 重置倒计时
    countdownSeconds.value = newTimeout;
  }
});

// 在组件卸载时清除倒计时
onBeforeUnmount(() => {
  if (countdownTimer) {
    clearInterval(countdownTimer);
  }
});

// 添加过渡状态
const isTransitioning = ref(false);

// 处理折叠/展开带有动画效果
const handleToggleCollapse = () => {
  isTransitioning.value = true;
  
  // 延迟状态切换，让按钮先隐藏
  setTimeout(() => {
    emit('toggle-collapse');
    
    // 过渡完成后移除过渡状态
    setTimeout(() => {
      isTransitioning.value = false;
    }, 300); // 与CSS过渡时间匹配
  }, 150);
};

// 切换显示用户操作按钮
const toggleActionButtons = (userId) => {
  // 如果是AI玩家，只高亮选中但不显示操作按钮
  if (isAiPlayer(userId)) {
    selectedUserId.value = userId; // 选中AI玩家
    return;
  }
  
  // 投票阶段的选择逻辑
  if (roomStore.gamePhase === 'voting') {
    console.log('[UserList] 投票阶段选择玩家:', userId);
    console.log('[UserList] 当前阶段:', roomStore.gamePhase);
    console.log('[UserList] 当前选中玩家:', selectedUserId.value);
    
    // 在投票阶段，选中并切换
    if (selectedUserId.value === userId) {
      selectedUserId.value = null; // 再次点击取消选择
      console.log('[UserList] 取消选择玩家:', userId);
    } else {
      selectedUserId.value = userId; // 选中新玩家
      console.log('[UserList] 选中新玩家:', userId);
      
      // 如果选中了新玩家，显示提示消息
      if (userId) {
        // 通过事件分发系统显示提示
        document.dispatchEvent(new CustomEvent('room-toast', { 
          detail: { type: 'info', message: '已选择投票目标，点击投票按钮确认' } 
        }));
      }
    }
    return;
  }
  
  // 对于普通用户，切换选中状态
  if (selectedUserId.value === userId) {
    selectedUserId.value = null;
  } else {
    selectedUserId.value = userId;
  }
};

// 添加点击文档其他位置关闭操作按钮的事件
const closeActionButtons = () => {
  selectedUserId.value = null;
};

// 在组件挂载时添加事件监听
onMounted(() => {
  document.addEventListener('click', (event) => {
    // 检查点击是否在用户列表外
    const usersList = document.querySelector('.users-list');
    if (usersList && !usersList.contains(event.target) && selectedUserId.value !== null) {
      closeActionButtons();
    }
  });
  
  // 添加清除选中状态的事件监听
  document.addEventListener('clear-user-selection', () => {
    selectedUserId.value = null;
  });
});

// 在组件卸载时移除事件监听
onBeforeUnmount(() => {
  document.removeEventListener('click', closeActionButtons);
  document.removeEventListener('clear-user-selection', () => {
    selectedUserId.value = null;
  });
});

const onAvatarError = (event) => {
  event.target.src = '/default_avatar.jpg';
};

// 判断是否为AI玩家
const isAiPlayer = (userId) => {
  return typeof userId === 'string' && userId.startsWith('llm_player_');
};

// 获取用户显示名称
const getDisplayUsername = (user) => {
  if (isAiPlayer(user.id)) {
    // 从llm_player_1提取数字部分，显示为"AI玩家_1"
    const playerNumber = user.id.replace('llm_player_', '');
    return `AI玩家_${playerNumber}`;
  }
  return user.username || '未知用户';
};

// 获取用户状态显示文本
const getUserStatus = (user) => {
  if (!user) return '';
  
  // 判断用户准备状态
  if (props.readyUsers.includes(user.id) && !props.gameStarted) {
    return '已准备';
  }
  
  // 判断是否是当前发言者
  if (user.id === props.currentSpeakerId) {
    return '正在发言';
  }
  
  // 默认不显示状态
  return '';
};

// 获取角色显示文本
const getRoleDisplay = (role) => {
  if (!role) return '';
  
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

// 初始化store
const roomStore = useRoomStore();
const userStore = useUserStore();

// 添加计算属性来缓存角色可见性结果
const roleVisibilityMap = computed(() => {
  const result = {};
  props.users.forEach(user => {
    result[user.id] = calculateShouldShowRole(user.id);
  });
  return result;
});

// 内部方法计算角色可见性，不记录日志
const calculateShouldShowRole = (userId) => {
  const currentUserId = userStore.user?.id;
  
  // 查找用户对象
  const user = props.users.find(u => u.id === userId);
  
  // 游戏没有开始或者没有角色信息时不显示角色
  if (!props.gameStarted || !props.roles) {
    return false;
  }
  
  // 如果用户被淘汰，显示角色
  if (user && user.eliminated) {
    return true;
  }
  
  // 当前用户的角色
  const myRole = props.currentRole;
  
  // 目标用户的角色 - 对于自己，优先使用currentRole
  let targetRole;
  if (userId === currentUserId) {
    targetRole = props.currentRole;
  } else {
    targetRole = props.roles[userId];
  }
  
  // 如果目标用户没有角色，不显示
  if (!targetRole) {
    return false;
  }
  
  // 规则1：如果是自己，始终显示自己的角色
  if (userId === currentUserId) {
    return true;
  }
  
  // 规则2：如果目标用户是上帝，任何人都能看到
  if (targetRole === 'god') {
    return true;
  }
  
  // 规则3：如果当前用户是上帝，能看到所有人角色
  if (myRole === 'god') {
    return true;
  }
  
  // 规则4：如果当前用户是卧底，且目标也是卧底
  if (myRole === 'spy' && targetRole === 'spy') {
    return true;
  }
  
  // 默认不显示
  return false;
};

// 对外暴露的shouldShowRole方法，使用缓存结果
const shouldShowRole = (userId) => {
  // 仅在需要调试问题时才输出日志
  // console.log(`[UserList] shouldShowRole: userId=${userId}, currentUserId=${userStore.user?.id}`);
  
  // 如果当前用户是卧底，且被查询的用户ID在卧底队友列表中，显示其角色
  if (props.currentRole === 'spy' && props.spyTeammates && props.spyTeammates.includes(userId)) {
    return true;
  }
  
  return roleVisibilityMap.value[userId] || false;
};

// 获取角色的样式类
const getRoleClass = (userId) => {
  if (!props.roles) return '';
  
  // 对于自己，优先使用currentRole
  let role;
  if (userId === props.currentUserId) {
    role = props.currentRole;
  } else {
    role = props.roles[userId];
  }
  
  if (role === 'spy') return 'role-spy';
  if (role === 'civilian') return 'role-civilian';
  if (role === 'god') return 'role-god';
  
  return '';
};

// 获取角色的显示名称
const getRoleName = (userId) => {
  if (!props.roles) return '';
  
  // 对于自己，优先使用currentRole
  let role;
  if (userId === props.currentUserId) {
    role = props.currentRole;
  } else {
    role = props.roles[userId];
  }
  
  if (role === 'spy') return '卧底';
  if (role === 'civilian') return '平民';
  if (role === 'god') return '上帝';
  
  return '';
};

// 获取当前用户投票的目标玩家名称
const getVotedTargetName = () => {
  // 确保roomStore和votedPlayers存在
  if (!roomStore || !roomStore.votedPlayers) {
    return '未知玩家';
  }
  
  const targetId = roomStore.votedPlayers[props.currentUserId];
  if (!targetId) return '未知玩家';
  
  // 查找目标用户
  const targetUser = props.users.find(user => user.id === targetId);
  if (!targetUser) return '未知玩家';
  
  return getDisplayUsername(targetUser);
};

// 获取投票计数
const getVoteCount = (userId) => {
  // 确保roomStore已被导入并正确初始化
  const roomStore = useRoomStore();
  
  // 对voteCount进行调试输出
  if (roomStore.gamePhase === 'voting' && userId) {
    console.log(`[UserList] 获取玩家 ${userId} 的投票数：`, 
      roomStore.voteCount ? (roomStore.voteCount[userId] || 0) : 0,
      '完整投票数据:', roomStore.voteCount);
  }
  
  // 确保voteCount对象存在后再访问
  if (!roomStore.voteCount) {
    return 0;
  }
  
  // 正确获取数值格式的票数
  const votes = roomStore.voteCount[userId];
  return votes ? Number(votes) : 0;
};

// 获取投票用户信息
const getVotingUsers = () => {
  // 返回已投票的用户列表
  return roomStore.votedPlayers || {};
};

// 获取存活玩家数量
const getAlivePlayersCount = () => {
  const roomStore = useRoomStore();
  
  // 过滤掉已淘汰的玩家以及上帝角色
  const alivePlayers = props.users.filter(user => {
    // 排除已淘汰玩家
    if (user.eliminated) return false;
    
    // 排除上帝角色
    if (roomStore.roles && roomStore.roles[user.id] === 'god') return false;
    
    // 计入存活的平民和卧底
    return true;
  });
  
  console.log('[UserList] 存活可投票玩家数量:', alivePlayers.length, '，排除上帝后的玩家列表:', 
    alivePlayers.map(u => ({ id: u.id, username: u.username, role: roomStore.roles?.[u.id] || '未知' })));
  
  return alivePlayers.length;
};

// 检查玩家是否已被淘汰
const isPlayerEliminated = (userId) => {
  const user = props.users.find(u => u.id === userId);
  return user && user.eliminated;
};

// 添加计算属性检查当前用户是否已投票
const hasVoted = computed(() => {
  return roomStore && 
         roomStore.votedPlayers && 
         props.currentUserId && 
         roomStore.votedPlayers[props.currentUserId] !== undefined;
});

// 获取投票按钮的提示信息
const getVoteButtonTitle = () => {
  if (roomStore.gamePhase !== 'voting') {
    return '当前不是投票阶段';
  }
  
  if (hasVoted.value) {
    return '您已经投过票了';
  }
  
  if (!selectedUserId.value) {
    return '请先选择要投票的玩家';
  }
  
  return '点击确认投票';
};

// 获取投票者提示文本
const getVotersTooltip = (userId) => {
  const roomStore = useRoomStore();
  const voters = [];
  
  // 遍历所有投票记录，找出投给该玩家的所有人
  for (const [voterId, targetId] of Object.entries(roomStore.votedPlayers)) {
    if (targetId === userId) {
      const voter = props.users.find(u => u.id === voterId);
      if (voter) {
        voters.push(getDisplayUsername(voter));
      }
    }
  }
  
  if (voters.length === 0) {
    return "暂无人投票";
  }
  
  return `${voters.join(', ')} 投票给了该玩家`;
};

// 获取用户名
const getUsernameById = (userId) => {
  const user = props.users.find(u => u.id === userId);
  return user ? getDisplayUsername(user) : '未知用户';
};

// 记录投票按钮状态
const logVoteButtonStatus = () => {
  console.log('[UserList] 投票按钮状态:', {
    currentPhase: roomStore.gamePhase, 
    isVotingPhase: roomStore.gamePhase === 'voting',
    selectedUserId: selectedUserId.value,
    hasVoted: hasVoted.value,
    buttonDisabled: roomStore.gamePhase !== 'voting' || !selectedUserId.value || hasVoted.value
  });
};

// 添加对投票按钮的调试
const handleVoteClick = () => {
  console.log('[UserList] 投票按钮点击事件触发');
  console.log('[UserList] 当前游戏阶段:', roomStore.gamePhase);
  console.log('[UserList] 当前选中用户:', selectedUserId.value);
  console.log('[UserList] 用户是否已投票:', hasVoted.value);
  
  // 确保当前是投票阶段
  if (roomStore.gamePhase !== 'voting') {
    document.dispatchEvent(new CustomEvent('room-toast', { 
      detail: { type: 'warning', message: '当前不是投票阶段' } 
    }));
    return;
  }
  
  // 检查用户是否已经投票
  if (hasVoted.value) {
    document.dispatchEvent(new CustomEvent('room-toast', { 
      detail: { type: 'warning', message: '您已经投过票了，每轮只能投一次票' } 
    }));
    return;
  }
  
  // 检查确认投票是否可进行
  if (!selectedUserId.value) {
    // 显示通知
    document.dispatchEvent(new CustomEvent('room-toast', { 
      detail: { type: 'warning', message: '请先选择要投票的玩家' } 
    }));
    return;
  }
  
  // 选中玩家后触发投票事件
  console.log('[UserList] 触发投票事件，目标ID:', selectedUserId.value);
  emit('vote', selectedUserId.value);
};
</script>

<style scoped>
.users-container {
  width: 280px;
  background-color: white;
  border-left: 1px solid #e0e0e0;
  display: flex;
  flex-direction: column;
  position: relative;
  transition: width 0.3s ease;
  z-index: 1100; /* 修改为比倒计时遮罩更高的值，确保在遮罩之上 */
}

.users-container.resizing {
  transition: none;
}

.resize-handle {
  position: absolute;
  left: 0;
  top: 0;
  width: 5px;
  height: 100%;
  cursor: col-resize;
  background-color: transparent;
  z-index: 10;
}

.resize-handle:hover {
  background-color: rgba(24, 144, 255, 0.1);
}

/* 调整大小手柄的视觉提示可以按需添加 */
/* .resize-handle::before { ... } */
/* .resize-handle:hover::before { ... } */

.users-container.collapsed {
  width: 60px !important; /* 添加!important确保折叠时覆盖inline style */
}

.users-header {
  display: flex;
  justify-content: flex-start;
  align-items: center;
  padding: 15px;
  border-bottom: 1px solid #f0f0f0;
}

.users-header h3 {
  margin: 0;
  font-size: 1.1rem;
  font-weight: 500;
  white-space: nowrap; /* 防止折叠时文字换行 */
  overflow: hidden;
  flex: 1;
  margin-left: 10px;
}

.users-container.collapsed .users-header h3,
.users-container.collapsed .users-list,
.users-container.collapsed .secret-chat-area {
  display: none;
}

.collapse-btn {
  background: none;
  border: none;
  font-size: 16px;
  cursor: pointer;
  padding: 5px;
  border-radius: 4px;
  transition: opacity 0.15s ease;
  flex-shrink: 0;
}

.collapse-btn:hover {
  background-color: #f0f0f0;
}

.transitioning .collapse-btn {
  opacity: 0;
}

.users-list {
  flex: 1;
  overflow-y: auto;
  padding: 10px 15px;
}

.user-item {
  display: flex;
  align-items: center;
  padding: 8px 10px;
  border-bottom: 1px solid #f9f9f9;
  cursor: pointer;
  position: relative;
  transition: all 0.2s ease;
  border-radius: 4px;
  margin-bottom: 2px;
  background-color: white; /* 所有玩家默认白色背景 */
}

/* 正在发言的用户项样式 */
.user-item.speaking {
  border-left: 3px solid #ffc107;
  background-color: rgba(255, 193, 7, 0.05);
  /* 移除所有可能导致浮动的动画和变换 */
}

.user-item:hover {
  background-color: #f5f5f5;
}

/* 修改选中玩家样式，特别是在投票阶段时更明显 */
.user-item.selected {
  background-color: #e6f7ff;
  border-left: 3px solid #1890ff;
  box-shadow: 0 2px 8px rgba(24, 144, 255, 0.25);
  /* 移除上移效果，防止浮动动画 */
}

/* 在投票阶段，选中的玩家有更明显的高亮 */
.user-item.selected:hover {
  background-color: #bae7ff;
}

.user-avatar {
  position: relative;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  overflow: hidden;
  margin-right: 10px;
  flex-shrink: 0;
}

.user-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.host-badge {
  position: absolute;
  bottom: 0;
  right: 0;
  background-color: #ff4d4f;
  color: white;
  font-size: 0.6rem;
  padding: 1px 4px;
  border-radius: 3px;
}

.user-info {
  display: flex;
  flex-direction: column;
  flex: 1;
  position: relative;
  padding-bottom: 22px; /* 为淘汰状态腾出空间 */
  min-height: 40px;     /* 确保最小高度 */
  min-width: 0;         /* 允许内容溢出时正确应用ellipsis */
  margin-right: 8px;    /* 为状态牌留出空间 */
}

.user-name {
  font-size: 0.95rem;
  color: #333;
  white-space: nowrap; /* 防止名字过长换行 */
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
}

/* 发言指示器样式 */
.speaking-indicator {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-left: 10px;
  min-width: 60px;
}

/* 添加明显的倒计时数字样式 */
.countdown-number {
  font-size: 14px;
  font-weight: bold;
  color: #ff6b01;
  margin-bottom: 2px;
  background-color: #fff8e6;
  padding: 2px 8px;
  border-radius: 10px;
  border: 1px solid #ffc107;
  text-align: center;
}

/* 移除波形动画，不保留任何指示器 */
.speaking-animation {
  display: none; /* 完全隐藏波形动画 */
}

/* 移除动画效果 */
@keyframes sound-wave {
  0% { height: 5px; } /* 固定高度，实际上不会应用，因为元素被隐藏了 */
  100% { height: 5px; }
}

.countdown-wrapper {
  width: 60px;
  height: 6px;
  background-color: #f0f0f0;
  border-radius: 3px;
  overflow: hidden;
  position: relative;
  margin-top: 5px; /* 增加一点上边距，因为波形动画被移除了 */
}

.countdown-bar {
  height: 100%;
  background-color: #ffc107;
  border-radius: 3px;
  transition: width 1s linear;
}

.ready-badge {
  background-color: #52c41a;
  color: white;
  font-size: 0.7rem;
  padding: 1px 4px;
  border-radius: 3px;
  margin-left: 5px;
}

.user-divider {
  height: 1px;
  background-color: #e8e8e8;
  margin: 15px 0;
}

.ai-assistant .user-name {
  color: #1890ff;
}

/* 用户操作按钮样式 */
.user-actions {
  display: flex;
  flex-direction: column;
  background: white;
  border-radius: 6px;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.12);
  padding: 6px;
  position: absolute;
  left: 10px;
  top: 100%;
  transform: translateY(0);
  z-index: 5;
  animation: fadeIn 0.2s ease;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(-5%) scale(0.95); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

.action-btn {
  background: none;
  border: none;
  display: flex;
  align-items: center;
  padding: 8px 10px;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
  margin: 2px 0;
  white-space: nowrap;
  color: #333;
}

.action-btn:hover {
  background-color: #f0f0f0;
}

.action-icon {
  font-size: 16px;
  line-height: 1;
  margin-right: 8px;
  width: 20px;
  text-align: center;
}

.action-text {
  font-size: 14px;
}

.kick-btn {
  color: #ff4d4f;
}

.kick-btn:hover {
  background-color: #fff1f0;
}

.secret-chat-area {
  padding: 15px;
  display: flex;
  justify-content: center;
  position: relative;
  z-index: 1000;
}

.secret-chat-button, .ready-game-button {
  padding: 12px 0;
  width: 100%;
  border: none;
  border-radius: 6px;
  font-weight: 600;
  font-size: 16px;
  cursor: pointer;
  transition: all 0.3s;
  text-align: center;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.1);
  position: relative; /* 为按钮也添加相对定位 */
  z-index: 1000; /* 默认按钮在遮罩下方 */
}

.secret-chat-button {
  background-color: #ff4d4f;
  color: white;
}

.secret-chat-button:hover {
  background-color: #ff7875;
}

.ready-game-button {
  background-color: #28a745;
  color: white;
  margin: 0 auto;
  min-width: 260px;
  position: relative;
  z-index: 2000; /* 设置比遮罩层更高的值，确保按钮可见和可点击 */
}

.ready-game-button:hover {
  background-color: #218838;
  transform: translateY(-1px);
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
}

/* Ready indicator style */
.ready-badge {
  background-color: #52c41a; /* Green */
  color: white;
  font-size: 0.7rem;
  padding: 1px 5px;
  border-radius: 4px;
  margin-left: 6px;
  vertical-align: middle;
}

/* 角色徽章基础样式 */
.role-badge {
  font-size: 0.7rem;
  padding: 2px 6px;
  border-radius: 3px;
  margin-left: 5px;
  color: white;
  font-weight: bold;
}

/* 角色身份牌样式 */
.user-role {
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 0.8rem;
  margin-left: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  color: white;
  box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
}

.role-spy {
  background-color: #f5222d; /* 卧底使用红色 */
  border: 1px solid #cf1322;
}

.role-civilian {
  background-color: #1890ff; /* 平民使用蓝色 */
  border: 1px solid #096dd9;
}

.role-god {
  background-color: #faad14; /* 上帝使用金色 */
  border: 1px solid #d48806;
  box-shadow: 0 0 5px rgba(250, 173, 20, 0.5); /* 特殊发光效果 */
}

.role-name {
  white-space: nowrap;
}

.ai-player {
  /* 移除AI玩家的特殊背景和边框，保持与普通玩家一致 */
}

.ai-badge {
  position: absolute;
  bottom: 0;
  right: 0;
  background-color: #1890ff;
  color: white;
  font-size: 0.6rem;
  padding: 1px 4px;
  border-radius: 3px;
}

.debug-info {
  font-size: 10px;
  background-color: #f5f5f5;
  padding: 5px;
  margin: 5px;
  border: 1px solid #ddd;
  white-space: pre-wrap;
  overflow: auto;
  max-height: 200px;
}

.debug-user-info {
  font-size: 8px;
  color: #888;
  margin-bottom: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 按钮区域样式 */
.user-action-buttons {
  display: flex;
  justify-content: center;
  padding: 10px;
  gap: 10px;
}

.vote-button, .secret-chat-button {
  padding: 8px 16px;
  border-radius: 4px;
  border: none;
  cursor: pointer;
  font-weight: bold;
  transition: all 0.3s;
}

.vote-button {
  background-color: #ff4757;
  color: white;
}

.secret-chat-button {
  background-color: #722ed1;
  color: white;
}

.vote-button:hover, .secret-chat-button:hover {
  opacity: 0.85;
}

.vote-button:disabled, .secret-chat-button:disabled {
  background-color: #ccc;
  cursor: not-allowed;
}

.user-list:not(.collapsed) {
  min-width: 240px;
  width: 25%;
  max-width: 350px;
  resize: horizontal;
  overflow: auto;
}

/* 改进投票计数样式 */
.vote-count {
  background-color: #ddd;
  color: #777;
  border-radius: 12px;
  padding: 2px 8px;
  font-size: 0.8rem;
  font-weight: bold;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-left: auto;
  margin-right: 5px;
  transition: all 0.3s ease;
  border: 1px solid #ccc;
}

/* 有票数时的高亮样式 */
.vote-count.has-votes {
  background-color: #ff4757;
  color: white;
  border: 1px solid #ff2142;
  box-shadow: 0 2px 5px rgba(255, 71, 87, 0.3);
  animation: voteCountPulse 2s infinite;
}

@keyframes voteCountPulse {
  0% { transform: scale(1); }
  50% { transform: scale(1.05); }
  100% { transform: scale(1); }
}

.vote-number {
  font-size: 1rem;
  margin-right: 2px;
  font-weight: bold;
}

.voted-by-you {
  background-color: #2ed573;
  color: white;
  border-radius: 12px;
  padding: 2px 8px;
  font-size: 0.8rem;
  position: absolute;
  right: 10px;
  top: 10px;
  font-weight: bold;
  box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
  animation: fadeInBounce 0.5s ease-out;
}

@keyframes fadeInBounce {
  0% { transform: scale(0.8); opacity: 0; }
  50% { transform: scale(1.1); opacity: 0.9; }
  100% { transform: scale(1); opacity: 1; }
}

/* 用户投票状态样式 */
.user-voting-status {
  margin-top: 5px;
  font-size: 0.8rem;
  color: #666;
  background-color: #f8f8f8;
  padding: 3px 8px;
  border-radius: 10px;
  display: inline-flex;
  align-items: center;
  border: 1px dashed #ddd;
}

.voted-target {
  font-weight: bold;
  color: #ff4757;
  margin-left: 4px;
}

/* 投票按钮样式调整 */
.vote-button {
  background-color: #ff4757;
  color: white;
  border: none;
  border-radius: 4px;
  padding: 10px 20px;
  font-size: 1rem;
  font-weight: bold;
  cursor: pointer;
  transition: all 0.3s;
  margin-right: 8px;
  box-shadow: 0 2px 5px rgba(0, 0, 0, 0.2);
}

.vote-button:hover {
  background-color: #ff6b81;
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.3);
}

.vote-button:disabled {
  background-color: #b2bec3;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
  opacity: 0.7;
}

/* 添加动画效果到投票按钮，仅在投票阶段且选中玩家时显示 */
.vote-button:not(:disabled) {
  animation: pulse 1.5s infinite;
}

@keyframes pulse {
  0% { box-shadow: 0 0 0 0 rgba(255, 71, 87, 0.4); }
  70% { box-shadow: 0 0 0 10px rgba(255, 71, 87, 0); }
  100% { box-shadow: 0 0 0 0 rgba(255, 71, 87, 0); }
}

/* 当投票按钮禁用但游戏已开始时的样式提示 */
.vote-button:disabled:not([disabled="false"]) {
  position: relative;
  overflow: hidden;
}

.vote-button:disabled:not([disabled="false"])::after {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 3px;
  background: linear-gradient(90deg, transparent, rgba(255,255,255,0.5), transparent);
  animation: waiting-animation 2s infinite;
}

@keyframes waiting-animation {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(100%); }
}

/* 准备按钮样式 */
.ready-button-container {
  display: flex;
  justify-content: center;
  padding: 15px;
  border-top: 1px solid #f0f0f0;
}

.ready-button {
  padding: 10px 20px;
  border-radius: 4px;
  font-size: 1rem;
  font-weight: bold;
  cursor: pointer;
  transition: all 0.3s;
  border: none;
  background-color: #52c41a;
  color: white;
  width: 100%;
  max-width: 200px;
}

.ready-button:hover {
  background-color: #73d13d;
}

.ready-button.ready-active {
  background-color: #52c41a;
}

.ready-button.ready-active:hover {
  background-color: #73d13d;
}

.ready-mark {
  position: absolute;
  top: -2px;
  right: -2px;
  width: 16px;
  height: 16px;
  background-color: #52c41a;
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  font-weight: bold;
  border: 2px solid white;
}

/* 用户项内容容器 */
.user-item-content {
  display: flex;
  align-items: center;
  width: 100%;
  position: relative;
  flex-wrap: nowrap;
}

/* 用户状态牌样式 */
.user-status-badge {
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 0.8rem;
  margin-left: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  color: white;
  box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
}

/* 准备状态牌的样式 */
.ready-status {
  background-color: #52c41a; /* 使用绿色背景 */
  border: 1px solid #389e0d;
}

/* 投票统计面板样式 */
.vote-summary-panel {
  padding: 15px;
  background-color: white;
  border-radius: 4px;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
  margin-top: 10px;
}

.vote-summary-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.vote-summary-title {
  font-size: 1.2rem;
  font-weight: 500;
}

.vote-summary-count {
  font-size: 1rem;
  font-weight: bold;
  color: #ff4757;
}

.vote-summary-content {
  margin-bottom: 10px;
}

.vote-summary-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 5px;
}

.vote-summary-name {
  font-size: 0.9rem;
  font-weight: bold;
}

.vote-summary-votes {
  font-size: 0.8rem;
  color: #777;
}

.vote-summary-empty {
  text-align: center;
  color: #777;
}

/* 被淘汰的玩家样式 */
.user-item.eliminated {
  opacity: 0.7;
  background-color: #f1f1f1;
  border-left: 3px solid #999;
  cursor: default;
  position: relative;
}

/* 添加淘汰标志 */
.user-item.eliminated::after {
  content: "已淘汰";
  position: absolute;
  right: 10px;
  top: 50%;
  transform: translateY(-50%);
  color: #999;
  font-size: 0.8rem;
  background-color: #e0e0e0;
  padding: 2px 5px;
  border-radius: 3px;
}

/* 被淘汰玩家的角色显示 */
.user-role.eliminated {
  color: #f44336;
  font-weight: bold;
}

/* 被淘汰的头像样式 */
.user-avatar.eliminated img {
  filter: grayscale(100%) brightness(0.8); /* 头像变灰 */
}

/* 淘汰标记样式 */
.eliminated-mark {
  position: absolute;
  top: -2px;
  right: -2px;
  width: 16px;
  height: 16px;
  background-color: #ff4d4f;
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  font-weight: bold;
  border: 2px solid white;
  box-shadow: 0 0 5px rgba(0, 0, 0, 0.2);
}

/* 淘汰状态文本 */
.eliminated-status {
  position: absolute;
  bottom: 0;
  right: 0;
  background-color: rgba(255, 59, 48, 0.9);
  color: white;
  padding: 2px 5px;
  border-radius: 3px;
  font-size: 12px;
  font-weight: bold;
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 0 3px rgba(0, 0, 0, 0.5);
}

/* 已投票按钮样式 */
.vote-button.voted {
  background-color: #52c41a;
  opacity: 0.8;
  cursor: not-allowed;
}

.vote-button:hover, .secret-chat-button:hover {
  opacity: 0.85;
}

/* 确保没有其他样式使用speaking类的动画 */
@keyframes float-speaking {
  0% { transform: translateY(0); }
  50% { transform: translateY(0); }
  100% { transform: translateY(0); }
}

/* AI助理容器样式 */
.ai-assistant-container {
  padding: 10px 15px;
  margin-top: 5px;
  margin-bottom: 5px;
  position: relative;
}

.divider {
  height: 1px;
  background-color: #e8e8e8;
  width: 100%;
  margin-bottom: 10px;
}

.ai-assistant-item {
  display: flex;
  align-items: center;
  padding: 8px 10px;
  border-radius: 4px;
  transition: all 0.2s;
  background-color: rgba(245, 245, 245, 0.5);
  border: 1px solid #f0f0f0;
}

.ai-assistant-item:hover {
  background-color: rgba(240, 240, 240, 0.8);
}

.ai-assistant-avatar {
  position: relative;
  min-width: 40px;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  overflow: hidden;
  margin-right: 10px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  border: 2px solid #e8e8e8;
}

.ai-assistant-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.ai-assistant-tip {
  font-size: 0.75rem;
  color: #999;
  margin-top: 2px;
}
</style> 