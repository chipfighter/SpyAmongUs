<template>
  <div 
    v-if="show" 
    class="floating-ball" 
    :style="position" 
    @mousedown="handleMouseDown"
    @click.stop="handleClick" 
    @dblclick.stop 
  >
    <div class="ball-content" :title="roomName">
      {{ roomName }}
    </div>
  </div>
</template>

<script setup>
import { defineProps, defineEmits, ref } from 'vue';

defineProps({
  show: {
    type: Boolean,
    required: true,
    default: false
  },
  roomName: {
    type: String,
    required: true,
    default: ''
  },
  position: {
    type: Object,
    required: true,
    default: () => ({ top: '100px', left: '20px' })
  }
});

const emit = defineEmits(['start-drag', 'clicked']);

const isDraggingCheck = ref(false);
const startPos = ref({ x: 0, y: 0 });

const handleMouseDown = (event) => {
  // Prevent browser default drag behavior
  event.preventDefault();
  isDraggingCheck.value = false; // Reset drag check flag
  startPos.value = { x: event.clientX, y: event.clientY };
  emit('start-drag', event); // Pass the original event to parent

  // Add a temporary listener to check if it's a drag or click
  const checkMove = (moveEvent) => {
    const deltaX = Math.abs(moveEvent.clientX - startPos.value.x);
    const deltaY = Math.abs(moveEvent.clientY - startPos.value.y);
    if (deltaX > 3 || deltaY > 3) { // Threshold to consider it a drag
      isDraggingCheck.value = true;
    }
  };
  
  const handleMouseUpGlobal = () => {
    document.removeEventListener('mousemove', checkMove);
    document.removeEventListener('mouseup', handleMouseUpGlobal);
    // If mouseup happens and isDraggingCheck is still false, it was likely a click
    // The handleClick method will handle emitting 'clicked'
  };

  document.addEventListener('mousemove', checkMove);
  document.addEventListener('mouseup', handleMouseUpGlobal);
};

const handleClick = (event) => {
    // Only emit 'clicked' if it wasn't considered a drag during mouse down/move/up cycle
    if (!isDraggingCheck.value) {
        emit('clicked', event);
    }
    // Reset flag after click check is done
    isDraggingCheck.value = false; 
};

</script>

<style scoped>
.floating-ball {
  position: fixed; /* Changed from absolute for simplicity if parent isn't relative */
  width: 60px;
  height: 60px;
  background-color: #1890ff;
  border-radius: 50%;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
  display: flex;
  justify-content: center;
  align-items: center;
  cursor: grab; /* Indicate draggability */
  z-index: 1000;
  user-select: none;
  transition: background-color 0.2s; /* Smooth hover effect */
}

.floating-ball:active {
    cursor: grabbing;
    background-color: #40a9ff; /* Slightly lighter when grabbed */
}

.ball-content {
  color: white;
  font-size: 12px;
  text-align: center;
  max-width: 50px; /* Ensure text fits */
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  pointer-events: none; /* Prevent text selection during drag */
}
</style> 