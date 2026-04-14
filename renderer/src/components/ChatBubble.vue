<template>
  <div class="chat-bubble" :class="{ 'typing': chatStore.isTyping }">
    <div class="bubble-content">
      <span v-if="chatStore.isTyping" class="typing-indicator">
        <span></span>
        <span></span>
        <span></span>
      </span>
      <span v-else>{{ chatStore.currentMessage }}</span>
    </div>
    <div class="bubble-tail"></div>
  </div>
</template>

<script setup>
import { useChatStore } from '../stores/chat'

const chatStore = useChatStore()
</script>

<style scoped>
.chat-bubble {
  position: absolute;
  top: 4px;
  left: 50%;
  transform: translateX(-50%);
  max-width: 280px;
  min-width: 60px;
  z-index: 100;
  animation: bubbleIn 0.3s ease-out;
}

.bubble-content {
  background: rgba(255, 255, 255, 0.95);
  border-radius: 18px;
  padding: 12px 16px;
  font-size: 14px;
  color: #333;
  line-height: 1.5;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
  border: 1px solid rgba(0, 0, 0, 0.05);
  word-wrap: break-word;
}

.bubble-tail {
  position: absolute;
  bottom: -8px;
  left: 50%;
  transform: translateX(-50%);
  width: 0;
  height: 0;
  border-left: 10px solid transparent;
  border-right: 10px solid transparent;
  border-top: 10px solid rgba(255, 255, 255, 0.95);
}

/* 输入中动画 */
.typing-indicator {
  display: flex;
  gap: 4px;
  padding: 4px 8px;
}

.typing-indicator span {
  width: 8px;
  height: 8px;
  background: #999;
  border-radius: 50%;
  animation: typingBounce 1.4s infinite ease-in-out both;
}

.typing-indicator span:nth-child(1) {
  animation-delay: -0.32s;
}

.typing-indicator span:nth-child(2) {
  animation-delay: -0.16s;
}

@keyframes typingBounce {
  0%, 80%, 100% {
    transform: scale(0.6);
    opacity: 0.5;
  }
  40% {
    transform: scale(1);
    opacity: 1;
  }
}

@keyframes bubbleIn {
  from {
    opacity: 0;
    transform: translateX(-50%) translateY(10px) scale(0.9);
  }
  to {
    opacity: 1;
    transform: translateX(-50%) translateY(0) scale(1);
  }
}
</style>
