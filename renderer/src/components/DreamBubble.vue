<template>
  <Transition name="dream-fade">
    <div v-if="visible" class="dream-bubble">
      <div class="dream-cloud">
        <img
          v-if="imageSrc"
          :src="imageSrc"
          class="dream-image"
          alt="梦境"
        />
        <p class="dream-text">来福梦到了...{{ text }}</p>
      </div>
      <div class="cloud-tail"></div>
    </div>
  </Transition>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  text: { type: String, default: '' },
  imageSrc: { type: String, default: null },
  duration: { type: Number, default: 8000 },
})

const emit = defineEmits(['dismiss'])

const visible = ref(true)
let dismissTimer = null

onMounted(() => {
  dismissTimer = setTimeout(() => {
    visible.value = false
    setTimeout(() => emit('dismiss'), 1000)
  }, props.duration)
})

onUnmounted(() => {
  if (dismissTimer) clearTimeout(dismissTimer)
})
</script>

<style scoped>
.dream-bubble {
  position: fixed;
  top: 20px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 500;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.dream-cloud {
  background: linear-gradient(135deg, #e8d5f5 0%, #c5cae9 100%);
  border-radius: 24px;
  padding: 16px;
  max-width: 240px;
  box-shadow:
    0 8px 32px rgba(100, 80, 160, 0.25),
    inset 0 1px 0 rgba(255, 255, 255, 0.4);
  text-align: center;
}

.dream-image {
  width: 100%;
  max-width: 200px;
  max-height: 200px;
  border-radius: 16px;
  object-fit: cover;
  margin-bottom: 10px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}

.dream-text {
  margin: 0;
  font-size: 13px;
  line-height: 1.6;
  color: #4a3f6b;
}

.cloud-tail {
  width: 20px;
  height: 20px;
  background: #d5c8e8;
  border-radius: 50%;
  margin-top: -4px;
  margin-left: 30px;
  box-shadow: 0 2px 6px rgba(100, 80, 160, 0.15);
}

.cloud-tail::after {
  content: '';
  display: block;
  width: 12px;
  height: 12px;
  background: #d5c8e8;
  border-radius: 50%;
  position: relative;
  top: 12px;
  left: 10px;
}

.dream-fade-enter-active {
  transition: opacity 0.5s ease-in, transform 0.5s ease-in;
}

.dream-fade-leave-active {
  transition: opacity 1s ease-out, transform 1s ease-out;
}

.dream-fade-enter-from {
  opacity: 0;
  transform: translateX(-50%) translateY(-10px);
}

.dream-fade-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(-10px);
}
</style>
