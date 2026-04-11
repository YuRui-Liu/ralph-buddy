<template>
  <div class="break-reminder-overlay">
    <div class="break-bubble">
      <div class="bubble-content">
        <p class="reminder-text">
          主人，你已经工作 45 分钟了，起来活动一下吧！
        </p>
        <div class="bubble-actions">
          <button class="btn-confirm" @click="onConfirm">好的去休息</button>
          <button class="btn-snooze" @click="onSnooze">再等 10 分钟</button>
        </div>
      </div>
      <div class="bubble-tail"></div>
    </div>
  </div>
</template>

<script setup>
import { inject } from 'vue'

// App.vue 通过 provide('breakReminder', { confirm, snooze }) 注入
const breakReminder = inject('breakReminder')

function onConfirm() {
  breakReminder.confirm()
}

function onSnooze() {
  breakReminder.snooze()
}
</script>

<style scoped>
.break-reminder-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 200;
  pointer-events: none;
}

.break-bubble {
  pointer-events: auto;
  position: relative;
  animation: bubbleIn 0.3s ease-out;
}

.bubble-content {
  background: rgba(255, 255, 255, 0.97);
  border-radius: 18px;
  padding: 16px 20px;
  max-width: 280px;
  font-size: 14px;
  color: #333;
  line-height: 1.6;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
  border: 1px solid rgba(0, 0, 0, 0.05);
}

.reminder-text {
  margin: 0 0 12px 0;
  text-align: center;
}

.bubble-actions {
  display: flex;
  gap: 8px;
  justify-content: center;
}

.btn-confirm,
.btn-snooze {
  padding: 6px 14px;
  border-radius: 12px;
  border: none;
  cursor: pointer;
  font-size: 13px;
  transition: opacity 0.15s;
}

.btn-confirm:hover,
.btn-snooze:hover {
  opacity: 0.8;
}

.btn-confirm {
  background: #4caf50;
  color: white;
}

.btn-snooze {
  background: #e0e0e0;
  color: #555;
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
  border-top: 10px solid rgba(255, 255, 255, 0.97);
}

@keyframes bubbleIn {
  from {
    opacity: 0;
    transform: translateY(10px) scale(0.9);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}
</style>
