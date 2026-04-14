# 来福情绪识别系统 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 来福通过摄像头"偷偷观察"主人，本地模型快速识别表情 + 视觉 LLM 深度理解，分层反应（动作 + 主动对话）。

**Architecture:** 前端 `useEmotionObserver` composable 管理摄像头截帧和调度（定时/事件/手动三触发），后端 `EmotionDetector` 两层检测（DeepFace 快速 → LLM 深度），petStore 接收结果驱动行为脚本和对话注入。

**Tech Stack:** DeepFace (Python, fer2013), OpenAI Vision API (深度分析), Vue 3 composable, getUserMedia, Canvas 截帧

---

## File Structure

### New Files
| File | Responsibility |
|------|---------------|
| `python-service/emotion/__init__.py` | Package init |
| `python-service/emotion/detector.py` | EmotionDetector: DeepFace 封装 + LLM 深度分析 + 变化判断 |
| `renderer/src/composables/useEmotionObserver.js` | 摄像头管理、截帧、调度（定时/事件/手动）、结果分发 |
| `python-service/tests/test_emotion.py` | EmotionDetector 单元测试 |

### Modified Files
| File | Changes |
|------|---------|
| `python-service/requirements.txt` | 添加 `deepface` 依赖 |
| `python-service/main.py` | 新增 `POST /api/emotion` 端点 + lifespan 初始化 |
| `python-service/agent/dog_agent.py` | 新增 `owner_emotion_context` 属性 + system prompt 注入 |
| `renderer/src/stores/pet.js` | 新增 `emotionObserver` 状态块 |
| `renderer/src/stores/settings.js` | 新增 `emotionEnabled` / `emotionInterval` + 持久化 |
| `renderer/src/composables/useBehaviorSequencer.js` | 新增 `peek_observe` + 4 个情绪反应脚本 |
| `renderer/src/components/SettingsPanel.vue` | 情绪观察设置区域 + 引导弹窗 |
| `renderer/src/App.vue` | 挂载 `useEmotionObserver` |

---

### Task 1: EmotionDetector — Layer 1 本地检测

**Files:**
- Create: `python-service/emotion/__init__.py`
- Create: `python-service/emotion/detector.py`
- Create: `python-service/tests/test_emotion.py`
- Modify: `python-service/requirements.txt`

- [ ] **Step 1: 添加 deepface 依赖**

在 `python-service/requirements.txt` 末尾追加：

```
deepface>=0.0.89
tf-keras>=2.15.0
```

- [ ] **Step 2: 创建 emotion 包初始化文件**

创建 `python-service/emotion/__init__.py`：

```python
```

(空文件，仅作为包标记)

- [ ] **Step 3: 写 Layer 1 检测的 failing test**

创建 `python-service/tests/test_emotion.py`：

```python
import pytest
import asyncio
import numpy as np
from unittest.mock import patch, MagicMock
from emotion.detector import EmotionDetector


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


@pytest.fixture
def detector():
    return EmotionDetector(deep_llm_call=None)


# ── Layer 1: 本地检测 ─────────────────────────────

def test_detect_returns_result_with_face(detector):
    """正常图片应返回 has_face=True 和情绪分类"""
    # 创建一张 100x100 的随机图像 JPEG
    from io import BytesIO
    from PIL import Image
    img = Image.fromarray(np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8))
    buf = BytesIO()
    img.save(buf, format="JPEG")
    image_bytes = buf.getvalue()

    # Mock DeepFace.analyze 返回一个正常结果
    mock_result = [{
        "dominant_emotion": "happy",
        "emotion": {
            "happy": 85.0, "sad": 2.0, "angry": 1.0,
            "surprise": 5.0, "neutral": 5.0, "fear": 1.0, "disgust": 1.0
        }
    }]
    with patch("emotion.detector.DeepFace") as mock_df:
        mock_df.analyze.return_value = mock_result
        result = run(detector.detect(image_bytes))

    assert result["has_face"] is True
    assert result["local"]["emotion"] == "happy"
    assert result["local"]["confidence"] == pytest.approx(0.85, abs=0.01)
    assert "happy" in result["local"]["all_scores"]


def test_detect_no_face(detector):
    """无人脸时返回 has_face=False"""
    from io import BytesIO
    from PIL import Image
    img = Image.fromarray(np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8))
    buf = BytesIO()
    img.save(buf, format="JPEG")
    image_bytes = buf.getvalue()

    with patch("emotion.detector.DeepFace") as mock_df:
        mock_df.analyze.side_effect = ValueError("Face could not be detected")
        result = run(detector.detect(image_bytes))

    assert result["has_face"] is False
    assert result["local"] is None


def test_detect_tracks_change(detector):
    """连续检测时 changed 字段应反映情绪变化"""
    mock_happy = [{"dominant_emotion": "happy",
                   "emotion": {"happy": 90.0, "sad": 2.0, "angry": 1.0,
                               "surprise": 2.0, "neutral": 3.0, "fear": 1.0, "disgust": 1.0}}]
    mock_sad = [{"dominant_emotion": "sad",
                 "emotion": {"happy": 5.0, "sad": 80.0, "angry": 3.0,
                             "surprise": 2.0, "neutral": 8.0, "fear": 1.0, "disgust": 1.0}}]

    with patch("emotion.detector.DeepFace") as mock_df:
        mock_df.analyze.return_value = mock_happy
        r1 = run(detector.detect(b"fake"))

        mock_df.analyze.return_value = mock_happy
        r2 = run(detector.detect(b"fake"))

        mock_df.analyze.return_value = mock_sad
        r3 = run(detector.detect(b"fake"))

    assert r1["changed"] is True   # 首次检测，与 None 比较 → changed
    assert r2["changed"] is False  # happy → happy → 无变化
    assert r3["changed"] is True   # happy → sad → 有变化
```

- [ ] **Step 4: 运行测试，确认失败**

Run: `cd E:/Proj/pet_buddy/python-service && python -m pytest tests/test_emotion.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'emotion.detector'`

- [ ] **Step 5: 实现 EmotionDetector Layer 1**

创建 `python-service/emotion/detector.py`：

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EmotionDetector — 混合情绪检测器
Layer 1: DeepFace 本地快速检测
Layer 2: 视觉 LLM 深度分析（由 should_trigger_deep 判断是否升级）
"""

import io
import time
from typing import Optional, Callable, Awaitable

# 延迟导入 DeepFace（首次调用时加载模型）
DeepFace = None

NEGATIVE_EMOTIONS = {"sad", "angry", "fear", "disgust"}
DEEP_COOLDOWN_SEC = 180  # 深度分析冷却：3 分钟


def _ensure_deepface():
    global DeepFace
    if DeepFace is None:
        from deepface import DeepFace as _DF
        DeepFace = _DF


class EmotionDetector:

    def __init__(self, deep_llm_call: Optional[Callable] = None):
        """
        Args:
            deep_llm_call: async (image_bytes, local_emotion) -> DeepResult dict
                           如果为 None 则禁用深度分析
        """
        self._deep_llm_call = deep_llm_call
        self._last_emotion: Optional[str] = None
        self._consecutive_neg: int = 0
        self._last_deep_time: float = 0

    # ── Layer 1: 本地快速检测 ─────────────────────────

    async def detect(self, image_bytes: bytes) -> dict:
        """
        Layer 1 快速检测。

        Returns:
            {
              "has_face": bool,
              "local": { "emotion": str, "confidence": float, "all_scores": dict } | None,
              "deep": None,          # Layer 2 结果（detect 不填充）
              "changed": bool,       # 相比上一次是否有情绪变化
            }
        """
        _ensure_deepface()

        try:
            results = DeepFace.analyze(
                img_path=image_bytes,
                actions=["emotion"],
                enforce_detection=True,
                detector_backend="opencv",
                silent=True,
            )
        except (ValueError, AttributeError):
            # 未检测到人脸
            return {"has_face": False, "local": None, "deep": None, "changed": False}

        face = results[0] if isinstance(results, list) else results
        emotion = face["dominant_emotion"]
        scores = face["emotion"]

        # 归一化为 0-1（DeepFace 返回 0-100）
        confidence = scores[emotion] / 100.0
        all_scores = {k: round(v / 100.0, 4) for k, v in scores.items()}

        # 变化检测
        changed = (emotion != self._last_emotion)

        # 连续负面情绪计数
        if emotion in NEGATIVE_EMOTIONS:
            self._consecutive_neg += 1
        else:
            self._consecutive_neg = 0

        self._last_emotion = emotion

        return {
            "has_face": True,
            "local": {
                "emotion": emotion,
                "confidence": round(confidence, 4),
                "all_scores": all_scores,
            },
            "deep": None,
            "changed": changed,
        }

    # ── 深度分析触发判断 ─────────────────────────────

    def should_trigger_deep(self, detect_result: dict) -> bool:
        """判断是否应升级到 Layer 2 深度分析"""
        if not detect_result["has_face"]:
            return False
        if not self._deep_llm_call:
            return False

        now = time.time()
        if now - self._last_deep_time < DEEP_COOLDOWN_SEC:
            return False

        # 条件 1: 情绪类别跳变
        if detect_result["changed"]:
            return True

        # 条件 2: 连续负面情绪 >= 2
        if self._consecutive_neg >= 2:
            return True

        return False

    # ── Layer 2: LLM 深度分析 ────────────────────────

    async def analyze_deep(self, image_bytes: bytes, local_result: dict) -> Optional[dict]:
        """
        调用视觉 LLM 进行深度情绪+场景分析。

        Returns:
            { "description": str, "suggested_action": str, "suggested_speech": str }
            或 None（如果 LLM 不可用或调用失败）
        """
        if not self._deep_llm_call:
            return None
        try:
            self._last_deep_time = time.time()
            return await self._deep_llm_call(image_bytes, local_result["local"]["emotion"])
        except Exception as e:
            print(f"❌ 情绪深度分析失败: {e}")
            return None
```

- [ ] **Step 6: 运行测试，确认通过**

Run: `cd E:/Proj/pet_buddy/python-service && python -m pytest tests/test_emotion.py -v`
Expected: 3 passed

- [ ] **Step 7: Commit**

```bash
git add python-service/emotion/ python-service/tests/test_emotion.py python-service/requirements.txt
git commit -m "feat(emotion): add EmotionDetector with Layer 1 local detection"
```

---

### Task 2: EmotionDetector — 深度分析触发逻辑测试

**Files:**
- Modify: `python-service/tests/test_emotion.py`

- [ ] **Step 1: 写 should_trigger_deep 的 failing test**

追加到 `python-service/tests/test_emotion.py`：

```python
# ── 深度分析触发判断 ─────────────────────────────

def test_should_trigger_deep_on_change():
    """情绪变化时应触发深度分析"""
    detector = EmotionDetector(deep_llm_call=lambda *a: None)
    result = {"has_face": True, "changed": True, "local": {"emotion": "sad"}}
    assert detector.should_trigger_deep(result) is True


def test_should_not_trigger_deep_without_change():
    """情绪无变化且无连续负面时不触发"""
    detector = EmotionDetector(deep_llm_call=lambda *a: None)
    result = {"has_face": True, "changed": False, "local": {"emotion": "happy"}}
    assert detector.should_trigger_deep(result) is False


def test_should_trigger_deep_on_consecutive_negative():
    """连续负面情绪 >= 2 次触发深度分析"""
    detector = EmotionDetector(deep_llm_call=lambda *a: None)
    detector._consecutive_neg = 2
    result = {"has_face": True, "changed": False, "local": {"emotion": "sad"}}
    assert detector.should_trigger_deep(result) is True


def test_should_not_trigger_deep_during_cooldown():
    """冷却期内不触发"""
    import time
    detector = EmotionDetector(deep_llm_call=lambda *a: None)
    detector._last_deep_time = time.time()  # 刚触发过
    result = {"has_face": True, "changed": True, "local": {"emotion": "sad"}}
    assert detector.should_trigger_deep(result) is False


def test_should_not_trigger_deep_without_llm():
    """没有 deep_llm_call 时不触发"""
    detector = EmotionDetector(deep_llm_call=None)
    result = {"has_face": True, "changed": True, "local": {"emotion": "sad"}}
    assert detector.should_trigger_deep(result) is False


def test_should_not_trigger_deep_without_face():
    """无人脸时不触发"""
    detector = EmotionDetector(deep_llm_call=lambda *a: None)
    result = {"has_face": False, "changed": False, "local": None}
    assert detector.should_trigger_deep(result) is False
```

- [ ] **Step 2: 运行测试，确认全部通过**

Run: `cd E:/Proj/pet_buddy/python-service && python -m pytest tests/test_emotion.py -v`
Expected: 9 passed

- [ ] **Step 3: Commit**

```bash
git add python-service/tests/test_emotion.py
git commit -m "test(emotion): add should_trigger_deep unit tests"
```

---

### Task 3: POST /api/emotion 端点 + LLM 深度分析接入

**Files:**
- Modify: `python-service/main.py`

- [ ] **Step 1: 添加全局 emotion_detector 变量**

在 `python-service/main.py` 顶部 import 区域，在 `from stt.whisper_engine import WhisperEngine` 之后添加：

```python
from emotion.detector import EmotionDetector
```

在全局实例区域（`dream_engine` 行之后）添加：

```python
emotion_detector: Optional[EmotionDetector] = None
```

- [ ] **Step 2: 在 lifespan 中初始化 EmotionDetector**

在 `python-service/main.py` 的 lifespan 函数内，`stt_engine = WhisperEngine(...)` 之后，`print("✅ DogBuddy 服务已就绪！")` 之前添加：

```python
    # 情绪检测器
    async def _deep_llm_call(image_bytes: bytes, local_emotion: str) -> dict:
        """调用视觉 LLM 进行深度情绪分析"""
        import base64
        b64 = base64.b64encode(image_bytes).decode()
        prompt = (
            f"这是一张用户的摄像头截图。本地模型检测到用户表情为 {local_emotion}。\n"
            "请用中文简短描述：\n"
            "1. 用户当前的情绪状态和可能的原因\n"
            "2. 场景描述（姿态、环境等）\n"
            "3. 作为一只关心主人的狗狗，应该做什么反应（一个词：comfort/play/guard/calm/celebrate）\n"
            "4. 用狗狗的口吻说一句关心的话\n\n"
            "请严格按 JSON 格式返回：\n"
            '{"description": "...", "suggested_action": "...", "suggested_speech": "..."}'
        )
        if agent and agent.llm_client and agent.llm_ready:
            cfg = agent.config.get("llm", {})
            model = cfg.get("vision_model", cfg.get("model", "deepseek-chat"))
            resp = await agent.llm_client.chat.completions.create(
                model=model,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                    ],
                }],
                temperature=0.7,
                max_tokens=200,
            )
            import json as _json
            raw = resp.choices[0].message.content
            # 尝试从回复中解析 JSON
            try:
                return _json.loads(raw)
            except _json.JSONDecodeError:
                return {"description": raw, "suggested_action": "comfort", "suggested_speech": ""}
        return None

    emotion_detector = EmotionDetector(deep_llm_call=_deep_llm_call)
```

注意: 在 lifespan 的 `global` 声明中追加 `emotion_detector`。

- [ ] **Step 3: 添加 Pydantic 响应模型**

在 `python-service/main.py` 的数据模型区域（`STTResponse` 之后）添加：

```python
class EmotionLocalResult(BaseModel):
    emotion: str
    confidence: float
    all_scores: Dict[str, float]

class EmotionDeepResult(BaseModel):
    description: str
    suggested_action: str
    suggested_speech: str

class EmotionResponse(BaseModel):
    has_face: bool
    local: Optional[EmotionLocalResult] = None
    deep: Optional[EmotionDeepResult] = None
    changed: bool = False
```

- [ ] **Step 4: 添加 POST /api/emotion 端点**

在 `python-service/main.py` 中，`@app.post("/api/stt")` 之前添加：

```python
@app.post("/api/emotion", response_model=EmotionResponse)
async def detect_emotion(
    image: UploadFile = File(...),
    deep: bool = Form(False),
):
    """
    情绪检测 — 摄像头截帧 → 本地快速识别 + 可选深度分析

    Args:
        image: JPEG 截帧
        deep:  是否强制进行 LLM 深度分析
    """
    if not emotion_detector:
        raise HTTPException(status_code=503, detail="情绪检测器未初始化")

    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="图像为空")

    # Layer 1: 本地快速检测
    result = await emotion_detector.detect(image_bytes)
    print(f"👁️ 情绪检测: has_face={result['has_face']}, "
          f"emotion={result['local']['emotion'] if result['local'] else 'N/A'}, "
          f"changed={result['changed']}")

    # Layer 2: 判断是否升级到深度分析
    if deep or (result["has_face"] and emotion_detector.should_trigger_deep(result)):
        deep_result = await emotion_detector.analyze_deep(image_bytes, result)
        result["deep"] = deep_result
        if deep_result:
            print(f"🧠 深度分析: {deep_result.get('description', '')[:50]}")
            # 注入到 agent 的 system prompt 上下文
            if agent:
                agent.owner_emotion_context = deep_result.get("description", "")

    return result
```

- [ ] **Step 5: 运行服务验证端点注册**

Run: `cd E:/Proj/pet_buddy/python-service && python -c "from main import app; print([r.path for r in app.routes if hasattr(r,'path')])" 2>/dev/null | grep emotion`
Expected: 包含 `/api/emotion`

- [ ] **Step 6: Commit**

```bash
git add python-service/main.py
git commit -m "feat(emotion): add POST /api/emotion endpoint with Layer 1+2 detection"
```

---

### Task 4: DogAgent 情绪上下文注入

**Files:**
- Modify: `python-service/agent/dog_agent.py`

- [ ] **Step 1: 添加 owner_emotion_context 属性**

在 `python-service/agent/dog_agent.py` 的 `__init__` 方法末尾添加：

```python
        self.owner_emotion_context: Optional[str] = None
```

- [ ] **Step 2: 在 _build_system_prompt 中注入情绪上下文**

在 `python-service/agent/dog_agent.py` 的 `_build_system_prompt` 方法中，在最后的 `return (` 之前添加：

```python
        # ── 主人情绪上下文（由情绪检测系统注入）──
        emotion_block = ''
        if self.owner_emotion_context:
            emotion_block = (
                '\n\n【主人当前状态】\n'
                f'你刚刚偷偷看了主人一眼，观察到：{self.owner_emotion_context}\n'
                '请根据观察到的情绪自然地调整你的语气和行为，'
                '但不要直接说"我检测到你很难过"这种机械的话。'
                '像一只敏感的狗狗那样，用行动和关心来回应。'
            )
```

然后在 return 语句的字符串拼接中，在 `{memory_block}` 之后、`'请用符合柯基犬人设的方式回应主人的话。'` 之前插入 `{emotion_block}`：

将：
```python
            f'{memory_block}\n\n'
            '请用符合柯基犬人设的方式回应主人的话。'
```

改为：
```python
            f'{memory_block}'
            f'{emotion_block}\n\n'
            '请用符合柯基犬人设的方式回应主人的话。'
```

- [ ] **Step 3: 运行现有测试确认无回归**

Run: `cd E:/Proj/pet_buddy/python-service && python -m pytest tests/ -v --ignore=tests/test_gpt_sovits.py 2>&1 | tail -20`
Expected: 所有现有测试仍然通过

- [ ] **Step 4: Commit**

```bash
git add python-service/agent/dog_agent.py
git commit -m "feat(emotion): inject owner_emotion_context into DogAgent system prompt"
```

---

### Task 5: 前端 — petStore + settingsStore 扩展

**Files:**
- Modify: `renderer/src/stores/pet.js`
- Modify: `renderer/src/stores/settings.js`

- [ ] **Step 1: petStore 添加 emotionObserver 状态**

在 `renderer/src/stores/pet.js` 中，在 `const lastInteraction = ref(Date.now())` 之后添加：

```javascript
  // 情绪观察状态
  const emotionObserver = ref({
    enabled: false,
    lastEmotion: null,
    lastConfidence: 0,
    lastDeepDesc: '',
    lastDetectTime: 0,
    isObserving: false,
    consecutiveNeg: 0,
  })
```

在 return 对象中追加 `emotionObserver`：

```javascript
    emotionObserver,
```

- [ ] **Step 2: settingsStore 添加情绪观察设置**

在 `renderer/src/stores/settings.js` 中，在天性模式设置区域之后添加：

```javascript
  // ========== 情绪观察设置 ==========

  const emotionEnabled = ref(false)
  const emotionInterval = ref(10)  // 分钟
```

在 `loadSettings` 函数的 `if (saved)` 块中追加：

```javascript
        if (settings.emotionEnabled !== undefined) emotionEnabled.value = settings.emotionEnabled
        if (settings.emotionInterval !== undefined) emotionInterval.value = settings.emotionInterval
```

在 `saveSettings` 函数的 settings 对象中追加：

```javascript
        emotionEnabled: emotionEnabled.value,
        emotionInterval: emotionInterval.value,
```

在 return 对象中追加：

```javascript
    // 情绪观察设置
    emotionEnabled,
    emotionInterval,
```

- [ ] **Step 3: Commit**

```bash
git add renderer/src/stores/pet.js renderer/src/stores/settings.js
git commit -m "feat(emotion): extend petStore and settingsStore with emotion observer state"
```

---

### Task 6: 行为脚本 — peek_observe + 情绪反应

**Files:**
- Modify: `renderer/src/composables/useBehaviorSequencer.js`

- [ ] **Step 1: 在 BEHAVIOR_SCRIPTS 中添加新脚本**

在 `renderer/src/composables/useBehaviorSequencer.js` 的 `BEHAVIOR_SCRIPTS` 对象中，在 `bedtime` 脚本之后添加：

```javascript
  // ─── 情绪观察 ───

  // 偷看动作（由 useEmotionObserver 主动调用，不参与随机触发）
  peek_observe: {
    id: 'peek_observe',
    label: '偷看',
    cooldown: 0,
    weight: 0,
    steps: [
      { type: 'pose',  value: 'alert',      duration: 300 },
      { type: 'pose',  value: 'cute_pose',  duration: 400 },
      { type: 'wait',  duration: 600 },
      { type: 'pose',  value: 'idle' },
    ],
  },

  // 情绪反应：安慰（主人难过/害怕时）
  emotion_comfort: {
    id: 'emotion_comfort',
    label: '安慰主人',
    cooldown: 0,
    weight: 0,
    steps: [
      { type: 'pose',  value: 'sad',        duration: 400 },
      { type: 'pose',  value: 'cuddle',     duration: 300 },
      { type: 'prop',  value: 'hearts',     op: 'add' },
      { type: 'wait',  duration: 3000 },
      { type: 'prop',  value: 'hearts',     op: 'remove' },
      { type: 'pose',  value: 'idle' },
    ],
  },

  // 情绪反应：开心（主人高兴时）
  emotion_happy_react: {
    id: 'emotion_happy_react',
    label: '跟着开心',
    cooldown: 0,
    weight: 0,
    steps: [
      { type: 'pose',  value: 'happy_run',  duration: 200 },
      { type: 'prop',  value: 'hearts',     op: 'add' },
      { type: 'wait',  duration: 2000 },
      { type: 'prop',  value: 'hearts',     op: 'remove' },
      { type: 'pose',  value: 'idle' },
    ],
  },

  // 情绪反应：小心翼翼（主人生气时）
  emotion_cautious: {
    id: 'emotion_cautious',
    label: '小心翼翼',
    cooldown: 0,
    weight: 0,
    steps: [
      { type: 'pose',  value: 'sad',        duration: 500 },
      { type: 'wait',  duration: 2000 },
      { type: 'pose',  value: 'idle' },
    ],
  },

  // 情绪反应：好奇（主人惊讶时）
  emotion_curious: {
    id: 'emotion_curious',
    label: '好奇',
    cooldown: 0,
    weight: 0,
    steps: [
      { type: 'pose',  value: 'cute_pose',  duration: 300 },
      { type: 'wait',  duration: 1500 },
      { type: 'pose',  value: 'idle' },
    ],
  },
```

- [ ] **Step 2: Commit**

```bash
git add renderer/src/composables/useBehaviorSequencer.js
git commit -m "feat(emotion): add peek_observe + emotion reaction behavior scripts"
```

---

### Task 7: useEmotionObserver composable

**Files:**
- Create: `renderer/src/composables/useEmotionObserver.js`

- [ ] **Step 1: 创建 useEmotionObserver**

创建 `renderer/src/composables/useEmotionObserver.js`：

```javascript
/**
 * useEmotionObserver — 来福偷偷观察主人
 *
 * 管理摄像头截帧、调度（定时/事件/手动三触发）、
 * 结果分发到 petStore 和 behaviorSequencer。
 *
 * 摄像头策略：每次截帧时打开 → 拍一帧 → 立即关闭，不保持常开。
 */

import { watch, onUnmounted } from 'vue'
import { usePetStore } from '../stores/pet'
import { useSettingsStore } from '../stores/settings'

// 情绪 → 行为脚本映射
const EMOTION_BEHAVIOR_MAP = {
  happy:    'emotion_happy_react',
  sad:      'emotion_comfort',
  angry:    'emotion_cautious',
  fear:     'emotion_comfort',
  disgust:  'emotion_cautious',
  surprise: 'emotion_curious',
  neutral:  null,  // 不触发特殊反应
}

export function useEmotionObserver (behaviorSequencer, chatStore) {
  const petStore = usePetStore()
  const settings = useSettingsStore()

  let intervalTimer = null
  let noFaceCount = 0
  let currentInterval = 0  // 当前实际轮询间隔 (ms)

  // ─── 截帧：打开摄像头 → canvas 截帧 → 关闭 ───

  async function captureFrame () {
    let stream = null
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 640, height: 480, facingMode: 'user' }
      })
      const track = stream.getVideoTracks()[0]
      const imageCapture = new ImageCapture(track)
      const bitmap = await imageCapture.grabFrame()

      const canvas = document.createElement('canvas')
      canvas.width = bitmap.width
      canvas.height = bitmap.height
      const ctx = canvas.getContext('2d')
      ctx.drawImage(bitmap, 0, 0)

      return new Promise((resolve) => {
        canvas.toBlob(resolve, 'image/jpeg', 0.8)
      })
    } catch (err) {
      console.warn('[EmotionObserver] 摄像头截帧失败:', err.message)
      return null
    } finally {
      if (stream) stream.getTracks().forEach(t => t.stop())
    }
  }

  // ─── 发送检测请求 ───

  async function detectEmotion (forceDeep = false) {
    if (petStore.emotionObserver.isObserving) return null

    const eo = petStore.emotionObserver
    eo.isObserving = true

    // 播放偷看动画
    if (behaviorSequencer && !behaviorSequencer.isRunning.value) {
      behaviorSequencer.trigger('peek_observe')
    }

    try {
      const blob = await captureFrame()
      if (!blob) {
        eo.isObserving = false
        return null
      }

      const pythonPort = await window.electronAPI?.getPythonPort?.() || 18765
      const formData = new FormData()
      formData.append('image', blob, 'frame.jpg')
      formData.append('deep', forceDeep ? 'true' : 'false')

      const res = await fetch(`http://127.0.0.1:${pythonPort}/api/emotion`, {
        method: 'POST',
        body: formData,
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)

      const result = await res.json()
      console.log('[EmotionObserver] 检测结果:', result)

      // 更新 petStore
      if (result.has_face) {
        noFaceCount = 0
        resetInterval()
        eo.lastEmotion = result.local.emotion
        eo.lastConfidence = result.local.confidence
        eo.lastDetectTime = Date.now()

        if (result.local.emotion && EMOTION_BEHAVIOR_MAP[result.local.emotion]) {
          // Layer 1 快速反应：触发姿态
          if (behaviorSequencer && !behaviorSequencer.isRunning.value) {
            behaviorSequencer.trigger(EMOTION_BEHAVIOR_MAP[result.local.emotion])
          }
        }

        // 连续负面计数
        const neg = ['sad', 'angry', 'fear', 'disgust']
        if (neg.includes(result.local.emotion)) {
          eo.consecutiveNeg++
        } else {
          eo.consecutiveNeg = 0
        }

        // Layer 2 深度反应
        if (result.deep) {
          eo.lastDeepDesc = result.deep.description || ''
          if (result.deep.suggested_speech && chatStore?.showMessage) {
            chatStore.showMessage(result.deep.suggested_speech, 6000)
          }
        }
      } else {
        noFaceCount++
        if (noFaceCount >= 3) {
          slowDownInterval()
        }
      }

      return result
    } catch (err) {
      console.error('[EmotionObserver] 检测请求失败:', err)
      return null
    } finally {
      eo.isObserving = false
    }
  }

  // ─── 定时调度 ───

  function startSchedule () {
    stopSchedule()
    currentInterval = settings.emotionInterval * 60 * 1000
    intervalTimer = setInterval(() => detectEmotion(false), currentInterval)
    console.log(`[EmotionObserver] 定时观察已启动: 每 ${settings.emotionInterval} 分钟`)
  }

  function stopSchedule () {
    if (intervalTimer) {
      clearInterval(intervalTimer)
      intervalTimer = null
    }
  }

  function resetInterval () {
    if (intervalTimer && currentInterval !== settings.emotionInterval * 60 * 1000) {
      startSchedule()
    }
  }

  function slowDownInterval () {
    // 连续 3 次未检测到人脸 → 间隔翻倍
    stopSchedule()
    currentInterval = Math.min(currentInterval * 2, 30 * 60 * 1000)
    intervalTimer = setInterval(() => detectEmotion(false), currentInterval)
    console.log(`[EmotionObserver] 未检测到人脸，降频: ${Math.round(currentInterval / 60000)} 分钟`)
  }

  // ─── 事件驱动触发 ───

  function onBeforeChat () {
    if (!settings.emotionEnabled || !petStore.emotionObserver.enabled) return
    const last = petStore.emotionObserver.lastDetectTime
    if (Date.now() - last > 60000) {  // 距上次 > 1 分钟才触发
      detectEmotion(false)
    }
  }

  function onIdle (idleMs) {
    if (!settings.emotionEnabled || !petStore.emotionObserver.enabled) return
    if (idleMs > 5 * 60 * 1000) {
      detectEmotion(false)
    }
  }

  // ─── 手动触发 ───

  function manualDetect () {
    return detectEmotion(true)
  }

  // ─── 权限请求（首次引导用） ───

  async function requestPermission () {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true })
      stream.getTracks().forEach(t => t.stop())
      return true
    } catch {
      return false
    }
  }

  // ─── 生命周期 ───

  function init () {
    if (settings.emotionEnabled && petStore.emotionObserver.enabled) {
      startSchedule()
    }
  }

  function destroy () {
    stopSchedule()
  }

  // 监听设置变化
  watch(() => settings.emotionEnabled, (enabled) => {
    if (enabled && petStore.emotionObserver.enabled) {
      startSchedule()
    } else {
      stopSchedule()
    }
  })

  watch(() => settings.emotionInterval, () => {
    if (intervalTimer) startSchedule()
  })

  onUnmounted(() => destroy())

  return {
    init,
    destroy,
    detectEmotion,
    manualDetect,
    onBeforeChat,
    onIdle,
    requestPermission,
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add renderer/src/composables/useEmotionObserver.js
git commit -m "feat(emotion): add useEmotionObserver composable with camera + scheduling"
```

---

### Task 8: 设置面板 — 情绪观察 UI + 引导弹窗

**Files:**
- Modify: `renderer/src/components/SettingsPanel.vue`

- [ ] **Step 1: 在 template 中添加情绪观察设置区域**

在 `renderer/src/components/SettingsPanel.vue` 的 template 中，`<!-- 天性模式 -->` section 之后、`<!-- 关于 -->` section 之前添加：

```html
        <!-- 情绪观察 -->
        <section class="settings-section">
          <h3>👁️ 情绪观察</h3>
          <div class="setting-row">
            <div>
              <span>让来福观察你</span>
              <p class="hint" style="margin: 2px 0 0 0;">通过摄像头感知你的心情</p>
            </div>
            <label class="toggle">
              <input type="checkbox" v-model="emotionToggle" @change="onEmotionToggle" />
              <span class="toggle-slider"></span>
            </label>
          </div>

          <template v-if="settings.emotionEnabled && petStore.emotionObserver.enabled">
            <div class="slider-control" style="margin-top: 12px;">
              <span>偷看频率</span>
              <input
                type="range"
                v-model.number="settings.emotionInterval"
                min="5"
                max="30"
                step="5"
                @change="settings.saveSettings()"
              />
              <span class="slider-value">{{ settings.emotionInterval }}分钟</span>
            </div>

            <button class="manual-detect-btn" @click="manualDetect">
              让来福看看你
            </button>

            <p class="hint" v-if="petStore.emotionObserver.lastEmotion" style="margin-top: 8px;">
              上次观察: {{ emotionLabel[petStore.emotionObserver.lastEmotion] || petStore.emotionObserver.lastEmotion }}
              ({{ Math.round(petStore.emotionObserver.lastConfidence * 100) }}%)
            </p>
          </template>
        </section>

        <!-- 引导弹窗 -->
        <div v-if="showOnboarding" class="onboarding-overlay" @click.self="cancelOnboarding">
          <div class="onboarding-dialog">
            <p class="onboarding-text">汪？主人，来福想看看你的样子！可以让来福偷偷看你吗？</p>
            <p class="hint" style="text-align: center;">深度分析时图像会发送给 AI 服务</p>
            <div class="onboarding-buttons">
              <button class="btn-accept" @click="acceptOnboarding">好呀！</button>
              <button class="btn-reject" @click="cancelOnboarding">不要</button>
            </div>
          </div>
        </div>
```

- [ ] **Step 2: 在 script 中添加逻辑**

在 `renderer/src/components/SettingsPanel.vue` 的 `<script setup>` 中，import 区域追加：

```javascript
import { usePetStore } from '@/stores/pet'
```

在已有变量之后添加：

```javascript
const petStore = usePetStore()

const emotionToggle = ref(settings.emotionEnabled && petStore.emotionObserver.enabled)
const showOnboarding = ref(false)

const emotionLabel = {
  happy: '开心', sad: '难过', angry: '生气',
  surprise: '惊讶', neutral: '平静', fear: '紧张', disgust: '厌恶'
}

function onEmotionToggle () {
  if (emotionToggle.value) {
    // 首次开启 → 引导流程
    if (!petStore.emotionObserver.enabled) {
      showOnboarding.value = true
    } else {
      settings.emotionEnabled = true
      settings.saveSettings()
    }
  } else {
    settings.emotionEnabled = false
    petStore.emotionObserver.enabled = false
    settings.saveSettings()
  }
}

async function acceptOnboarding () {
  showOnboarding.value = false
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ video: true })
    stream.getTracks().forEach(t => t.stop())
    petStore.emotionObserver.enabled = true
    settings.emotionEnabled = true
    settings.saveSettings()
  } catch {
    emotionToggle.value = false
    petStore.emotionObserver.enabled = false
  }
}

function cancelOnboarding () {
  showOnboarding.value = false
  emotionToggle.value = false
}

async function manualDetect () {
  const pythonPort = await window.electronAPI?.getPythonPort?.() || 18765
  // 简易实现：直接截帧并发送
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { width: 640, height: 480, facingMode: 'user' }
    })
    const track = stream.getVideoTracks()[0]
    const imageCapture = new ImageCapture(track)
    const bitmap = await imageCapture.grabFrame()
    stream.getTracks().forEach(t => t.stop())

    const canvas = document.createElement('canvas')
    canvas.width = bitmap.width
    canvas.height = bitmap.height
    canvas.getContext('2d').drawImage(bitmap, 0, 0)

    const blob = await new Promise(r => canvas.toBlob(r, 'image/jpeg', 0.8))
    const formData = new FormData()
    formData.append('image', blob, 'frame.jpg')
    formData.append('deep', 'true')

    const res = await fetch(`http://127.0.0.1:${pythonPort}/api/emotion`, {
      method: 'POST', body: formData
    })
    if (res.ok) {
      const result = await res.json()
      if (result.has_face && result.local) {
        petStore.emotionObserver.lastEmotion = result.local.emotion
        petStore.emotionObserver.lastConfidence = result.local.confidence
        petStore.emotionObserver.lastDetectTime = Date.now()
        if (result.deep) petStore.emotionObserver.lastDeepDesc = result.deep.description || ''
      }
    }
  } catch (err) {
    console.error('[Settings] 手动检测失败:', err)
  }
}
```

- [ ] **Step 3: 添加样式**

在 `<style scoped>` 末尾（`</style>` 之前）添加：

```css
/* 手动检测按钮 */
.manual-detect-btn {
  width: 100%;
  margin-top: 12px;
  padding: 10px;
  background: rgba(102, 126, 234, 0.1);
  border: 1px dashed #667eea;
  border-radius: 8px;
  color: #667eea;
  font-size: 13px;
  cursor: pointer;
  transition: background 0.2s;
}

.manual-detect-btn:hover {
  background: rgba(102, 126, 234, 0.2);
}

/* 引导弹窗 */
.onboarding-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
}

.onboarding-dialog {
  background: var(--bg-panel, #fff);
  border-radius: 16px;
  padding: 24px;
  max-width: 300px;
  text-align: center;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}

.onboarding-text {
  font-size: 15px;
  line-height: 1.6;
  color: var(--text-primary, #333);
  margin: 0 0 12px 0;
}

.onboarding-buttons {
  display: flex;
  gap: 12px;
  justify-content: center;
  margin-top: 16px;
}

.btn-accept {
  padding: 8px 24px;
  background: #667eea;
  color: white;
  border: none;
  border-radius: 20px;
  cursor: pointer;
  font-size: 14px;
  transition: background 0.2s;
}

.btn-accept:hover { background: #5a6fd6; }

.btn-reject {
  padding: 8px 24px;
  background: var(--bg-secondary, #eee);
  color: var(--text-secondary, #666);
  border: none;
  border-radius: 20px;
  cursor: pointer;
  font-size: 14px;
}
```

- [ ] **Step 4: Commit**

```bash
git add renderer/src/components/SettingsPanel.vue
git commit -m "feat(emotion): add emotion observer settings UI with onboarding dialog"
```

---

### Task 9: App.vue — 挂载 useEmotionObserver

**Files:**
- Modify: `renderer/src/App.vue`

- [ ] **Step 1: 导入并初始化 useEmotionObserver**

在 `renderer/src/App.vue` 的 `<script setup>` import 区域追加：

```javascript
import { useEmotionObserver } from './composables/useEmotionObserver'
```

在 `const { init: initBreak, ... } = useBreakReminder(activeCanvasProxy)` 之后添加：

```javascript
// 情绪观察（需要行为序列器，目前先传 null，PoseCanvas 挂载后注入）
const emotionObserver = useEmotionObserver(null, chatStore)
```

在 `onMounted` 回调中，`initNature()` / `initBreak()` 之后添加：

```javascript
  emotionObserver.init()
```

在 `onUnmounted` 回调中，`destroyBreak()` 之后添加：

```javascript
  emotionObserver.destroy()
```

- [ ] **Step 2: provide emotionObserver 给子组件使用**

在 `provide('breakReminder', ...)` 之后添加：

```javascript
provide('emotionObserver', emotionObserver)
```

- [ ] **Step 3: Commit**

```bash
git add renderer/src/App.vue
git commit -m "feat(emotion): mount useEmotionObserver in App.vue"
```

---

### Task 10: 集成测试 — 端到端验证

**Files:**
- (No new files, manual verification)

- [ ] **Step 1: 运行后端全部测试**

Run: `cd E:/Proj/pet_buddy/python-service && python -m pytest tests/test_emotion.py -v`
Expected: 9 passed

- [ ] **Step 2: 验证后端服务启动无报错**

Run: `cd E:/Proj/pet_buddy/python-service && timeout 10 python -c "import emotion.detector; print('✅ emotion module imports OK')" 2>&1`
Expected: 输出 `✅ emotion module imports OK`

- [ ] **Step 3: 验证 API 模型导入**

Run: `cd E:/Proj/pet_buddy/python-service && python -c "from main import EmotionResponse; print(EmotionResponse.model_json_schema())" 2>&1 | head -5`
Expected: 输出 JSON schema，包含 `has_face`, `local`, `deep`, `changed` 字段

- [ ] **Step 4: Commit 最终集成确认**

```bash
git add -A
git commit -m "feat(emotion): complete emotion recognition system integration"
```
