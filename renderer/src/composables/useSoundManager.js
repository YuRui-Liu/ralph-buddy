/**
 * useSoundManager
 * 统一管理音效播放。使用模块级缓存（Map），首次调用时懒加载 Audio 实例。
 *
 * 用法：
 *   const { playSound } = useSoundManager()
 *   playSound('bark_short')   // 播放 /sounds/bark_short.wav
 */

// 模块级缓存，所有 composable 实例共享同一批 Audio 对象
const audioCache = new Map()

function getAudio(name) {
  if (!audioCache.has(name)) {
    const audio = new Audio(`/sounds/${name}.wav`)
    audio.volume = 0.7
    audioCache.set(name, audio)
  }
  return audioCache.get(name)
}

export function useSoundManager() {
  /**
   * 播放指定音效。若上次同名音效仍在播放，先暂停再重播。
   * @param {string} name - 音效名称，对应 /sounds/{name}.wav
   */
  function playSound(name) {
    const audio = getAudio(name)
    if (!audio.paused) {
      audio.pause()
      audio.currentTime = 0
    }
    audio.play().catch(() => {
      // 忽略浏览器自动播放限制（用户未交互时可能被阻止）
    })
  }

  return { playSound }
}
