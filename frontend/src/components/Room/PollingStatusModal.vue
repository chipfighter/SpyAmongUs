<template>
  <div v-if="isOpen" class="modal-overlay" @click.self="closeModal"> <!-- @click.self allows closing by clicking overlay -->
    <div class="modal-content polling-status-modal">
      <p>{{ message }}</p>
      <!-- Optional close button -->
      <!-- <button @click="closeModal">关闭</button> -->
    </div>
  </div>
</template>

<script setup>
import { defineProps, defineEmits } from 'vue';

const props = defineProps({
  isOpen: {
    type: Boolean,
    required: true
  },
  message: {
    type: String,
    required: true
  }
});

const emit = defineEmits(['close']);

const closeModal = () => {
  emit('close'); // Emit close event for parent component to handle
};
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
}

.modal-content {
  background-color: white;
  padding: 20px 30px;
  border-radius: 8px;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
  text-align: center;
  /* Prevent closing when clicking inside the modal content */
  pointer-events: auto;
}

.polling-status-modal p {
  margin: 0;
  font-size: 1.1em;
  color: #333; /* Example text color */
}
</style> 