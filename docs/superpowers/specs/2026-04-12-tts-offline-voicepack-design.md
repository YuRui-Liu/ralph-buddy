# TTS 离线语音包架构设计

**日期**：2026-04-12  
**状态**：已确认  
**关联文档**：PRD.md, ARCHITECTURE.md  

---

## 背景与问题

现有 `GptSoVITSEngine` 通过启动 `tools/GPT-SoVITS/api_v2.py` 子进程、HTTP 调用的方式进行语音合成，存在以下问题：

- 启动延迟约 60s，首次合成需等待子进程就绪
- 额外进程管理开销（端口占用、进程监控、异常退出处理）
- 固定音效（叫声、情绪响应）每次都走实时推理，浪费算力
- 无缓存机制，相同文本重复合成

目标：**去掉子进程依赖，固定音效预合成，LLM 回复内嵌推理 + 缓存，Edge TTS 兜底。**

---

## 整体架构

```
synthesize(text, hint)
        │
        ├─ hint 指定 clip（预合成音效）→ ClipsPlayer     0ms
        ├─ text 命中磁盘缓存            → TTSCache       ~5ms
        ├─ EmbeddedTTSEngine 已就绪     → 推理 + 写缓存  ~2-5s
        └─ 兜底                         → EdgeTTSEngine  ~1-2s
```

外部调用方（FastAPI）只与 `TTSRouter` 交互，三层引擎完全透明。

---

## 第一节：语音包格式

语音包为**自包含目录**，可整目录打包为 `.zip` 分发。

```
voices/lafu-clone/
├── config.json              # 元数据 + 推理参数
├── models/
│   ├── gpt.ckpt
│   └── sovits.pth
├── reference/
│   └── ref.wav              # 参考音频（3-10s）
└── clips/                   # 预合成静态音效
    ├── greetings/
    │   ├── morning.wav
    │   └── return.wav
    ├── emotions/
    │   ├── happy_01.wav
    │   ├── sad_01.wav
    │   └── excited_01.wav
    └── barks/
        ├── bark_short.wav
        └── bark_long.wav
```

### config.json 结构

```json
{
  "id": "lafu-clone",
  "name": "来福克隆音色",
  "type": "gptsovits-v2",
  "models": {
    "gpt": "models/gpt.ckpt",
    "sovits": "models/sovits.pth"
  },
  "reference": {
    "audio": "reference/ref.wav",
    "text": "汪汪汪",
    "lang": "zh"
  },
  "clips": {
    "greetings": [
      "clips/greetings/morning.wav",
      "clips/greetings/return.wav"
    ],
    "emotions": {
      "happy":   ["clips/emotions/happy_01.wav"],
      "sad":     ["clips/emotions/sad_01.wav"],
      "excited": ["clips/emotions/excited_01.wav"]
    },
    "barks": {
      "short": "clips/barks/bark_short.wav",
      "long":  "clips/barks/bark_long.wav"
    }
  },
  "inference": {
    "top_k": 20,
    "top_p": 0.85,
    "temperature": 0.6,
    "speed": 1.0
  }
}
```

**设计约束：**
- `clips/` 仅存固定音效，LLM 回复不打入包内
- 保持与现有 `VoiceManager` 的 `gpt-sovits` 类型字段兼容

---

## 第二节：离线预合成工具链

新增 `python-service/tools/prebake.py`，用 GPT-SoVITS 批量生成 `clips/` 目录。此工具仅在**制作语音包时**离线运行，不参与应用运行时。

### 工作流

```
phrase_list.json + config.json
        │
        ▼
    prebake.py CLI
        │
   调用 GPT-SoVITS 推理
        │
   去重 + 质检（静音/时长检测）
        │
   写入 clips/ + 更新 config.json
```

### 短语表格式 `phrase_list.json`

```json
{
  "greetings": [
    { "file": "morning.wav", "text": "主人早上好！" },
    { "file": "return.wav",  "text": "你回来啦！" }
  ],
  "emotions": {
    "happy":   [{ "file": "happy_01.wav",   "text": "太棒了！" }],
    "sad":     [{ "file": "sad_01.wav",     "text": "呜呜..." }],
    "excited": [{ "file": "excited_01.wav", "text": "冲！" }]
  },
  "barks": [
    { "file": "bark_short.wav", "text": "汪！" },
    { "file": "bark_long.wav",  "text": "汪汪汪汪！" }
  ]
}
```

### CLI 用法

```bash
# 批量预合成（跳过已存在文件）
python tools/prebake.py \
  --voice-dir voices/lafu-clone \
  --phrases   phrase_list.json \
  --skip-existing

# 仅重新合成指定分组
python tools/prebake.py \
  --voice-dir voices/lafu-clone \
  --phrases   phrase_list.json \
  --group emotions
```

### 内置质检

| 条件 | 处理 |
|---|---|
| 音频时长 < 0.3s | 警告并跳过 |
| 静音占比 > 80% | 标记为疑似异常 |
| 合成异常 | 写入 `prebake_errors.json` |

---

## 第三节：内嵌推理引擎

`EmbeddedTTSEngine` 替换 `GptSoVITSEngine`，直接 import GPT-SoVITS 推理模块，无子进程、无 HTTP。

```python
class EmbeddedTTSEngine:
    def __init__(self, voice_dir: str):
        self._ready = False
        self._lock = asyncio.Lock()
        # 从 config.json 读取模型路径、推理参数

    async def warmup(self):
        """后台线程加载模型，不阻塞主进程"""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._load_models)

    def _load_models(self):
        from GPTSoVITS.inference_webui import get_tts_wav
        self._infer_fn = get_tts_wav
        self._ready = True

    async def synthesize(self, text: str) -> bytes:
        if not self._ready:
            raise RuntimeError("模型尚未就绪")
        async with self._lock:          # 推理非线程安全，串行执行
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._run_inference, text)
```

**关键点：**
- `warmup()` 在 FastAPI `lifespan` 启动事件中调用，后台异步执行
- `asyncio.Lock` 保证同一时刻只有一个推理任务，其余排队
- `run_in_executor` 将 CPU 密集推理放入线程池，不阻塞事件循环

---

## 第四节：TTS 路由器 + 缓存

### TTSRouter

```python
router = TTSRouter(
    clips=ClipsPlayer(voice_dir),
    inference=EmbeddedTTSEngine(voice_dir),
    fallback=EdgeTTSEngine(),
    cache=TTSCache(limit_mb=500),
)

# 调用示例
await router.synthesize("", hint="barks.short")          # 播放预合成
await router.synthesize("", hint="emotions.happy")       # 播放预合成
await router.synthesize("今天天气真好！", hint="llm")     # 推理 + 缓存
```

### 磁盘缓存

```
python-service/cache/tts/
├── index.json          # { "sha256前8位(text+voice_id)": "filename.wav" }
├── a3f2c1.wav
└── b8e9d4.wav
```

- **Key**：`sha256(text + voice_id)` 前8位
- **上限**：500MB（`config.json` 可配置）
- **淘汰策略**：LRU
- **范围**：仅缓存 LLM 推理结果，不缓存 clip

---

## 第五节：启动与预热流程

```
t=0s   Electron 启动 → 渲染宠物动画
t=0s   FastAPI 启动
         ├─ ClipsPlayer 就绪（WAV 直接可读）
         └─ EdgeTTSEngine 就绪（在线兜底）
         └─ 后台：EmbeddedTTSEngine.warmup() 开始

t=~15s 模型加载完成 → EmbeddedTTSEngine._ready = True
         └─ 前端"语音加载中"提示消失，克隆音色全面可用
```

### 前端状态机

```
LOADING ──（就绪）──► READY
   │                    │
   ▼                    ▼
Edge TTS 兜底       克隆音色合成
```

### 状态接口

```
GET /api/tts/status
→ { "ready": false, "message": "加载模型中..." }
→ { "ready": true }
```

---

## 改动范围

| 文件 | 改动类型 | 说明 |
|---|---|---|
| `tts/embedded_engine.py` | 新增 | 替代 `gpt_sovits_engine.py` |
| `tts/clips_player.py` | 新增 | 播放预合成 clip |
| `tts/router.py` | 新增 | TTSRouter 调度逻辑 |
| `tts/cache.py` | 新增 | 磁盘缓存模块 |
| `tts/voice_manager.py` | 修改 | `get_manager()` 返回 TTSRouter |
| `tools/prebake.py` | 新增 | 离线预合成 CLI |
| `main.py` | 修改 | 启动 warmup，暴露 `/api/tts/status` |
| `tts/gpt_sovits_engine.py` | 废弃 | 保留至迁移完成后删除 |

**不需要改动：** `edge_engine.py`、`audio_processor.py`、Electron/前端 IPC 层。

---

## 不在本次范围内

- GPT-SoVITS 模型训练流程（现有 `docs/0409-2114-M2声音克隆指南.md` 已覆盖）
- 前端语音包管理 UI
- 多语音包热切换
