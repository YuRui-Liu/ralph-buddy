/**
 * useSimpleVAD
 * 基于 AudioWorklet PCM 原始数据的语音活动检测器。
 *
 * 彻底绕过 AnalyserNode（在部分 Electron + Windows 环境下
 * AnalyserNode 的 getByteFrequencyData / getByteTimeDomainData 返回全零）。
 *
 * 方案：AudioWorklet 始终发送 PCM 帧 → 主线程直接计算 RMS 能量 → VAD 判定。
 *
 * @returns {{ start, stop, pause, resume, getStream }}
 */

export function useSimpleVAD(options = {}) {
  const {
    onSpeechStart   = () => {},
    onSpeechEnd     = async () => {},  // 接收 Blob (audio/wav)
    onVADMisfire    = () => {},

    // 能量阈值（基于 PCM Float32 RMS，范围 0-1，静音≈0-0.005，轻声≈0.01-0.03，正常≈0.03-0.15）
    energyThreshold  = 0.008,  // RMS 阈值，低于此值认为静音
    silenceDuration  = 3500,   // ms：静音持续多久触发 onSpeechEnd（3.5秒，留足思考停顿）
    minSpeechMs      = 300,    // ms：低于此值认为误触
    maxSpeechMs      = 60000,  // ms：最长录音（1分钟）

    // 自适应背景噪声
    adaptiveNoise    = true,
    noiseMargin      = 0.005,  // 在背景噪声上额外加的 margin
  } = options

  let audioContext   = null
  let source         = null
  let stream         = null
  let muteGain       = null
  let workletNode    = null
  let processor      = null   // ScriptProcessor fallback
  let vadTimer       = null   // VAD 判定定时器
  let silenceTimer   = null
  let speechStartMs  = 0

  let isSpeaking     = false
  let isRunning      = false
  let isPaused       = false
  let backgroundRMS  = 0
  let currentEnergy  = 0      // 最新一帧的 RMS

  // 录音缓冲区
  let recordedChunks = []
  // 诊断计数器
  let _diagCount     = 0
  // MediaRecorder 备用模式
  let _mediaRecorder = null

  // ────────── PCM 帧处理（每帧 128 样本，~375fps@48kHz） ──────────

  function _onPCMFrame(pcmFloat32) {
    if (!isRunning || isPaused) return

    // 计算 RMS
    let sum = 0
    for (let i = 0; i < pcmFloat32.length; i++) {
      sum += pcmFloat32[i] * pcmFloat32[i]
    }
    currentEnergy = Math.sqrt(sum / pcmFloat32.length)

    // 录音中：缓存 PCM
    if (isSpeaking) {
      recordedChunks.push(pcmFloat32)
    }
  }

  // ────────── VAD 判定（30ms 轮询） ──────────

  function _vadTick() {
    if (!isRunning || isPaused) return

    const energy = currentEnergy
    const thresh = _threshold()

    // 诊断日志：每 ~3 秒
    if (++_diagCount % 100 === 0) {
      console.log(`[VAD] energy=${energy.toFixed(4)} threshold=${thresh.toFixed(4)} bg=${backgroundRMS.toFixed(4)} speaking=${isSpeaking}`)
    }

    // 动态更新背景噪声（说话期间不更新）
    if (adaptiveNoise && !isSpeaking) {
      backgroundRMS = backgroundRMS * 0.95 + energy * 0.05
    }

    if (energy > thresh) {
      if (!isSpeaking) {
        _startSpeech()
      }
      if (silenceTimer) {
        clearTimeout(silenceTimer)
        silenceTimer = null
      }
    } else if (isSpeaking) {
      if (!silenceTimer) {
        silenceTimer = setTimeout(_endSpeech, silenceDuration)
      }
    }

    // 超长录音截断
    if (isSpeaking && speechStartMs && Date.now() - speechStartMs > maxSpeechMs) {
      _endSpeech()
    }
  }

  function _threshold() {
    return adaptiveNoise
      ? Math.max(energyThreshold, backgroundRMS + noiseMargin)
      : energyThreshold
  }

  // ────────── 启动 ──────────

  async function start() {
    if (isRunning) return
    isRunning = true

    // 列出可用麦克风
    const devices = await navigator.mediaDevices.enumerateDevices()
    const mics = devices.filter(d => d.kind === 'audioinput')
    console.log(`[VAD] 可用麦克风 (${mics.length}):`, mics.map(m => `${m.label || '(unnamed)'} [${m.deviceId.slice(0,8)}]`))

    // 尝试多种约束组合，直到获取到未静音的麦克风流
    // Intel 智音技术 (SST) 驱动在启用 echoCancellation/noiseSuppression 时
    // 会导致 track.muted=true（驱动内部音频管线冲突）
    const constraintSets = [
      // 1. 先尝试完全裸约束（绕过 SST 处理管线）
      { audio: { channelCount: 1, echoCancellation: false, noiseSuppression: false, autoGainControl: false } },
      // 2. 只开 autoGainControl
      { audio: { channelCount: 1, echoCancellation: false, noiseSuppression: false, autoGainControl: true } },
      // 3. 全开（原始方式，某些设备上正常）
      { audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true } },
      // 4. 最简约束
      { audio: true },
    ]

    // 对每种约束，还会尝试不同的 deviceId
    const deviceIds = ['default', ...mics.filter(m => m.deviceId !== 'default' && m.deviceId !== 'communications').map(m => m.deviceId)]

    stream = null
    let chosenLabel = ''
    for (const constraints of constraintSets) {
      for (const devId of deviceIds) {
        try {
          const c = typeof constraints.audio === 'object'
            ? { audio: { ...constraints.audio, deviceId: devId } }
            : constraints
          const testStream = await navigator.mediaDevices.getUserMedia(c)
          const testTrack = testStream.getAudioTracks()[0]
          console.log(`[VAD] 尝试: device=${devId.slice(0,8)}, constraints=${JSON.stringify(c.audio)}, muted=${testTrack.muted}`)

          if (!testTrack.muted) {
            stream = testStream
            chosenLabel = testTrack.label
            console.log(`[VAD] ✅ 找到可用麦克风: ${chosenLabel}`)
            break
          }

          // 有些设备初始 muted=true 但很快会 unmute，等 300ms
          const unmuted = await new Promise(resolve => {
            if (!testTrack.muted) { resolve(true); return }
            const timer = setTimeout(() => resolve(false), 300)
            testTrack.onunmute = () => { clearTimeout(timer); resolve(true) }
          })

          if (unmuted) {
            stream = testStream
            chosenLabel = testTrack.label
            console.log(`[VAD] ✅ 麦克风 unmute 成功: ${chosenLabel}`)
            break
          }

          // 不行，释放这个流
          testStream.getTracks().forEach(t => t.stop())
        } catch (e) {
          console.warn(`[VAD] 约束失败: ${e.message}`)
        }
      }
      if (stream) break
    }

    if (!stream) {
      // 最后兜底：无论 muted 与否都用
      console.warn('[VAD] ⚠️ 所有组合的 track 均为 muted，强制使用默认麦克风')
      stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    }

    const track = stream.getAudioTracks()[0]
    const settings = track.getSettings()
    console.log(`[VAD] 最终麦克风: ${track.label}`)
    console.log(`[VAD]   enabled=${track.enabled}, readyState=${track.readyState}, muted=${track.muted}`)
    console.log(`[VAD]   settings:`, JSON.stringify(settings))

    audioContext = new (window.AudioContext || window.webkitAudioContext)({
      sampleRate: settings.sampleRate || undefined,  // 尝试匹配设备采样率
    })
    if (audioContext.state === 'suspended') {
      console.log('[VAD] AudioContext suspended, resuming...')
      await audioContext.resume()
    }
    console.log(`[VAD] AudioContext state=${audioContext.state}, sampleRate=${audioContext.sampleRate}`)

    source = audioContext.createMediaStreamSource(stream)

    // 静音输出（保持音频图活跃）
    muteGain = audioContext.createGain()
    muteGain.gain.value = 0
    source.connect(muteGain)
    muteGain.connect(audioContext.destination)

    // ---- 方案 A: AudioWorklet ----
    let workletOk = false
    try {
      await audioContext.audioWorklet.addModule('/capture-processor.js')
      workletNode = new AudioWorkletNode(audioContext, 'capture-processor')
      source.connect(workletNode)
      workletNode.port.onmessage = (e) => _onPCMFrame(e.data)
      workletOk = true
      console.log('[VAD] AudioWorklet 已连接')
    } catch (err) {
      console.warn('[VAD] AudioWorklet 失败:', err.message)
    }

    // ---- 方案 B: ScriptProcessor（并行，双保险） ----
    processor = audioContext.createScriptProcessor(4096, 1, 1)
    source.connect(processor)
    processor.connect(muteGain)
    processor.onaudioprocess = (e) => {
      const input = e.inputBuffer.getChannelData(0)
      _onPCMFrame(new Float32Array(input))
    }
    console.log('[VAD] ScriptProcessor 已连接（并行监听）')

    // ---- 深层诊断：1秒后检查是否收到非零数据 ----
    const diagStart = Date.now()
    await new Promise(r => setTimeout(r, 1000))
    const trackStillMuted = stream.getAudioTracks()[0]?.muted
    console.log(`[VAD] ===== 1秒诊断 =====`)
    console.log(`[VAD] currentEnergy = ${currentEnergy.toFixed(6)}, track.muted = ${trackStillMuted}`)
    // 0.0001 以下视为浮点噪声，不是真实音频
    if (currentEnergy < 0.0001 || trackStillMuted) {
      console.error('[VAD] ⚠️ 麦克风未提供有效音频数据！')
      console.error('[VAD] 最可能的原因：Windows 隐私设置阻止了桌面应用访问麦克风')
      console.error('[VAD] 请检查：Windows 设置 > 隐私和安全性 > 麦克风')
      console.error('[VAD]   1. "麦克风访问" → 开启')
      console.error('[VAD]   2. "允许应用访问麦克风" → 开启')
      console.error('[VAD]   3. "允许桌面应用访问你的麦克风" → 开启 ← 关键！Electron 需要此项')

      // 最后手段：尝试用 MediaRecorder 捕获，测试是否能获得数据
      try {
        const testData = await _testMediaRecorder(stream)
        if (testData) {
          console.log('[VAD] ✅ MediaRecorder 能获取数据，切换到 MediaRecorder 模式')
          _startMediaRecorderMode(stream)
        } else {
          console.error('[VAD] ❌ MediaRecorder 也获取不到数据，麦克风可能被系统禁止')
        }
      } catch (e) {
        console.error('[VAD] MediaRecorder 测试失败:', e.message)
      }
    } else {
      console.log(`[VAD] ✅ 麦克风数据正常, energy=${currentEnergy.toFixed(6)}, muted=${trackStillMuted}`)
    }

    // 等 500ms 估算背景噪声
    if (adaptiveNoise) {
      await _estimateBackground()
    }

    // 启动 VAD 判定循环
    vadTimer = setInterval(_vadTick, 30)

    console.log(`[VAD] 启动完成, bg=${backgroundRMS.toFixed(4)}`)
  }

  // ────────── MediaRecorder 诊断 & 备用模式 ──────────

  function _testMediaRecorder(testStream) {
    return new Promise((resolve) => {
      try {
        const mr = new MediaRecorder(testStream)
        const chunks = []
        mr.ondataavailable = (e) => { if (e.data.size > 0) chunks.push(e.data) }
        mr.onstop = async () => {
          if (chunks.length === 0) { resolve(false); return }
          const blob = new Blob(chunks, { type: mr.mimeType })
          console.log(`[VAD] MediaRecorder 测试: ${blob.size} bytes, type=${mr.mimeType}`)
          // 尝试解码检查是否有声音
          try {
            const buf = await blob.arrayBuffer()
            const ac = new (window.AudioContext || window.webkitAudioContext)()
            const decoded = await ac.decodeAudioData(buf)
            const pcm = decoded.getChannelData(0)
            let peak = 0
            for (let i = 0; i < pcm.length; i++) {
              const a = Math.abs(pcm[i])
              if (a > peak) peak = a
            }
            ac.close()
            console.log(`[VAD] MediaRecorder 解码: ${pcm.length} samples, peak=${peak.toFixed(6)}`)
            resolve(peak > 0.0001)
          } catch (e) {
            // 解码失败但有数据 = 至少能录音
            console.log(`[VAD] MediaRecorder 解码失败但有 ${blob.size} bytes 数据`)
            resolve(blob.size > 1000)
          }
        }
        mr.start()
        setTimeout(() => { if (mr.state === 'recording') mr.stop() }, 1000)
      } catch (e) {
        resolve(false)
      }
    })
  }

  // MediaRecorder 备用模式：用 timeslice 分片录音，解码 PCM 计算能量
  function _startMediaRecorderMode(mrStream) {
    console.log('[VAD] 切换到 MediaRecorder 备用模式')
    // 断开不工作的 Web Audio 路径
    if (workletNode) { workletNode.disconnect(); workletNode = null }
    if (processor)   { processor.disconnect();   processor = null }

    const mr = new MediaRecorder(mrStream)
    // 存为实例变量以便 stop 时清理
    _mediaRecorder = mr

    mr.ondataavailable = async (e) => {
      if (e.data.size === 0) return
      try {
        const buf = await e.data.arrayBuffer()
        const tempCtx = new (window.AudioContext || window.webkitAudioContext)()
        const decoded = await tempCtx.decodeAudioData(buf)
        const pcm = decoded.getChannelData(0)
        tempCtx.close()
        _onPCMFrame(pcm)
      } catch (err) {
        // 分片太小可能解码失败，忽略
      }
    }
    mr.start(200) // 每 200ms 一个分片
  }

  // ────────── 背景噪声估算 ──────────

  function _estimateBackground() {
    return new Promise(resolve => {
      const samples = []
      const timer = setInterval(() => {
        samples.push(currentEnergy)
        if (samples.length >= 17) {  // ~500ms
          clearInterval(timer)
          backgroundRMS = samples.reduce((a, b) => a + b, 0) / samples.length
          console.log(`[VAD] 背景噪声基线: ${backgroundRMS.toFixed(4)}`)
          resolve()
        }
      }, 30)
    })
  }

  // ────────── 录音控制 ──────────

  function _startSpeech() {
    isSpeaking    = true
    speechStartMs = Date.now()
    recordedChunks = []
    onSpeechStart()
  }

  function _endSpeech() {
    if (!isSpeaking) return
    isSpeaking = false
    if (silenceTimer) { clearTimeout(silenceTimer); silenceTimer = null }

    const duration = Date.now() - speechStartMs
    if (duration < minSpeechMs) {
      recordedChunks = []
      onVADMisfire()
      return
    }

    const sampleRate = audioContext ? audioContext.sampleRate : 48000
    const blob = _buildWavBlob(recordedChunks, sampleRate)
    recordedChunks = []
    console.log(`[VAD] 语音结束: ${duration}ms, WAV ${blob.size} bytes, sr=${sampleRate}`)
    onSpeechEnd(blob)
  }

  // ────────── WAV 编码 ──────────

  function _buildWavBlob(chunks, sampleRate) {
    const totalLen = chunks.reduce((s, c) => s + c.length, 0)
    const merged = new Float32Array(totalLen)
    let off = 0
    for (const c of chunks) { merged.set(c, off); off += c.length }

    // 诊断
    let sum = 0; let peak = 0
    for (let i = 0; i < merged.length; i++) {
      sum += merged[i] * merged[i]
      const a = Math.abs(merged[i])
      if (a > peak) peak = a
    }
    const rms = Math.sqrt(sum / (merged.length || 1))
    console.log(`[VAD] PCM 诊断: ${merged.length} samples, RMS=${rms.toFixed(6)}, peak=${peak.toFixed(6)}`)

    const numSamples = merged.length
    const wavBuf = new ArrayBuffer(44 + numSamples * 2)
    const v = new DataView(wavBuf)
    const w = (o, s) => { for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i)) }

    w(0, 'RIFF')
    v.setUint32(4, 36 + numSamples * 2, true)
    w(8, 'WAVE')
    w(12, 'fmt ')
    v.setUint32(16, 16, true)
    v.setUint16(20, 1, true)
    v.setUint16(22, 1, true)
    v.setUint32(24, sampleRate, true)
    v.setUint32(28, sampleRate * 2, true)
    v.setUint16(32, 2, true)
    v.setUint16(34, 16, true)
    w(36, 'data')
    v.setUint32(40, numSamples * 2, true)

    for (let i = 0; i < numSamples; i++) {
      const s = Math.max(-1, Math.min(1, merged[i]))
      v.setInt16(44 + i * 2, s < 0 ? s * 0x8000 : s * 0x7FFF, true)
    }

    return new Blob([wavBuf], { type: 'audio/wav' })
  }

  // ────────── 暂停 / 恢复 ──────────

  function pause() {
    if (!isRunning || isPaused) return
    isPaused = true
    if (isSpeaking) _endSpeech()
    if (silenceTimer) { clearTimeout(silenceTimer); silenceTimer = null }
  }

  async function resume() {
    if (!isRunning || !isPaused) return
    isPaused = false
    if (adaptiveNoise) {
      await _estimateBackground()
    }
  }

  // ────────── 停止 ──────────

  function stop() {
    isRunning = false
    if (vadTimer)     { clearInterval(vadTimer);     vadTimer     = null }
    if (silenceTimer) { clearTimeout(silenceTimer);   silenceTimer = null }
    if (isSpeaking) _endSpeech()
    if (_mediaRecorder && _mediaRecorder.state === 'recording') {
      _mediaRecorder.stop(); _mediaRecorder = null
    }
    if (workletNode) { workletNode.disconnect();      workletNode  = null }
    if (processor)   { processor.disconnect();        processor    = null }
    if (muteGain)    { muteGain.disconnect();         muteGain     = null }
    if (source)      { source.disconnect();           source       = null }
    if (audioContext) { audioContext.close();          audioContext  = null }
    if (stream)      { stream.getTracks().forEach(t => t.stop()); stream = null }
  }

  function getStream() { return stream }

  return { start, stop, pause, resume, getStream }
}
