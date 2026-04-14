# Pet Attribute System & Dream Engine Design

## Overview

为来福增加完整的 6 属性系统和做梦功能。属性影响对话风格和行为序列权重，做梦时整理记忆、更新用户画像、调整属性，使来福逐渐适配主人。

## 属性定义

| 属性 | 含义 | 范围 | 默认值 |
|------|------|------|--------|
| HEALTH | 身体状态，过低萎靡/混乱 | 0-100 | 80 |
| MOOD | 心情状态，过低冷漠/嗜睡 | 0-100 | 70 |
| ENERGY | 精力值，互动消耗，休息恢复 | 0-100 | 80 |
| AFFECTION | 与主人的羁绊程度 | 0-100 | 50 |
| OBEDIENCE | 对指令的响应程度 | 0-100 | 60 |
| SNARK | 语言犀利程度 | 0-100 | 30 |

### 自然变化

运行时每 10 分钟 tick 一次：

| 属性 | 运行时 tick | 备注 |
|------|------------|------|
| HEALTH | -1 | 长期不互动/不休息 |
| MOOD | -2 | 自然下降 |
| ENERGY | -3 | 活动消耗 |
| AFFECTION | -0.5 | 缓慢下降 |
| OBEDIENCE | 0 | 仅做梦调整 |
| SNARK | 0 | 仅做梦调整 |

离线变化（每小时）：

| 属性 | 离线/小时 | 备注 |
|------|----------|------|
| HEALTH | -0.5 | 缓慢下降 |
| MOOD | -1 | 想主人 |
| ENERGY | +5 | 休息恢复，上限 100 |
| AFFECTION | -1 | 分离焦虑 |
| OBEDIENCE | 0 | 无 |
| SNARK | 0 | 无 |

### 互动影响

| 互动类型 | HEALTH | MOOD | ENERGY | AFFECTION | OBEDIENCE | SNARK |
|---------|--------|------|--------|-----------|-----------|-------|
| 对话互动 | 0 | +3 | -2 | +2 | 0 | 0 |
| 玩耍行为 | 0 | +5 | -5 | +1 | 0 | 0 |
| 被回应 | 0 | +2 | 0 | +3 | +1 | 0 |
| 被忽视（长时间无互动） | 0 | -5 | 0 | -2 | 0 | 0 |

OBEDIENCE 和 SNARK 不受日常互动影响，仅通过做梦时 LLM 基于记忆调整。

## 做梦系统

### 触发条件

- 来福处于 sleep 状态
- 距上次做梦 ≥ 4 小时

### 流程

```
1. 收集素材
   - 短期记忆（近期对话）
   - 向量检索相关中期记忆
   - 当前用户画像（user_profile）
   - 当前 6 项属性值

2. LLM 调用（单次请求，三合一任务）
   - 生成梦境描述（1-2 句，符合来福性格）
   - 记忆整理：提取/更新用户画像 key-value
   - 属性调整：基于相处模式输出各属性 delta

3. 写入结果
   - 更新 user_profile 表
   - 更新 pet_attributes 表
   - 压缩短期记忆到中期
   - 记录梦境到 events 表（importance=3）

4. 返回前端
   - 梦境文本（醒来后气泡展示）
   - 属性变化 delta 值
```

### LLM Prompt 设计

系统提示要求 LLM 返回 JSON：

```json
{
  "dream_text": "来福梦到和主人一起在草地上奔跑...",
  "profile_updates": [
    {"key": "favorite_topic", "value": "编程"},
    {"key": "interaction_style", "value": "喜欢聊天但有时很忙"}
  ],
  "attribute_deltas": {
    "health": 0,
    "mood": 3,
    "energy": 0,
    "affection": 5,
    "obedience": 2,
    "snark": -1
  },
  "reasoning": "主人最近经常陪来福聊天，来福更信任主人了"
}
```

属性 delta 限制在 [-10, +10] 范围内，防止单次做梦剧烈波动。

## 存储设计

### SQLite 新增表 `pet_attributes`

```sql
CREATE TABLE IF NOT EXISTS pet_attributes (
    key TEXT PRIMARY KEY,
    value REAL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

存储 6 个属性 + `last_tick_time` + `last_dream_time`。

## 后端架构

### 新增文件

- `python-service/agent/pet_attributes.py` — 属性管理类
  - `PetAttributeManager`
  - `load()` / `save()` — SQLite 读写
  - `tick()` — 运行时衰减（每 10 分钟调用）
  - `apply_offline(hours)` — 启动时离线变化计算
  - `apply_interaction(interaction_type)` — 互动属性变化
  - `apply_dream_delta(deltas)` — 做梦调整
  - `get_all()` — 返回所有属性字典
  - `get_prompt_hints()` — 生成注入 system prompt 的属性描述

- `python-service/agent/dream_engine.py` — 做梦引擎
  - `DreamEngine`
  - `can_dream()` — 冷却时间检查（≥ 4h）
  - `dream()` — 执行完整做梦流程
  - 依赖：`memory_system`, `pet_attributes`, `llm_client`

### 修改文件

- `python-service/agent/dog_agent.py`
  - 引入 `PetAttributeManager`
  - system prompt 中注入全部 6 个属性的描述
  - 对话后调用 `apply_interaction("chat")`

- `python-service/main.py`
  - 新增端点：
    - `GET /api/pet/attributes` — 获取当前属性
    - `POST /api/pet/attributes/tick` — 前端定时调用 tick
    - `POST /api/pet/dream` — 触发做梦
  - 启动时：加载属性 → 计算离线变化 → 保存

- `python-service/memory/memory_system.py`
  - `_init_db()` 中新增 `pet_attributes` 表 DDL

## 前端架构

### 修改文件

- `renderer/src/stores/pet.js`
  - 新增 `health`, `affection` 响应式属性
  - 新增 `fetchAttributes()` — 从后端拉取
  - 新增 `syncAttributes()` — 推送到后端
  - 移除前端本地的属性计算逻辑，改为后端驱动

- `renderer/src/composables/useBehaviorSequencer.js`
  - 行为权重受属性影响：
    - `ENERGY < 20` → sleep ×3, excited ×0.2
    - `MOOD < 30` → sad ×3, flatter ×0.5
    - `MOOD > 80` → excited ×2, happy_run ×2
    - `HEALTH < 30` → 活跃行为 ×0.3, sleep ×2
    - `AFFECTION > 80` → flatter ×2, lickScreen ×2

### 新增文件

- `renderer/src/composables/usePetAttributeTicker.js`
  - 每 10 分钟调用 `POST /api/pet/attributes/tick`
  - 拉取最新属性更新 store
  - 应用启动时调用一次获取初始值

## 对话系统集成

属性注入 system prompt 示例：

```
【来福当前状态】
健康值: 75/100 — 状态还不错
心情: 45/100 — 有点低落
精力: 30/100 — 比较累了
亲密度: 82/100 — 和主人很亲近
顺从度: 55/100 — 有时候会任性
毒舌值: 40/100 — 偶尔调侃

请根据以上状态调整你的回应风格和行为。
```
