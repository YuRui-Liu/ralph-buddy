# ralph-buddy v1.0 发布版配置化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 消除所有硬编码路径/端口/密钥，统一配置加载，使项目可移植部署。

**Architecture:** 新建 `core/config.py` 统一配置加载（config.json → .env → 环境变量），前端新建 `utils/api.js` 统一 API base URL，所有组件从这两个入口获取配置。

**Tech Stack:** python-dotenv, Vue 3 utils module, .gitignore

---

## File Structure

### New Files
| File | Responsibility |
|------|---------------|
| `python-service/core/__init__.py` | Package init |
| `python-service/core/config.py` | 统一配置加载器 |
| `python-service/config.example.json` | 配置模板（无敏感信息） |
| `python-service/.env.example` | 环境变量模板 |
| `renderer/src/utils/api.js` | 前端 API base URL 统一管理 |
| `.gitignore` | 保护敏感文件 |
| `docs/发布部署/配置说明.md` | 配置项清单文档 |
| `docs/发布部署/部署指南.md` | 部署说明 |

### Modified Files
| File | Changes |
|------|---------|
| `python-service/main.py` | 用 core.config 替换硬编码路径/端口 |
| `python-service/memory/memory_system.py` | 用 config 替换 E:\ embedding 路径 |
| `python-service/tts/gpt_sovits_engine.py` | 用 config 替换硬编码端口 9880 |
| `python-service/agent/dog_agent.py` | 用 core.config 替换 _load_config |
| `renderer/src/App.vue` | 用 apiFetch 替换硬编码 fetch |
| `renderer/src/components/InputPanel.vue` | 同上 |
| `renderer/src/components/VoiceRecorder.vue` | 同上 |
| `renderer/src/components/DreamDiary.vue` | 同上 |
| `renderer/src/components/MemoryPanel.vue` | 同上 |
| `renderer/src/components/VoiceManager.vue` | 同上 |
| `renderer/src/components/SettingsPanel.vue` | 同上 |
| `renderer/src/components/VoicePackageWizard.vue` | 同上 |
| `renderer/src/composables/usePetAttributeTicker.js` | 同上 |
| `renderer/src/composables/useEmotionObserver.js` | 同上 |
| `renderer/src/plugins/flirt/FlirtPlugin.vue` | 同上 |
| `renderer/src/plugins/search/SearchPlugin.vue` | 同上 |
| `electron/main.js` | 端口配置化 |

---

### Task 1: core/config.py — 统一配置加载器

**Files:**
- Create: `python-service/core/__init__.py`
- Create: `python-service/core/config.py`
- Create: `python-service/config.example.json`
- Create: `python-service/.env.example`

- [ ] **Step 1: 创建 core 包**

创建空文件 `python-service/core/__init__.py`。

- [ ] **Step 2: 创建 config.example.json**

创建 `python-service/config.example.json`：

```json
{
  "llm": {
    "provider": "openai",
    "base_url": "https://api.deepseek.com/v1",
    "api_key": "",
    "model": "deepseek-chat"
  },
  "user": {
    "name": "主人"
  },
  "pet": {
    "name": "来福",
    "personality": "活泼、忠诚、有点粘人、偶尔调皮",
    "obedience": 60,
    "snark": 30
  },
  "tts": {
    "provider": "edge",
    "voice": "zh-CN-XiaoxiaoNeural"
  },
  "stt": {
    "provider": "whisper",
    "model": "small"
  },
  "image": {
    "provider": "siliconflow",
    "base_url": "https://api.siliconflow.cn/v1",
    "api_key": "",
    "model": "black-forest-labs/FLUX.1-schnell"
  },
  "server": {
    "host": "127.0.0.1",
    "port": 18765
  },
  "paths": {
    "whisper_model": "",
    "embedding_model": "",
    "data_dir": "data",
    "gpt_sovits_dir": "",
    "gpt_sovits_port": 9880
  }
}
```

- [ ] **Step 3: 创建 .env.example**

创建 `python-service/.env.example`：

```bash
# ===== API 密钥（必填，至少填 LLM）=====
LLM_API_KEY=
IMAGE_API_KEY=

# ===== 服务配置 =====
PYTHON_HOST=127.0.0.1
PYTHON_PORT=18765

# ===== 本地模型路径（留空则自动下载或降级）=====
WHISPER_MODEL_PATH=
EMBEDDING_MODEL_PATH=
GPT_SOVITS_DIR=
GPT_SOVITS_PORT=9880

# ===== 数据存储目录（默认 ./data）=====
DATA_DIR=
```

- [ ] **Step 4: 创建 core/config.py**

创建 `python-service/core/config.py`：

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一配置加载器
加载顺序：config.json → .env 文件 → 环境变量（最高优先级）
"""

import os
import json
from typing import Optional

from dotenv import load_dotenv

_SERVICE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_config: Optional[dict] = None


def load_config() -> dict:
    """
    加载并返回合并后的配置字典。
    1. 读取 config.json（或 config.example.json 作为兜底）
    2. 加载 .env 文件
    3. 环境变量覆盖敏感字段和路径
    """
    global _config

    # 1. 读取 config.json
    config_path = os.path.join(_SERVICE_DIR, 'config.json')
    example_path = os.path.join(_SERVICE_DIR, 'config.example.json')

    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
    elif os.path.exists(example_path):
        print("[config] config.json 不存在，使用 config.example.json 默认值")
        with open(example_path, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
    else:
        print("[config] 未找到配置文件，使用内置默认值")
        cfg = _builtin_defaults()

    # 确保所有顶层 key 存在
    for key, default in _builtin_defaults().items():
        if key not in cfg:
            cfg[key] = default
        elif isinstance(default, dict):
            for k, v in default.items():
                if k not in cfg[key]:
                    cfg[key][k] = v

    # 2. 加载 .env
    env_path = os.path.join(_SERVICE_DIR, '.env')
    load_dotenv(env_path, override=True)

    # 3. 环境变量覆盖
    _apply_env_overrides(cfg)

    # 4. 解析相对路径
    _resolve_paths(cfg)

    _config = cfg
    return cfg


def get_config() -> dict:
    """获取全局配置单例。未初始化则自动加载。"""
    global _config
    if _config is None:
        load_config()
    return _config


def get_service_dir() -> str:
    """返回 python-service 目录的绝对路径。"""
    return _SERVICE_DIR


def _builtin_defaults() -> dict:
    return {
        "llm": {"provider": "openai", "base_url": "", "api_key": "", "model": "deepseek-chat"},
        "user": {"name": "主人"},
        "pet": {"name": "来福", "personality": "活泼、忠诚、有点粘人、偶尔调皮",
                "obedience": 60, "snark": 30},
        "tts": {"provider": "edge", "voice": "zh-CN-XiaoxiaoNeural"},
        "stt": {"provider": "whisper", "model": "small"},
        "image": {"provider": "siliconflow", "base_url": "https://api.siliconflow.cn/v1",
                  "api_key": "", "model": "black-forest-labs/FLUX.1-schnell"},
        "server": {"host": "127.0.0.1", "port": 18765},
        "paths": {"whisper_model": "", "embedding_model": "", "data_dir": "data",
                  "gpt_sovits_dir": "", "gpt_sovits_port": 9880},
    }


def _apply_env_overrides(cfg: dict) -> None:
    """环境变量覆盖配置中的对应字段。"""
    _override(cfg, "llm", "api_key", "LLM_API_KEY")
    _override(cfg, "image", "api_key", "IMAGE_API_KEY")
    _override(cfg, "server", "host", "PYTHON_HOST")
    _override_int(cfg, "server", "port", "PYTHON_PORT")
    _override(cfg, "paths", "whisper_model", "WHISPER_MODEL_PATH")
    _override(cfg, "paths", "embedding_model", "EMBEDDING_MODEL_PATH")
    _override(cfg, "paths", "gpt_sovits_dir", "GPT_SOVITS_DIR")
    _override_int(cfg, "paths", "gpt_sovits_port", "GPT_SOVITS_PORT")
    _override(cfg, "paths", "data_dir", "DATA_DIR")


def _override(cfg, section, key, env_var):
    val = os.getenv(env_var)
    if val:
        cfg[section][key] = val


def _override_int(cfg, section, key, env_var):
    val = os.getenv(env_var)
    if val:
        try:
            cfg[section][key] = int(val)
        except ValueError:
            pass


def _resolve_paths(cfg: dict) -> None:
    """将相对路径解析为绝对路径（相对于 python-service 目录）。"""
    paths = cfg.get("paths", {})
    data_dir = paths.get("data_dir", "data")
    if data_dir and not os.path.isabs(data_dir):
        paths["data_dir"] = os.path.normpath(os.path.join(_SERVICE_DIR, data_dir))
    else:
        paths["data_dir"] = data_dir or os.path.join(_SERVICE_DIR, "data")
```

- [ ] **Step 5: Commit**

```bash
cd E:/Proj/pet_buddy
git add python-service/core/ python-service/config.example.json python-service/.env.example
git commit -m "feat(config): add unified config loader with env override support"
```

---

### Task 2: 后端硬编码消除 — main.py

**Files:**
- Modify: `python-service/main.py`

- [ ] **Step 1: 替换 config 加载方式**

在 `python-service/main.py` 的 import 区域，添加：

```python
from core.config import load_config, get_config, get_service_dir
```

- [ ] **Step 2: 在 lifespan 开头加载配置**

在 lifespan 函数的 `print("🐕 DogBuddy 服务启动中...")` 之后，添加：

```python
    cfg = load_config()
    print(f"📋 配置加载完成: server={cfg['server']['host']}:{cfg['server']['port']}")
```

- [ ] **Step 3: 替换 Whisper 模型路径**

将 main.py 中的：

```python
    local_model = os.path.expanduser(r"E:\LLM\backbone\Voice\faster-whisper-small")
    if not os.path.exists(local_model):
        local_model = None
```

替换为：

```python
    local_model = cfg['paths'].get('whisper_model') or None
    if local_model and not os.path.exists(local_model):
        print(f"⚠️ Whisper 模型路径不存在: {local_model}，将自动下载")
        local_model = None
```

- [ ] **Step 4: 替换 main 入口的 host/port**

将文件末尾的：

```python
if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 18765))

    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=port,
        log_level="info"
    )
```

替换为：

```python
if __name__ == "__main__":
    import uvicorn

    cfg = get_config()
    host = cfg['server']['host']
    port = cfg['server']['port']

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        log_level="info"
    )
```

- [ ] **Step 5: 让 DogBuddyAgent 使用统一配置**

在 lifespan 中，将 `agent = DogBuddyAgent(memory, attr_manager)` 改为传入已加载的配置（DogBuddyAgent 的 `_load_config` 方法已经读取 config.json，不需要改 agent 代码，只需确保 config.json 存在即可——这已由 core/config 保证）。

无需修改 agent/dog_agent.py 的 `_load_config`，因为它读的是同一个 config.json。

- [ ] **Step 6: Commit**

```bash
cd E:/Proj/pet_buddy
git add python-service/main.py
git commit -m "fix(config): remove hardcoded Whisper path and server port from main.py"
```

---

### Task 3: 后端硬编码消除 — memory_system.py + gpt_sovits_engine.py

**Files:**
- Modify: `python-service/memory/memory_system.py`
- Modify: `python-service/tts/gpt_sovits_engine.py`

- [ ] **Step 1: 修复 memory_system.py 的 embedding 路径**

在 `python-service/memory/memory_system.py` 中，将：

```python
LOCAL_EMBED_MODEL = r'E:\LLM\backbone\embeddings\all-MiniLM-L6-v2'
```

替换为：

```python
def _get_embed_model_path() -> str:
    """从统一配置获取 embedding 模型路径。"""
    try:
        from core.config import get_config
        return get_config()['paths'].get('embedding_model', '')
    except Exception:
        return os.getenv('EMBEDDING_MODEL_PATH', '')
```

然后将所有引用 `LOCAL_EMBED_MODEL` 的地方改为调用 `_get_embed_model_path()`。具体在 `_make_embedding_function` 方法中，将：

```python
            if os.path.exists(LOCAL_EMBED_MODEL):
                return _LocalEF(LOCAL_EMBED_MODEL)
```

替换为：

```python
            embed_path = _get_embed_model_path()
            if embed_path and os.path.exists(embed_path):
                return _LocalEF(embed_path)
```

- [ ] **Step 2: 修复 gpt_sovits_engine.py 的端口**

在 `python-service/tts/gpt_sovits_engine.py` 中，将类属性：

```python
    API_PORT = 9880
    API_BASE = f"http://127.0.0.1:{API_PORT}"
```

替换为：

```python
    def __init__(self, voice_dir: str, api_port: int = 0):
        # ... existing init code ...
        if api_port:
            self.API_PORT = api_port
        else:
            try:
                from core.config import get_config
                self.API_PORT = get_config()['paths'].get('gpt_sovits_port', 9880)
            except Exception:
                self.API_PORT = 9880
        self.API_BASE = f"http://127.0.0.1:{self.API_PORT}"
```

注意：需要将 `API_PORT` 和 `API_BASE` 从类属性改为实例属性。同时将 `-p` 参数和 `-a` 参数中引用的 `self.API_PORT` 保持不变（已经是实例引用）。

- [ ] **Step 3: Commit**

```bash
cd E:/Proj/pet_buddy
git add python-service/memory/memory_system.py python-service/tts/gpt_sovits_engine.py
git commit -m "fix(config): remove hardcoded embedding path and GPT-SoVITS port"
```

---

### Task 4: 前端 api.js — 统一 API 调用

**Files:**
- Create: `renderer/src/utils/api.js`

- [ ] **Step 1: 创建 api.js**

创建 `renderer/src/utils/api.js`：

```javascript
/**
 * 统一 API 调用基地址管理
 *
 * 所有组件从此处导入 apiFetch，不再各自拼接 http://127.0.0.1:${port}
 *
 * 用法：
 *   import { apiFetch, getApiBase } from '@/utils/api'
 *   const res = await apiFetch('/api/chat', { method: 'POST', body: ... })
 */

let _baseUrl = null

export async function getApiBase () {
  if (_baseUrl) return _baseUrl
  const port = await window.electronAPI?.getPythonPort?.() || 18765
  _baseUrl = `http://127.0.0.1:${port}`
  return _baseUrl
}

export async function apiFetch (path, options = {}) {
  const base = await getApiBase()
  return fetch(`${base}${path}`, options)
}

/**
 * 获取完整 API URL（用于非 fetch 场景，如 Audio src）
 */
export async function apiUrl (path) {
  const base = await getApiBase()
  return `${base}${path}`
}
```

- [ ] **Step 2: Commit**

```bash
cd E:/Proj/pet_buddy
git add renderer/src/utils/api.js
git commit -m "feat(config): add unified apiFetch utility for frontend API calls"
```

---

### Task 5: 前端组件硬编码替换 — 核心组件

**Files:**
- Modify: `renderer/src/App.vue`
- Modify: `renderer/src/components/InputPanel.vue`
- Modify: `renderer/src/components/VoiceRecorder.vue`
- Modify: `renderer/src/components/DreamDiary.vue`

每个文件的改造模式相同：
1. 添加 `import { apiFetch, apiUrl } from '@/utils/api'`
2. 删除本地 `pythonPort` 变量和 `getPythonPort` 调用
3. 将 `fetch(`http://127.0.0.1:${port}/api/xxx`, ...)` 替换为 `apiFetch('/api/xxx', ...)`

- [ ] **Step 1: App.vue**

在 `renderer/src/App.vue` 中：

添加 import：
```javascript
import { apiFetch } from './utils/api'
```

将 `doInteract` 函数中的：
```javascript
  const port = await window.electronAPI?.getPythonPort?.() || 18765
  ...
  const res = await fetch(`http://127.0.0.1:${port}/api/pet/interact/${action}`, { method: 'POST' })
```
替换为：
```javascript
  const res = await apiFetch(`/api/pet/interact/${action}`, { method: 'POST' })
```

对所有其他 fetch 调用做相同替换（如 plugin session clear）。

- [ ] **Step 2: InputPanel.vue**

添加 import `apiFetch`，删除 `getPythonPort` 函数，将：
```javascript
const response = await fetch(`http://localhost:${await getPythonPort()}/api/chat`, {
```
替换为：
```javascript
const response = await apiFetch('/api/chat', {
```

- [ ] **Step 3: VoiceRecorder.vue**

添加 import `apiFetch`，删除 `let pythonPort = 18765` 和 onMounted 中的 port 获取。

将所有 `fetch(`http://127.0.0.1:${pythonPort}/api/...`)` 替换为 `apiFetch('/api/...')`。涉及的端点：
- `/api/stt`
- `/api/chat`
- `/api/tts`
- `/api/mic/start`
- `/api/mic/stop`
- `/api/mic/cancel`

- [ ] **Step 4: DreamDiary.vue**

添加 import `{ apiFetch, apiUrl }`，将：
```javascript
const port = await window.electronAPI?.getPythonPort?.() || 18765
const res = await fetch(`http://127.0.0.1:${port}/api/dream/history`)
```
替换为：
```javascript
const res = await apiFetch('/api/dream/history')
```

图片 URL 替换：
```javascript
image_url: d.image_path
  ? `http://127.0.0.1:${port}/api/dream/image/${d.image_path.split('/').pop()}`
  : null,
```
替换为：
```javascript
image_url: d.image_path
  ? await apiUrl(`/api/dream/image/${d.image_path.split('/').pop()}`)
  : null,
```

- [ ] **Step 5: Commit**

```bash
cd E:/Proj/pet_buddy
git add renderer/src/App.vue renderer/src/components/InputPanel.vue renderer/src/components/VoiceRecorder.vue renderer/src/components/DreamDiary.vue
git commit -m "fix(config): replace hardcoded API URLs in core components with apiFetch"
```

---

### Task 6: 前端组件硬编码替换 — 其余组件

**Files:**
- Modify: `renderer/src/components/MemoryPanel.vue`
- Modify: `renderer/src/components/VoiceManager.vue`
- Modify: `renderer/src/components/SettingsPanel.vue`
- Modify: `renderer/src/components/VoicePackageWizard.vue`
- Modify: `renderer/src/composables/usePetAttributeTicker.js`
- Modify: `renderer/src/composables/useEmotionObserver.js`
- Modify: `renderer/src/plugins/flirt/FlirtPlugin.vue`
- Modify: `renderer/src/plugins/search/SearchPlugin.vue`

所有文件同样的模式：导入 `apiFetch`/`apiUrl`，替换硬编码 fetch。

- [ ] **Step 1: MemoryPanel.vue**

添加 `import { apiFetch } from '@/utils/api'`，删除 `pythonPort` ref 和 port 获取逻辑，替换所有 `fetch(`http://127.0.0.1:${pythonPort.value}/api/...`)` 为 `apiFetch('/api/...')`。

- [ ] **Step 2: VoiceManager.vue**

同上模式。替换涉及的端点：`/api/tts/voices`、`/api/tts/voices/{id}/activate`、`/api/tts`、`/api/tts/voices/{id}` DELETE。

- [ ] **Step 3: SettingsPanel.vue**

同上模式。替换 `/api/emotion` 调用。

- [ ] **Step 4: VoicePackageWizard.vue**

同上模式。替换 `/api/voice-clone/upload`、`/api/voice-clone/train`、`/api/tts/voices`、`/api/tts`。

- [ ] **Step 5: usePetAttributeTicker.js**

删除 `const API_BASE = 'http://127.0.0.1'` 和 `let port = 18765` 和 `getPort()` 函数。

添加 `import { apiFetch } from '../utils/api'`。

将所有 `fetch(`${API_BASE}:${p}/api/...`)` 替换为 `apiFetch('/api/...')`。

- [ ] **Step 6: useEmotionObserver.js**

添加 import，将：
```javascript
const pythonPort = await window.electronAPI?.getPythonPort?.() || 18765
...
const res = await fetch(`http://127.0.0.1:${pythonPort}/api/emotion`, {
```
替换为：
```javascript
const res = await apiFetch('/api/emotion', {
```

- [ ] **Step 7: FlirtPlugin.vue + SearchPlugin.vue**

插件使用 `window.pluginAPI` 而非 `window.electronAPI`。为插件场景，在 `api.js` 中已兼容（`getPythonPort` fallback 到 18765）。

添加 import `apiFetch`，替换所有 `fetch(`http://127.0.0.1:${pythonPort}/api/...`)` 为 `apiFetch('/api/...')`。

注意：插件中 `window.pluginAPI?.getPythonPort` 需要在 `api.js` 的 `getApiBase` 中也检查。修改 `api.js`：

```javascript
export async function getApiBase () {
  if (_baseUrl) return _baseUrl
  const port = await window.electronAPI?.getPythonPort?.()
    || await window.pluginAPI?.getPythonPort?.()
    || 18765
  _baseUrl = `http://127.0.0.1:${port}`
  return _baseUrl
}
```

- [ ] **Step 8: Commit**

```bash
cd E:/Proj/pet_buddy
git add renderer/src/components/ renderer/src/composables/ renderer/src/plugins/ renderer/src/utils/api.js
git commit -m "fix(config): replace all remaining hardcoded API URLs with apiFetch"
```

---

### Task 7: .gitignore + 安全清理

**Files:**
- Create: `.gitignore`
- Modify: `python-service/config.json` — 清除 API key

- [ ] **Step 1: 创建 .gitignore**

创建项目根目录 `.gitignore`：

```
# 依赖
node_modules/
__pycache__/
*.pyc

# 敏感配置（用户自己的配置文件）
python-service/config.json
python-service/.env
*.env
!*.env.example

# 数据目录
python-service/data/

# 构建产物
dist/

# IDE
.vscode/
.idea/

# 系统文件
.DS_Store
Thumbs.db

# npm 缓存
.npm-cache/
```

- [ ] **Step 2: 清除 config.json 中的 API key**

将 `python-service/config.json` 中的 `"api_key": "sk-3e169ba45e0a4f45a5fb00fe2dbfbe35"` 改为 `"api_key": ""`。

注意：由于 .gitignore 生效后 config.json 不再被追踪，需要先清除再添加 gitignore。执行顺序：
1. 先修改 config.json 清空 api_key
2. 提交这个修改
3. 然后添加 .gitignore 将 config.json 排除
4. `git rm --cached python-service/config.json` 停止追踪

- [ ] **Step 3: Commit 清除 API key**

```bash
cd E:/Proj/pet_buddy
git add python-service/config.json
git commit -m "security: remove exposed API key from config.json"
```

- [ ] **Step 4: Commit .gitignore 并停止追踪敏感文件**

```bash
cd E:/Proj/pet_buddy
git add .gitignore
git rm --cached python-service/config.json python-service/.env 2>/dev/null
git commit -m "chore: add .gitignore, stop tracking config.json and .env"
```

---

### Task 8: 部署文档

**Files:**
- Create: `docs/发布部署/配置说明.md`
- Create: `docs/发布部署/部署指南.md`

- [ ] **Step 1: 创建配置说明文档**

创建 `docs/发布部署/配置说明.md`：

```markdown
# ralph-buddy 配置说明

## 配置文件

| 文件 | 位置 | 是否提交 git | 说明 |
|------|------|-------------|------|
| config.example.json | python-service/ | 是 | 配置模板，复制为 config.json 使用 |
| config.json | python-service/ | 否 | 实际配置文件（含你的 API key） |
| .env.example | python-service/ | 是 | 环境变量模板 |
| .env | python-service/ | 否 | 实际环境变量文件 |

## 配置项清单

### LLM 对话服务

| 配置键 | 环境变量 | 默认值 | 必填 | 说明 |
|--------|----------|--------|------|------|
| llm.provider | — | openai | 否 | LLM 提供商（openai 兼容格式） |
| llm.base_url | — | (空) | 是 | API 地址，如 https://api.deepseek.com/v1 |
| llm.api_key | LLM_API_KEY | (空) | **是** | API 密钥。**敏感**，建议写 .env |
| llm.model | — | deepseek-chat | 否 | 模型名称 |

### AI 绘图服务

| 配置键 | 环境变量 | 默认值 | 必填 | 说明 |
|--------|----------|--------|------|------|
| image.provider | — | siliconflow | 否 | 绘图提供商 |
| image.base_url | — | https://api.siliconflow.cn/v1 | 否 | API 地址 |
| image.api_key | IMAGE_API_KEY | (空) | 选填 | 绘图密钥。不填则跳过梦境图片生成 |
| image.model | — | FLUX.1-schnell | 否 | 绘图模型 |

### 服务配置

| 配置键 | 环境变量 | 默认值 | 必填 | 说明 |
|--------|----------|--------|------|------|
| server.host | PYTHON_HOST | 127.0.0.1 | 否 | 服务绑定地址 |
| server.port | PYTHON_PORT | 18765 | 否 | 服务端口 |

### 本地模型路径

| 配置键 | 环境变量 | 默认值 | 必填 | 说明 |
|--------|----------|--------|------|------|
| paths.whisper_model | WHISPER_MODEL_PATH | (空) | 否 | Whisper STT 本地模型路径。空=自动下载 |
| paths.embedding_model | EMBEDDING_MODEL_PATH | (空) | 否 | 向量 embedding 模型路径。空=使用默认 |
| paths.data_dir | DATA_DIR | data | 否 | 数据存储目录（记忆、梦境等） |
| paths.gpt_sovits_dir | GPT_SOVITS_DIR | (空) | 否 | GPT-SoVITS 安装目录。空=跳过声音克隆 |
| paths.gpt_sovits_port | GPT_SOVITS_PORT | 9880 | 否 | GPT-SoVITS 子进程端口 |

### 语音合成

| 配置键 | 默认值 | 说明 |
|--------|--------|------|
| tts.provider | edge | 默认 Edge TTS（在线） |
| tts.voice | zh-CN-XiaoxiaoNeural | 语音名称 |

### 语音识别

| 配置键 | 默认值 | 说明 |
|--------|--------|------|
| stt.provider | whisper | faster-whisper 本地识别 |
| stt.model | small | 模型大小：tiny/base/small/medium/large |

### 宠物配置

| 配置键 | 默认值 | 说明 |
|--------|--------|------|
| pet.name | 来福 | 宠物名称 |
| pet.personality | 活泼、忠诚... | 性格描述 |
| pet.obedience | 60 | 初始顺从度 0-100 |
| pet.snark | 30 | 初始毒舌值 0-100 |

## 配置加载规则

优先级从高到低：**环境变量 > .env 文件 > config.json**

敏感配置（API key）建议只写在 .env 中，不要写入 config.json。
```

- [ ] **Step 2: 创建部署指南**

创建 `docs/发布部署/部署指南.md`：

```markdown
# ralph-buddy 部署指南

## 快速开始

### 1. 克隆项目

```bash
git clone <repo-url>
cd pet_buddy
```

### 2. 配置

```bash
# 复制配置模板
cp python-service/config.example.json python-service/config.json
cp python-service/.env.example python-service/.env

# 编辑 .env，填入 API key
# 必填：LLM_API_KEY
# 选填：IMAGE_API_KEY（梦境绘图）、模型路径
```

### 3. 安装依赖

```bash
# Python 依赖
cd python-service
pip install -r requirements.txt

# Node 依赖
cd ..
npm install
```

### 4. 启动

```bash
# 开发模式
npm run dev

# 生产模式
npm run build
npm start
```

## 配置方式

### 方式一：编辑 .env（推荐）

```bash
LLM_API_KEY=sk-your-key-here
WHISPER_MODEL_PATH=/path/to/faster-whisper-small
```

### 方式二：编辑 config.json

直接修改 `python-service/config.json` 中的对应字段。

### 方式三：环境变量（Docker/CI）

```bash
export LLM_API_KEY=sk-your-key-here
export PYTHON_PORT=8000
```

## 本地模型（可选）

### Whisper STT 模型

不配置路径时自动从 HuggingFace 下载（首次需联网）。

手动安装：
```bash
# 设置 .env
WHISPER_MODEL_PATH=/path/to/faster-whisper-small
```

### Embedding 模型

不配置时使用 Chroma 默认 embedding。

### GPT-SoVITS 声音克隆

不配置时跳过，使用 Edge TTS 在线语音。

## 目录结构

```
pet_buddy/
├── electron/              # Electron 主进程
├── renderer/              # Vue 前端
├── python-service/        # Python 后端
│   ├── config.json        # 你的配置（不提交 git）
│   ├── config.example.json # 配置模板
│   ├── .env               # 你的环境变量（不提交 git）
│   ├── .env.example       # 环境变量模板
│   └── data/              # 数据目录（记忆、梦境等）
└── docs/                  # 文档
```
```

- [ ] **Step 3: Commit**

```bash
cd E:/Proj/pet_buddy
git add docs/发布部署/
git commit -m "docs: add deployment guide and configuration reference"
```

---

### Task 9: 集成验证

- [ ] **Step 1: 验证 config 模块加载**

```bash
cd E:/Proj/pet_buddy/python-service
python -c "from core.config import load_config; c=load_config(); print(f'port={c[\"server\"][\"port\"]}, host={c[\"server\"][\"host\"]}')"
```

Expected: `port=18765, host=127.0.0.1`

- [ ] **Step 2: 验证无 E:\ 硬编码**

```bash
cd E:/Proj/pet_buddy
grep -rn "E:\\\\" python-service/*.py python-service/**/*.py --include="*.py" | grep -v test_ | grep -v __pycache__ | grep -v tools/
```

Expected: 无输出（生产代码中不再有 E:\）

- [ ] **Step 3: 验证现有测试不受影响**

```bash
cd E:/Proj/pet_buddy/python-service
python -m pytest tests/test_emotion.py tests/test_dream_engine.py -v 2>&1 | tail -5
```

Expected: 全部通过

- [ ] **Step 4: 验证 .gitignore 生效**

```bash
cd E:/Proj/pet_buddy
git status | grep config.json
```

Expected: config.json 不再出现在 tracked files 中

- [ ] **Step 5: Final commit**

```bash
cd E:/Proj/pet_buddy
git add -A
git commit -m "feat: ralph-buddy v1.0 release configuration complete"
```
