# ralph-buddy v1.0 发布版构造设计

> 消除硬编码、统一配置管理、保护敏感信息，使项目可直接部署、开箱即用。

## 总体策略

**三层配置加载优先级**：环境变量 > .env 文件 > config.json 默认值

```
启动时加载顺序：
1. 读取 config.json（结构化配置 + 默认值）
2. 读取 .env 文件（覆盖敏感配置和路径）
3. 读取环境变量（最终覆盖，用于 Docker/CI）
```

## 审计结果

| 类别 | 数量 | 严重度 |
|------|------|--------|
| API key 明文提交 | 1（DeepSeek sk-xxx） | 安全 |
| Windows 绝对路径 (E:\) | 3 处生产代码 + 2 处测试 | 致命 |
| 硬编码端口 18765 | 15+ 文件 | 高 |
| 硬编码 127.0.0.1 | 8 个前端组件 | 高 |
| config.json/.env 未被 .gitignore 保护 | — | 安全 |

### 需要修改的文件

**Python 后端（生产代码）：**
- `python-service/main.py` — 硬编码 whisper 模型路径 `E:\LLM\...`、绑定地址、端口
- `python-service/memory/memory_system.py` — 硬编码 embedding 模型路径 `E:\LLM\...`
- `python-service/tts/gpt_sovits_engine.py` — 硬编码 API 端口 9880
- `python-service/config.json` — 明文 API key

**前端（8 个组件硬编码 IP/端口）：**
- `renderer/src/App.vue`
- `renderer/src/components/InputPanel.vue`
- `renderer/src/components/VoiceRecorder.vue`
- `renderer/src/components/DreamDiary.vue`
- `renderer/src/components/DreamBubble.vue`
- `renderer/src/components/MemoryPanel.vue`
- `renderer/src/components/VoiceManager.vue`
- `renderer/src/components/SettingsPanel.vue`
- `renderer/src/composables/usePetAttributeTicker.js`
- `renderer/src/composables/useEmotionObserver.js`

**Electron：**
- `electron/main.js` — 硬编码 dev 端口 5173、Python 端口 18765

**测试文件：**
- `python-service/tests/test_gpt_sovits.py`
- `python-service/tests/test_mic.py`

## 配置文件体系

### config.json — 结构化默认配置

提交到 git 的是 `config.example.json`（无敏感信息），用户复制为 `config.json` 后填入自己的值。

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

### .env — 敏感信息和本机路径

不提交 git，提交 `.env.example` 作为模板。

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

### 环境变量覆盖规则

| 环境变量 | 覆盖的 config.json 字段 | 说明 |
|----------|------------------------|------|
| `LLM_API_KEY` | `llm.api_key` | LLM 服务密钥 |
| `IMAGE_API_KEY` | `image.api_key` | 绘图服务密钥 |
| `PYTHON_HOST` | `server.host` | 服务绑定地址 |
| `PYTHON_PORT` | `server.port` | 服务端口 |
| `WHISPER_MODEL_PATH` | `paths.whisper_model` | Whisper 本地模型路径 |
| `EMBEDDING_MODEL_PATH` | `paths.embedding_model` | 向量 embedding 模型路径 |
| `GPT_SOVITS_DIR` | `paths.gpt_sovits_dir` | GPT-SoVITS 安装目录 |
| `GPT_SOVITS_PORT` | `paths.gpt_sovits_port` | GPT-SoVITS API 端口 |
| `DATA_DIR` | `paths.data_dir` | 数据目录（记忆、梦境图片等） |

## Python 端统一配置加载

### 新建 core/config.py

```python
"""
统一配置加载器
加载顺序：config.json → .env → 环境变量
"""

def load_config() -> dict:
    cfg = _read_config_json()
    load_dotenv()
    _apply_env_overrides(cfg)
    _resolve_paths(cfg)
    return cfg

def get_config() -> dict:
    """全局单例获取配置"""
```

所有模块通过 `from core.config import get_config` 获取配置，不再自行读文件或硬编码路径。

### 路径为空时的降级行为

| 路径配置 | 为空时的行为 |
|----------|-------------|
| `whisper_model` | 自动从 HuggingFace Mirror 下载到 `~/.cache/whisper/` |
| `embedding_model` | 使用 Chroma 默认 embedding（首次自动下载） |
| `gpt_sovits_dir` | 跳过克隆语音功能，使用 Edge TTS 兜底 |
| `data_dir` | 默认为 `python-service/data/`（相对路径） |

## 前端端口统一

### 新建 renderer/src/utils/api.js

```javascript
/**
 * 统一 API 调用基地址管理
 * 所有组件从此处获取 base URL，不再各自拼接
 */
let _baseUrl = null

export async function getApiBase() {
  if (_baseUrl) return _baseUrl
  const port = await window.electronAPI?.getPythonPort?.() || 18765
  _baseUrl = `http://127.0.0.1:${port}`
  return _baseUrl
}

export async function apiFetch(path, options = {}) {
  const base = await getApiBase()
  return fetch(`${base}${path}`, options)
}
```

所有 Vue 组件和 composable 从 `api.js` 导入 `apiFetch`，替换原来的 `fetch(`http://127.0.0.1:${port}...`)` 模式。

### 需要替换的组件

8 个 Vue 组件 + 2 个 composable 中的所有 `fetch(`http://127.0.0.1:${port}/api/...`)` 替换为 `apiFetch('/api/...')`。

## Git 安全改造

### .gitignore 新增

```
# 敏感配置
python-service/config.json
python-service/.env
*.env

# 数据目录
python-service/data/
```

### 新增模板文件

- `python-service/config.example.json` — 带注释的配置模板，所有 api_key 字段为空
- `python-service/.env.example` — 环境变量模板

### API key 轮换

当前 `config.json` 中的 DeepSeek API key `sk-3e169ba45e0a4f45a5fb00fe2dbfbe35` 已提交到 git 历史。需要：
1. 在 DeepSeek 控制台轮换此 key
2. 新 key 只写入 .env，不再进入 git

## 输出物清单

| 文件 | 说明 |
|------|------|
| `python-service/core/__init__.py` | 新包 |
| `python-service/core/config.py` | 统一配置加载模块 |
| `python-service/config.example.json` | 配置模板（无敏感信息） |
| `python-service/.env.example` | 环境变量模板 |
| `renderer/src/utils/api.js` | 前端 API base URL 统一管理 |
| `docs/发布部署/配置说明.md` | 完整配置项清单文档 |
| `docs/发布部署/部署指南.md` | 部署步骤说明 |
| `.gitignore` 更新 | 保护敏感文件 |

## 不做的事情

- 不改功能逻辑，只做配置化和路径消除
- 不新增需求
- 不改 `tools/GPT-SoVITS/` 目录（第三方工具原样保留）
- 不做 Docker 化（后续可选）
- 不做多环境切换（dev/staging/prod），当前只需单环境配置化
