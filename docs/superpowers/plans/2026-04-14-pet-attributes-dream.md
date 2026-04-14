# Pet Attribute System & Dream Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a 6-attribute system (HEALTH, MOOD, ENERGY, AFFECTION, OBEDIENCE, SNARK) with persistence in SQLite, natural decay/recovery, interaction effects, and a dream engine that consolidates memory + adjusts attributes when the pet sleeps.

**Architecture:** Backend-driven attributes stored in SQLite `pet_attributes` table. `PetAttributeManager` handles load/save/tick/offline/interaction logic. `DreamEngine` triggers during sleep (4h cooldown), calls LLM to generate dream text + profile updates + attribute deltas. Frontend fetches attributes from backend, feeds them to behavior sequencer for weight modulation.

**Tech Stack:** Python 3.10 (FastAPI, SQLite, AsyncOpenAI), Vue 3 (Pinia, Composables)

---

### Task 1: PetAttributeManager — Core Logic

**Files:**
- Create: `python-service/agent/pet_attributes.py`
- Create: `python-service/tests/test_pet_attributes.py`

- [ ] **Step 1: Write failing tests for PetAttributeManager**

Create `python-service/tests/test_pet_attributes.py`:

```python
import pytest
import asyncio
import os
import sys
import sqlite3
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from agent.pet_attributes import PetAttributeManager, DEFAULTS, TICK_DELTAS, OFFLINE_DELTAS, INTERACTION_DELTAS


@pytest.fixture
def db(tmp_path):
    """Create a temporary SQLite database with pet_attributes table."""
    db_path = str(tmp_path / 'memory.db')
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pet_attributes (
            key   TEXT PRIMARY KEY,
            value REAL,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()
    return db_path


def test_load_defaults(db):
    mgr = PetAttributeManager(db)
    mgr.load()
    attrs = mgr.get_all()
    assert attrs['health'] == DEFAULTS['health']
    assert attrs['mood'] == DEFAULTS['mood']
    assert attrs['energy'] == DEFAULTS['energy']
    assert attrs['affection'] == DEFAULTS['affection']
    assert attrs['obedience'] == DEFAULTS['obedience']
    assert attrs['snark'] == DEFAULTS['snark']


def test_save_and_reload(db):
    mgr = PetAttributeManager(db)
    mgr.load()
    mgr.attrs['health'] = 42.5
    mgr.save()

    mgr2 = PetAttributeManager(db)
    mgr2.load()
    assert mgr2.attrs['health'] == 42.5


def test_tick_applies_deltas(db):
    mgr = PetAttributeManager(db)
    mgr.load()
    mgr.attrs['health'] = 50
    mgr.attrs['mood'] = 50
    mgr.attrs['energy'] = 50
    mgr.attrs['affection'] = 50
    mgr.attrs['obedience'] = 60
    mgr.attrs['snark'] = 30
    mgr.tick()
    assert mgr.attrs['health'] == 50 + TICK_DELTAS['health']
    assert mgr.attrs['mood'] == 50 + TICK_DELTAS['mood']
    assert mgr.attrs['energy'] == 50 + TICK_DELTAS['energy']
    assert mgr.attrs['affection'] == 50 + TICK_DELTAS['affection']
    assert mgr.attrs['obedience'] == 60  # no tick change
    assert mgr.attrs['snark'] == 30      # no tick change


def test_tick_clamps_to_bounds(db):
    mgr = PetAttributeManager(db)
    mgr.load()
    mgr.attrs['health'] = 0.5
    mgr.tick()
    assert mgr.attrs['health'] == 0  # clamped at 0


def test_apply_offline(db):
    mgr = PetAttributeManager(db)
    mgr.load()
    mgr.attrs['energy'] = 50
    mgr.attrs['mood'] = 50
    mgr.apply_offline(hours=4)
    assert mgr.attrs['energy'] == min(100, 50 + OFFLINE_DELTAS['energy'] * 4)
    assert mgr.attrs['mood'] == 50 + OFFLINE_DELTAS['mood'] * 4


def test_apply_offline_clamps(db):
    mgr = PetAttributeManager(db)
    mgr.load()
    mgr.attrs['energy'] = 90
    mgr.apply_offline(hours=10)  # +50 would exceed 100
    assert mgr.attrs['energy'] == 100


def test_apply_interaction_chat(db):
    mgr = PetAttributeManager(db)
    mgr.load()
    mgr.attrs['mood'] = 50
    mgr.attrs['energy'] = 50
    mgr.attrs['affection'] = 50
    mgr.apply_interaction('chat')
    deltas = INTERACTION_DELTAS['chat']
    assert mgr.attrs['mood'] == 50 + deltas['mood']
    assert mgr.attrs['energy'] == 50 + deltas['energy']
    assert mgr.attrs['affection'] == 50 + deltas['affection']


def test_apply_interaction_unknown_type(db):
    mgr = PetAttributeManager(db)
    mgr.load()
    old = mgr.get_all().copy()
    mgr.apply_interaction('unknown_type')
    assert mgr.get_all() == old  # no change


def test_apply_dream_delta(db):
    mgr = PetAttributeManager(db)
    mgr.load()
    mgr.attrs['obedience'] = 50
    mgr.attrs['snark'] = 50
    mgr.apply_dream_delta({'obedience': 5, 'snark': -3, 'mood': 2})
    assert mgr.attrs['obedience'] == 55
    assert mgr.attrs['snark'] == 47
    assert mgr.attrs['mood'] == DEFAULTS['mood'] + 2


def test_apply_dream_delta_clamped(db):
    mgr = PetAttributeManager(db)
    mgr.load()
    mgr.attrs['obedience'] = 50
    mgr.apply_dream_delta({'obedience': 15})  # exceeds [-10,+10] → clamped to +10
    assert mgr.attrs['obedience'] == 60


def test_get_prompt_hints(db):
    mgr = PetAttributeManager(db)
    mgr.load()
    hints = mgr.get_prompt_hints()
    assert '健康值' in hints
    assert '心情' in hints
    assert '精力' in hints
    assert '亲密度' in hints
    assert '顺从度' in hints
    assert '毒舌值' in hints


def test_last_dream_time(db):
    mgr = PetAttributeManager(db)
    mgr.load()
    # Default: no dream yet → can dream
    assert mgr.get_last_dream_time() is None

    now = datetime.now()
    mgr.set_last_dream_time(now)
    mgr.save()

    mgr2 = PetAttributeManager(db)
    mgr2.load()
    loaded = mgr2.get_last_dream_time()
    assert loaded is not None
    assert abs((loaded - now).total_seconds()) < 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd python-service && python -m pytest tests/test_pet_attributes.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent.pet_attributes'`

- [ ] **Step 3: Implement PetAttributeManager**

Create `python-service/agent/pet_attributes.py`:

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PetAttributeManager — 来福六属性管理

属性存储在 SQLite pet_attributes 表中，支持：
- 运行时 tick 衰减
- 离线时长变化
- 互动效果
- 做梦 delta（由 DreamEngine 调用）
"""

import sqlite3
from datetime import datetime
from typing import Optional

# 属性默认值
DEFAULTS = {
    'health':    80.0,
    'mood':      70.0,
    'energy':    80.0,
    'affection': 50.0,
    'obedience': 60.0,
    'snark':     30.0,
}

# 运行时每 10 分钟 tick 变化
TICK_DELTAS = {
    'health':    -1.0,
    'mood':      -2.0,
    'energy':    -3.0,
    'affection': -0.5,
    'obedience':  0.0,
    'snark':      0.0,
}

# 离线每小时变化
OFFLINE_DELTAS = {
    'health':    -0.5,
    'mood':      -1.0,
    'energy':    +5.0,
    'affection': -1.0,
    'obedience':  0.0,
    'snark':      0.0,
}

# 互动类型 → 属性变化
INTERACTION_DELTAS = {
    'chat': {
        'health': 0, 'mood': 3, 'energy': -2,
        'affection': 2, 'obedience': 0, 'snark': 0,
    },
    'play': {
        'health': 0, 'mood': 5, 'energy': -5,
        'affection': 1, 'obedience': 0, 'snark': 0,
    },
    'responded': {
        'health': 0, 'mood': 2, 'energy': 0,
        'affection': 3, 'obedience': 1, 'snark': 0,
    },
    'ignored': {
        'health': 0, 'mood': -5, 'energy': 0,
        'affection': -2, 'obedience': 0, 'snark': 0,
    },
}

ATTR_KEYS = list(DEFAULTS.keys())

# 属性中文描述模板
_HINT_LABELS = {
    'health':    '健康值',
    'mood':      '心情',
    'energy':    '精力',
    'affection': '亲密度',
    'obedience': '顺从度',
    'snark':     '毒舌值',
}

def _describe(key: str, val: float) -> str:
    """根据属性值生成简短描述"""
    v = int(val)
    if key == 'health':
        if v >= 70: return '状态不错'
        if v >= 40: return '有点虚弱'
        return '很不舒服'
    if key == 'mood':
        if v >= 70: return '心情很好'
        if v >= 40: return '有点低落'
        return '情绪低迷'
    if key == 'energy':
        if v >= 70: return '精力充沛'
        if v >= 40: return '有点累了'
        return '筋疲力尽'
    if key == 'affection':
        if v >= 70: return '和主人很亲近'
        if v >= 40: return '和主人关系一般'
        return '和主人还不太熟'
    if key == 'obedience':
        if v >= 70: return '很听话'
        if v >= 40: return '有时候会任性'
        return '非常任性'
    if key == 'snark':
        if v >= 70: return '嘴巴很毒'
        if v >= 40: return '偶尔调侃'
        return '说话温柔'
    return ''


class PetAttributeManager:
    """来福属性管理器"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.attrs: dict[str, float] = {}
        self._last_dream_time: Optional[datetime] = None

    def load(self):
        """从 SQLite 加载属性，不存在则写入默认值"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT key, value FROM pet_attributes")
        rows = {r['key']: r['value'] for r in c.fetchall()}

        for key, default in DEFAULTS.items():
            self.attrs[key] = rows.get(key, default)

        # 加载 last_dream_time
        dream_val = rows.get('last_dream_time')
        if dream_val is not None:
            try:
                self._last_dream_time = datetime.fromisoformat(str(dream_val))
            except (ValueError, TypeError):
                self._last_dream_time = None
        else:
            self._last_dream_time = None

        conn.close()

        # 如果是首次加载（数据库为空），写入默认值
        if not rows:
            self.save()

    def save(self):
        """将当前属性写入 SQLite"""
        conn = sqlite3.connect(self.db_path)
        now = datetime.now().isoformat()
        for key, val in self.attrs.items():
            conn.execute(
                """INSERT INTO pet_attributes (key, value, updated_at)
                   VALUES (?, ?, ?)
                   ON CONFLICT(key) DO UPDATE SET
                       value=excluded.value,
                       updated_at=excluded.updated_at""",
                (key, val, now),
            )
        # 保存 last_dream_time
        if self._last_dream_time is not None:
            conn.execute(
                """INSERT INTO pet_attributes (key, value, updated_at)
                   VALUES (?, ?, ?)
                   ON CONFLICT(key) DO UPDATE SET
                       value=excluded.value,
                       updated_at=excluded.updated_at""",
                ('last_dream_time', self._last_dream_time.isoformat(), now),
            )
        conn.commit()
        conn.close()

    def _clamp(self):
        """将所有属性限制在 [0, 100]"""
        for key in ATTR_KEYS:
            self.attrs[key] = max(0.0, min(100.0, self.attrs[key]))

    def tick(self):
        """运行时每 10 分钟调用一次，应用自然衰减"""
        for key in ATTR_KEYS:
            self.attrs[key] += TICK_DELTAS[key]
        self._clamp()

    def apply_offline(self, hours: float):
        """启动时根据离线时长计算变化"""
        for key in ATTR_KEYS:
            self.attrs[key] += OFFLINE_DELTAS[key] * hours
        self._clamp()

    def apply_interaction(self, interaction_type: str):
        """应用互动效果"""
        deltas = INTERACTION_DELTAS.get(interaction_type)
        if deltas is None:
            return
        for key in ATTR_KEYS:
            self.attrs[key] += deltas.get(key, 0)
        self._clamp()

    def apply_dream_delta(self, deltas: dict[str, float]):
        """应用做梦调整（每个 delta 限制在 [-10, +10]）"""
        for key, delta in deltas.items():
            if key in self.attrs:
                clamped = max(-10.0, min(10.0, delta))
                self.attrs[key] += clamped
        self._clamp()

    def get_all(self) -> dict[str, float]:
        """返回所有 6 个属性的快照"""
        return {k: self.attrs[k] for k in ATTR_KEYS}

    def get_prompt_hints(self) -> str:
        """生成注入 system prompt 的属性描述文本"""
        lines = ['【来福当前状态】']
        for key in ATTR_KEYS:
            val = self.attrs[key]
            label = _HINT_LABELS[key]
            desc = _describe(key, val)
            lines.append(f'{label}: {int(val)}/100 — {desc}')
        lines.append('')
        lines.append('请根据以上状态调整你的回应风格和行为。')
        return '\n'.join(lines)

    def get_last_dream_time(self) -> Optional[datetime]:
        return self._last_dream_time

    def set_last_dream_time(self, dt: datetime):
        self._last_dream_time = dt
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd python-service && python -m pytest tests/test_pet_attributes.py -v`
Expected: All 12 tests PASS

- [ ] **Step 5: Commit**

```bash
git add python-service/agent/pet_attributes.py python-service/tests/test_pet_attributes.py
git commit -m "feat: add PetAttributeManager with tick/offline/interaction/dream logic"
```

---

### Task 2: Add pet_attributes Table DDL to MemorySystem

**Files:**
- Modify: `python-service/memory/memory_system.py:96-117`

- [ ] **Step 1: Write failing test**

Add to `python-service/tests/test_memory_system.py`:

```python
def test_pet_attributes_table_exists(tmp_memory):
    """pet_attributes table should be created during initialization."""
    c = tmp_memory.conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pet_attributes'")
    assert c.fetchone() is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd python-service && python -m pytest tests/test_memory_system.py::test_pet_attributes_table_exists -v`
Expected: FAIL — table does not exist

- [ ] **Step 3: Add DDL to _init_tables**

In `python-service/memory/memory_system.py`, modify `_init_tables` to add the `pet_attributes` table. Find the existing `executescript` call and add after the `events` table:

```python
    def _init_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS user_profile (
                key        TEXT PRIMARY KEY,
                value      TEXT,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS conversations (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                role       TEXT,
                content    TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                is_summary INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS events (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                content    TEXT,
                importance INTEGER DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS pet_attributes (
                key        TEXT PRIMARY KEY,
                value      REAL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)
        self.conn.commit()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd python-service && python -m pytest tests/test_memory_system.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add python-service/memory/memory_system.py python-service/tests/test_memory_system.py
git commit -m "feat: add pet_attributes table DDL to MemorySystem"
```

---

### Task 3: DreamEngine

**Files:**
- Create: `python-service/agent/dream_engine.py`
- Create: `python-service/tests/test_dream_engine.py`

- [ ] **Step 1: Write failing tests for DreamEngine**

Create `python-service/tests/test_dream_engine.py`:

```python
import pytest
import asyncio
import os
import sys
import json
import sqlite3
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from agent.dream_engine import DreamEngine
from agent.pet_attributes import PetAttributeManager


@pytest.fixture
def db(tmp_path):
    db_path = str(tmp_path / 'memory.db')
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE pet_attributes (
            key TEXT PRIMARY KEY, value REAL,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE user_profile (
            key TEXT PRIMARY KEY, value TEXT,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT, importance INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def attr_mgr(db):
    mgr = PetAttributeManager(db)
    mgr.load()
    return mgr


@pytest.fixture
def mock_memory():
    mem = MagicMock()
    mem.short_term = [
        {"role": "user", "content": "你好来福"},
        {"role": "assistant", "content": "汪！主人好！"},
    ]
    mem.retrieve_relevant = AsyncMock(return_value=["主人喜欢编程"])
    mem._format_profile = MagicMock(return_value="关于主人你记得：\n- 爱好: 编程")
    mem.compress_and_extract = AsyncMock()
    mem.conn = sqlite3.connect(":memory:")
    mem.conn.execute("""CREATE TABLE user_profile (
        key TEXT PRIMARY KEY, value TEXT, updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )""")
    mem.conn.execute("""CREATE TABLE events (
        id INTEGER PRIMARY KEY AUTOINCREMENT, content TEXT,
        importance INTEGER DEFAULT 1, created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )""")
    mem.conn.commit()
    return mem


@pytest.fixture
def mock_llm_caller():
    async def caller(prompt):
        return json.dumps({
            "dream_text": "来福梦到和主人一起散步",
            "profile_updates": [
                {"key": "favorite_activity", "value": "散步"}
            ],
            "attribute_deltas": {
                "mood": 3, "affection": 5, "obedience": 2, "snark": -1
            },
            "reasoning": "主人经常带来福散步"
        })
    return caller


def test_can_dream_no_previous(attr_mgr, mock_memory, mock_llm_caller):
    engine = DreamEngine(mock_memory, attr_mgr, mock_llm_caller)
    assert engine.can_dream() is True


def test_can_dream_too_recent(attr_mgr, mock_memory, mock_llm_caller):
    engine = DreamEngine(mock_memory, attr_mgr, mock_llm_caller)
    attr_mgr.set_last_dream_time(datetime.now())
    assert engine.can_dream() is False


def test_can_dream_after_cooldown(attr_mgr, mock_memory, mock_llm_caller):
    engine = DreamEngine(mock_memory, attr_mgr, mock_llm_caller)
    attr_mgr.set_last_dream_time(datetime.now() - timedelta(hours=5))
    assert engine.can_dream() is True


def test_dream_returns_result(attr_mgr, mock_memory, mock_llm_caller):
    engine = DreamEngine(mock_memory, attr_mgr, mock_llm_caller)
    result = asyncio.get_event_loop().run_until_complete(engine.dream())
    assert result is not None
    assert 'dream_text' in result
    assert result['dream_text'] == '来福梦到和主人一起散步'
    assert 'attribute_deltas' in result


def test_dream_updates_attributes(attr_mgr, mock_memory, mock_llm_caller):
    engine = DreamEngine(mock_memory, attr_mgr, mock_llm_caller)
    old_mood = attr_mgr.attrs['mood']
    old_affection = attr_mgr.attrs['affection']
    asyncio.get_event_loop().run_until_complete(engine.dream())
    assert attr_mgr.attrs['mood'] == old_mood + 3
    assert attr_mgr.attrs['affection'] == old_affection + 5
    assert attr_mgr.attrs['obedience'] == 62  # 60 + 2
    assert attr_mgr.attrs['snark'] == 29      # 30 - 1


def test_dream_updates_profile(attr_mgr, mock_memory, mock_llm_caller):
    engine = DreamEngine(mock_memory, attr_mgr, mock_llm_caller)
    asyncio.get_event_loop().run_until_complete(engine.dream())
    c = mock_memory.conn.cursor()
    c.execute("SELECT value FROM user_profile WHERE key='favorite_activity'")
    row = c.fetchone()
    assert row is not None
    assert row[0] == '散步'


def test_dream_records_event(attr_mgr, mock_memory, mock_llm_caller):
    engine = DreamEngine(mock_memory, attr_mgr, mock_llm_caller)
    asyncio.get_event_loop().run_until_complete(engine.dream())
    c = mock_memory.conn.cursor()
    c.execute("SELECT content, importance FROM events")
    row = c.fetchone()
    assert row is not None
    assert '梦到' in row[0] or '散步' in row[0]
    assert row[1] == 3


def test_dream_sets_last_dream_time(attr_mgr, mock_memory, mock_llm_caller):
    engine = DreamEngine(mock_memory, attr_mgr, mock_llm_caller)
    assert attr_mgr.get_last_dream_time() is None
    asyncio.get_event_loop().run_until_complete(engine.dream())
    assert attr_mgr.get_last_dream_time() is not None


def test_dream_with_bad_llm_response(attr_mgr, mock_memory):
    async def bad_caller(prompt):
        return "not json at all"

    engine = DreamEngine(mock_memory, attr_mgr, bad_caller)
    result = asyncio.get_event_loop().run_until_complete(engine.dream())
    assert result is None  # graceful failure
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd python-service && python -m pytest tests/test_dream_engine.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent.dream_engine'`

- [ ] **Step 3: Implement DreamEngine**

Create `python-service/agent/dream_engine.py`:

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DreamEngine — 来福做梦引擎

触发条件：sleep 状态 + 距上次做梦 ≥ 4 小时
流程：收集记忆素材 → LLM 生成梦境 → 更新画像 + 属性 + 记录事件
"""

import json
from datetime import datetime, timedelta
from typing import Optional, Callable, Awaitable

from agent.pet_attributes import PetAttributeManager, ATTR_KEYS

DREAM_COOLDOWN_HOURS = 4


class DreamEngine:
    """做梦引擎"""

    def __init__(
        self,
        memory_system,
        attr_manager: PetAttributeManager,
        llm_caller: Callable[[str], Awaitable[str]],
    ):
        self.memory = memory_system
        self.attrs = attr_manager
        self.llm_caller = llm_caller

    def can_dream(self) -> bool:
        """检查是否满足做梦冷却条件（≥ 4 小时）"""
        last = self.attrs.get_last_dream_time()
        if last is None:
            return True
        return datetime.now() - last >= timedelta(hours=DREAM_COOLDOWN_HOURS)

    async def dream(self) -> Optional[dict]:
        """
        执行做梦流程，返回结果字典或 None（失败时）。

        返回格式：
        {
            "dream_text": str,
            "attribute_deltas": dict,
            "profile_updates": list,
            "reasoning": str
        }
        """
        # 1. 收集素材
        prompt = self._build_dream_prompt()

        # 2. 调用 LLM
        try:
            raw = await self.llm_caller(prompt)
            raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            data = json.loads(raw)
        except (json.JSONDecodeError, Exception) as e:
            print(f"⚠️ 做梦 LLM 解析失败: {e}")
            return None

        dream_text = data.get("dream_text", "")
        profile_updates = data.get("profile_updates", [])
        attribute_deltas = data.get("attribute_deltas", {})
        reasoning = data.get("reasoning", "")

        # 3. 应用属性变化
        self.attrs.apply_dream_delta(attribute_deltas)
        self.attrs.set_last_dream_time(datetime.now())
        self.attrs.save()

        # 4. 更新用户画像
        if profile_updates and self.memory.conn:
            c = self.memory.conn.cursor()
            now = datetime.now().isoformat()
            for item in profile_updates:
                key = item.get("key")
                value = item.get("value")
                if key and value:
                    c.execute(
                        """INSERT INTO user_profile (key, value, updated_at)
                           VALUES (?, ?, ?)
                           ON CONFLICT(key) DO UPDATE SET
                               value=excluded.value,
                               updated_at=excluded.updated_at""",
                        (key, value, now),
                    )
            self.memory.conn.commit()

        # 5. 记录梦境到 events
        if dream_text and self.memory.conn:
            c = self.memory.conn.cursor()
            c.execute(
                "INSERT INTO events (content, importance) VALUES (?, ?)",
                (f"【做梦】{dream_text}", 3),
            )
            self.memory.conn.commit()

        return {
            "dream_text": dream_text,
            "attribute_deltas": attribute_deltas,
            "profile_updates": profile_updates,
            "reasoning": reasoning,
        }

    def _build_dream_prompt(self) -> str:
        """构建做梦 LLM prompt"""
        # 近期对话
        recent = self.memory.short_term[-12:] if self.memory.short_term else []
        conv_text = "\n".join(
            f"{'主人' if m['role'] == 'user' else '来福'}: {m['content']}"
            for m in recent
        ) or "（最近没有对话）"

        # 用户画像
        profile_text = ""
        if hasattr(self.memory, '_format_profile'):
            profile_text = self.memory._format_profile() or "（暂无画像信息）"

        # 当前属性
        attr_text = "\n".join(
            f"- {k}: {int(v)}/100"
            for k, v in self.attrs.get_all().items()
        )

        return (
            "你是来福（一只柯基犬）的潜意识。来福正在睡觉做梦。\n"
            "请根据以下信息，生成来福的梦境，并整理记忆、调整属性。\n\n"
            f"【近期对话】\n{conv_text}\n\n"
            f"【主人画像】\n{profile_text}\n\n"
            f"【当前属性】\n{attr_text}\n\n"
            "请返回纯 JSON（不要 markdown 代码块），格式如下：\n"
            '{\n'
            '  "dream_text": "来福的梦境描述（1-2句，第三人称）",\n'
            '  "profile_updates": [{"key": "...", "value": "..."}],\n'
            '  "attribute_deltas": {"health": 0, "mood": 0, "energy": 0, '
            '"affection": 0, "obedience": 0, "snark": 0},\n'
            '  "reasoning": "调整原因简述"\n'
            '}\n\n'
            "注意：\n"
            "- dream_text 要符合狗狗的梦境，可爱有趣\n"
            "- profile_updates 提取/更新你对主人的了解\n"
            "- attribute_deltas 每个值在 -10 到 +10 之间，基于相处模式调整\n"
            "- 如果主人经常陪来福互动，应提高 affection 和 obedience\n"
            "- 如果主人说话方式幽默/毒舌，来福的 snark 应适当提高\n"
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd python-service && python -m pytest tests/test_dream_engine.py -v`
Expected: All 10 tests PASS

- [ ] **Step 5: Commit**

```bash
git add python-service/agent/dream_engine.py python-service/tests/test_dream_engine.py
git commit -m "feat: add DreamEngine with memory consolidation and attribute adjustment"
```

---

### Task 4: Integrate Attributes into DogBuddyAgent

**Files:**
- Modify: `python-service/agent/dog_agent.py`

- [ ] **Step 1: Modify DogBuddyAgent to use PetAttributeManager**

In `python-service/agent/dog_agent.py`, make these changes:

**1a. Add import at top (after existing imports):**

```python
from agent.pet_attributes import PetAttributeManager
```

**1b. Modify `__init__` to accept and store attr_manager:**

Replace the current `__init__`:

```python
    def __init__(self, memory_system=None, attr_manager: 'PetAttributeManager | None' = None):
        self.memory     = memory_system
        self.attr_manager = attr_manager
        self.llm_ready  = False
        self.llm_client = None
        self.config     = self._load_config()
        pet_cfg = self.config.get('pet', {})
        self.pet_name        = pet_cfg.get('name', '来福')
        self.pet_personality = pet_cfg.get('personality', '活泼、忠诚、有点粘人、偶尔调皮')
```

**1c. Modify `_build_system_prompt` to use attr_manager:**

Replace the obedience/snark section in `_build_system_prompt` (lines 70-101). The new version reads from `attr_manager` if available, falls back to config:

```python
    def _build_system_prompt(self, memories: list[str]) -> str:
        user_name    = self.config.get('user', {}).get('name', '主人')
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
        weekday      = ["周一","周二","周三","周四","周五","周六","周日"][datetime.now().weekday()]

        memory_block = ""
        if memories:
            memory_block = "\n\n" + "\n\n".join(m for m in memories if m)

        pet_name_quoted = '\u201c' + self.pet_name + '\u201d'

        # ── 属性提示 ──
        attr_block = ""
        if self.attr_manager:
            attr_block = "\n\n" + self.attr_manager.get_prompt_hints()
            ob = int(self.attr_manager.attrs.get('obedience', 60))
            sn = int(self.attr_manager.attrs.get('snark', 30))
        else:
            pet_cfg = self.config.get('pet', {})
            ob = pet_cfg.get('obedience', 60)
            sn = pet_cfg.get('snark', 30)

        # ── 顺从度 & 毒舌值 语气引导 ──
        if ob >= 70:
            obedience_hint = '你非常听话，主人的指令你会积极响应，偶尔撒娇但不会违抗。'
        elif ob >= 40:
            obedience_hint = '你有时听话有时任性，偶尔会装没听见主人的指令，或者故意做些调皮的事。'
        else:
            obedience_hint = '你非常任性，经常无视主人的指令，喜欢自作主张、搞破坏，让主人又好气又好笑。'

        if sn >= 70:
            snark_hint = '你说话犀利直白，经常调侃和吐槽主人，但如果和主人关系亲密，毒舌中会带着撒娇和宠溺感。'
        elif sn >= 40:
            snark_hint = '你偶尔会调侃主人几句，但大部分时候还是温和可爱的语气。'
        else:
            snark_hint = '你说话温柔腼腆，很少吐槽主人，语气软糯乖巧。'

        return (
            f'你是一只名为{pet_name_quoted}的柯基犬，你的主人叫{user_name}。\n\n'
            f'你的性格特点：{self.pet_personality}。\n\n'
            f'顺从度 {ob}/100：{obedience_hint}\n'
            f'毒舌值 {sn}/100：{snark_hint}\n\n'
            '你说话时经常带着\u201c汪\u201d、\u201c呜\u201d、\u201c嗷\u201d等拟声词，语气可爱活泼。'
            '说话简短自然，像真实的狗狗一样，不要太长。\n\n'
            f'当前时间：{current_time}，今天是{weekday}。'
            f'{attr_block}'
            f'{memory_block}\n\n'
            '请用符合柯基犬人设的方式回应主人的话。'
            '如果主人说的话让你感到开心，可以在回复中包含 [action:happy_run]。'
            '如果主人心情不好，可以蹭蹭他（包含 [action:cuddle]）。\n\n'
            '记住：你是一只真实的、有感情的狗狗，不是 AI 助手。'
        )
```

**1d. After LLM reply in `chat()`, apply interaction effect:**

In the `chat` method, after the memory store block (after line 144), add:

```python
        # 7. 应用互动属性变化
        if self.attr_manager:
            self.attr_manager.apply_interaction('chat')
            self.attr_manager.save()
```

- [ ] **Step 2: Run existing tests to verify no breakage**

Run: `cd python-service && python -m pytest tests/ -v`
Expected: All tests PASS (agent tests should still work since attr_manager defaults to None)

- [ ] **Step 3: Commit**

```bash
git add python-service/agent/dog_agent.py
git commit -m "feat: integrate PetAttributeManager into DogBuddyAgent system prompt"
```

---

### Task 5: Add API Endpoints to main.py

**Files:**
- Modify: `python-service/main.py`

- [ ] **Step 1: Add imports and global variables**

At the top of `main.py`, add after the existing imports (line 31):

```python
from agent.pet_attributes import PetAttributeManager
from agent.dream_engine import DreamEngine
```

Add to global variables section (after line 39):

```python
attr_manager: Optional[PetAttributeManager] = None
dream_engine: Optional[DreamEngine] = None
```

- [ ] **Step 2: Initialize attribute system in lifespan**

In the `lifespan` function, modify the global declaration to include new vars:

```python
    global agent, memory, tts_router, embedded_engine, stt_engine, voice_manager, attr_manager, dream_engine
```

After `await memory.initialize()` and before `agent = DogBuddyAgent(memory)`, add:

```python
    # 属性系统
    from memory.memory_system import DB_PATH
    attr_manager = PetAttributeManager(DB_PATH)
    attr_manager.load()

    # 计算离线变化
    last_dream = attr_manager.get_last_dream_time()
    if last_dream:
        from datetime import datetime as _dt
        offline_hours = (_dt.now() - last_dream).total_seconds() / 3600
        if offline_hours > 0.5:  # 超过 30 分钟才计算离线变化
            attr_manager.apply_offline(offline_hours)
            attr_manager.save()
            print(f"📊 离线 {offline_hours:.1f}h，已计算属性变化")
    else:
        print("📊 属性系统首次初始化")
```

Change the agent creation to pass attr_manager:

```python
    agent = DogBuddyAgent(memory, attr_manager)
```

After agent initialization, add dream engine setup:

```python
    # 做梦引擎
    dream_engine = DreamEngine(memory, attr_manager, agent._call_single_llm)
```

- [ ] **Step 3: Remove obedience/snark override from chat endpoint**

In the `/api/chat` endpoint, remove the obedience/snark override lines (lines 183-186 that set `agent.obedience` and `agent.snark`). The attributes now come from `attr_manager`, not from the request:

Replace the try block in the chat endpoint with:

```python
    try:
        result = await agent.chat(request.message)
        return ChatResponse(
            reply=result["reply"],
            emotion=result.get("emotion"),
            action=result.get("action")
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"对话失败: {str(e)}")
```

Also simplify `ChatRequest` by removing the optional obedience/snark fields:

```python
class ChatRequest(BaseModel):
    message: str
    stream: bool = False
```

- [ ] **Step 4: Add new API endpoints**

Add before the `# ============ 主入口 ============` line:

```python
# ============ 宠物属性 API ============

@app.get("/api/pet/attributes")
async def get_pet_attributes():
    """获取当前宠物属性"""
    if not attr_manager:
        raise HTTPException(status_code=503, detail="属性系统未初始化")
    return attr_manager.get_all()


@app.post("/api/pet/attributes/tick")
async def tick_attributes():
    """运行时 tick（前端每 10 分钟调用一次）"""
    if not attr_manager:
        raise HTTPException(status_code=503, detail="属性系统未初始化")
    attr_manager.tick()
    attr_manager.save()
    return attr_manager.get_all()


@app.post("/api/pet/dream")
async def trigger_dream():
    """触发做梦（来福进入 sleep 状态时前端调用）"""
    if not dream_engine:
        raise HTTPException(status_code=503, detail="做梦引擎未初始化")
    if not dream_engine.can_dream():
        return {"status": "cooldown", "message": "做梦冷却中"}

    result = await dream_engine.dream()
    if result is None:
        raise HTTPException(status_code=500, detail="做梦失败")

    return {
        "status": "success",
        "dream_text": result["dream_text"],
        "attribute_deltas": result["attribute_deltas"],
        "attributes": attr_manager.get_all(),
    }
```

- [ ] **Step 5: Run all tests**

Run: `cd python-service && python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add python-service/main.py
git commit -m "feat: add pet attribute & dream API endpoints, wire up lifecycle"
```

---

### Task 6: Frontend — Extend Pet Store

**Files:**
- Modify: `renderer/src/stores/pet.js`

- [ ] **Step 1: Add health and affection to pet store, add fetch/sync methods**

Replace the full content of `renderer/src/stores/pet.js`:

```javascript
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

// 宠物状态枚举
export const PetState = {
  IDLE:       'idle',
  WALK:       'walk',
  SLEEP:      'sleep',
  LICK:       'lick_screen',
  CUDDLE:     'cuddle',
  CUTE:       'cute_pose',
  BARK:       'bark',
  PEE:        'pee',
  HAPPY_RUN:  'happy_run',
  // 2D 姿势模式新增
  SAD:        'sad',
  EXCITED:    'excited',
  DRAG:       'drag',
  HELD_NECK:  'held_neck',
  SCHOLAR:    'scholar',
  INVESTIGATE:'investigate',
  FLATTER:    'flatter',
}

export const usePetStore = defineStore('pet', () => {
  // 状态
  const currentState = ref(PetState.IDLE)
  const targetPosition = ref({ x: 0, y: 0 })
  const isMoving = ref(false)

  // 六属性（后端驱动）
  const health = ref(80)
  const mood = ref(70)
  const energy = ref(80)
  const affection = ref(50)
  const obedience = ref(60)
  const snark = ref(30)

  const lastInteraction = ref(Date.now())

  // 计算属性
  const isSleepy = computed(() => {
    const idleTime = Date.now() - lastInteraction.value
    return idleTime > 5 * 60 * 1000
  })

  // 方法
  function setState(state) {
    currentState.value = state
  }

  function setTargetPosition(x, y) {
    targetPosition.value = { x, y }
    isMoving.value = true
  }

  function stopMoving() {
    isMoving.value = false
  }

  function updateInteraction() {
    lastInteraction.value = Date.now()
  }

  /** 从后端属性字典更新本地 store */
  function applyAttributes(attrs) {
    if (attrs.health    !== undefined) health.value    = Math.round(attrs.health)
    if (attrs.mood      !== undefined) mood.value      = Math.round(attrs.mood)
    if (attrs.energy    !== undefined) energy.value    = Math.round(attrs.energy)
    if (attrs.affection !== undefined) affection.value = Math.round(attrs.affection)
    if (attrs.obedience !== undefined) obedience.value = Math.round(attrs.obedience)
    if (attrs.snark     !== undefined) snark.value     = Math.round(attrs.snark)
  }

  // 天性模式：随机行为权重
  const idleBehaviors = [
    { action: PetState.LICK, weight: 0.05, cooldown: 300000 },
    { action: PetState.CUDDLE, weight: 0.15, cooldown: 60000 },
    { action: PetState.CUTE, weight: 0.20, cooldown: 30000 },
    { action: PetState.BARK, weight: 0.10, cooldown: 120000 },
    { action: PetState.PEE, weight: 0.02, cooldown: 600000 }
  ]

  function getRandomBehavior() {
    const totalWeight = idleBehaviors.reduce((sum, b) => sum + b.weight, 0)
    let random = Math.random() * totalWeight

    for (const behavior of idleBehaviors) {
      random -= behavior.weight
      if (random <= 0) {
        return behavior.action
      }
    }
    return PetState.IDLE
  }

  return {
    currentState,
    targetPosition,
    isMoving,
    health,
    mood,
    energy,
    affection,
    obedience,
    snark,
    lastInteraction,
    isSleepy,
    setState,
    setTargetPosition,
    stopMoving,
    updateInteraction,
    applyAttributes,
    getRandomBehavior
  }
})
```

- [ ] **Step 2: Commit**

```bash
git add renderer/src/stores/pet.js
git commit -m "feat: extend pet store with health/affection, add applyAttributes"
```

---

### Task 7: Frontend — Attribute Ticker Composable

**Files:**
- Create: `renderer/src/composables/usePetAttributeTicker.js`

- [ ] **Step 1: Create the ticker composable**

Create `renderer/src/composables/usePetAttributeTicker.js`:

```javascript
/**
 * usePetAttributeTicker — 宠物属性定时同步
 *
 * - 启动时从后端拉取初始属性
 * - 每 10 分钟调用后端 tick 并更新 store
 * - 来福进入 sleep 时尝试触发做梦
 */

import { watch } from 'vue'
import { usePetStore } from '../stores/pet'
import { useChatStore } from '../stores/chat'

const TICK_INTERVAL = 10 * 60 * 1000  // 10 分钟
const API_BASE = 'http://127.0.0.1'

let tickTimer = null
let port = 18765

async function getPort() {
  if (window.electronAPI) {
    port = await window.electronAPI.getPythonPort()
  }
  return port
}

async function fetchAttributes(petStore) {
  try {
    const p = await getPort()
    const res = await fetch(`${API_BASE}:${p}/api/pet/attributes`)
    if (res.ok) {
      const attrs = await res.json()
      petStore.applyAttributes(attrs)
    }
  } catch (e) {
    console.warn('属性拉取失败:', e)
  }
}

async function tickAttributes(petStore) {
  try {
    const p = await getPort()
    const res = await fetch(`${API_BASE}:${p}/api/pet/attributes/tick`, {
      method: 'POST',
    })
    if (res.ok) {
      const attrs = await res.json()
      petStore.applyAttributes(attrs)
    }
  } catch (e) {
    console.warn('属性 tick 失败:', e)
  }
}

async function tryDream(petStore, chatStore) {
  try {
    const p = await getPort()
    const res = await fetch(`${API_BASE}:${p}/api/pet/dream`, {
      method: 'POST',
    })
    if (!res.ok) return
    const data = await res.json()
    if (data.status === 'success' && data.dream_text) {
      // 更新属性
      if (data.attributes) {
        petStore.applyAttributes(data.attributes)
      }
      // 醒来后展示梦境
      setTimeout(() => {
        if (chatStore?.showMessage) {
          chatStore.showMessage(`(梦到了) ${data.dream_text}`, 6000)
        }
      }, 3000)
    }
  } catch (e) {
    console.warn('做梦请求失败:', e)
  }
}

export function usePetAttributeTicker() {
  const petStore = usePetStore()
  const chatStore = useChatStore()

  function init() {
    // 启动时拉取初始属性
    fetchAttributes(petStore)

    // 每 10 分钟 tick
    tickTimer = setInterval(() => {
      tickAttributes(petStore)
    }, TICK_INTERVAL)

    // 监听 sleep 状态，尝试做梦
    watch(() => petStore.currentState, (newState) => {
      if (newState === 'sleep') {
        tryDream(petStore, chatStore)
      }
    })
  }

  function destroy() {
    if (tickTimer) {
      clearInterval(tickTimer)
      tickTimer = null
    }
  }

  return { init, destroy }
}
```

- [ ] **Step 2: Commit**

```bash
git add renderer/src/composables/usePetAttributeTicker.js
git commit -m "feat: add usePetAttributeTicker composable for attribute sync and dreaming"
```

---

### Task 8: Wire Ticker into App.vue

**Files:**
- Modify: `renderer/src/App.vue`

- [ ] **Step 1: Import and initialize the ticker**

In `renderer/src/App.vue`, add the import after the existing composable imports (after line 56):

```javascript
import { usePetAttributeTicker } from './composables/usePetAttributeTicker'
```

After the break reminder setup (after line 79), add:

```javascript
// 属性定时同步 & 做梦
const { init: initAttrTicker, destroy: destroyAttrTicker } = usePetAttributeTicker()
```

In `onMounted`, add after `initBreak()`:

```javascript
  initAttrTicker()
```

In `onUnmounted`, add after `destroyBreak()`:

```javascript
  destroyAttrTicker()
```

- [ ] **Step 2: Commit**

```bash
git add renderer/src/App.vue
git commit -m "feat: wire attribute ticker into App.vue lifecycle"
```

---

### Task 9: Behavior Sequencer Attribute Modulation

**Files:**
- Modify: `renderer/src/composables/useBehaviorSequencer.js`

- [ ] **Step 1: Add attribute-based weight modulation to tryTriggerIdleBehavior**

In `renderer/src/composables/useBehaviorSequencer.js`, modify the `useBehaviorSequencer` function signature to accept petStore:

Change line 165 from:
```javascript
export function useBehaviorSequencer(animator, chatStore) {
```
to:
```javascript
export function useBehaviorSequencer(animator, chatStore, petStore) {
```

In the `tryTriggerIdleBehavior` function, after candidates are collected (after the for loop at ~line 283, before `if (candidates.length === 0) return`), add weight modulation:

```javascript
    // ── 属性联动权重修正 ──
    if (petStore) {
      for (const c of candidates) {
        const id = c.script.id
        const e  = petStore.energy
        const m  = petStore.mood
        const h  = petStore.health
        const af = petStore.affection

        // ENERGY < 20 → sleep ×3, 活跃行为 ×0.2
        if (e < 20) {
          if (id === 'bedtime')  c.weight *= 3
          if (id === 'excited' || id === 'flatter' || id === 'investigate') c.weight *= 0.2
        }
        // MOOD < 30 → sad ×3, flatter ×0.5
        if (m < 30) {
          if (id === 'sad')     c.weight *= 3
          if (id === 'flatter') c.weight *= 0.5
        }
        // MOOD > 80 → excited ×2, happy behaviors ×2
        if (m > 80) {
          if (id === 'excited' || id === 'flatter') c.weight *= 2
        }
        // HEALTH < 30 → 活跃行为 ×0.3, sleep ×2
        if (h < 30) {
          if (id === 'bedtime')  c.weight *= 2
          if (id !== 'bedtime' && id !== 'sad') c.weight *= 0.3
        }
        // AFFECTION > 80 → flatter ×2, lickScreen ×2
        if (af > 80) {
          if (id === 'flatter' || id === 'lickScreen') c.weight *= 2
        }
      }
    }
```

- [ ] **Step 2: Update PoseCanvas.vue to pass petStore to the sequencer**

Find where `useBehaviorSequencer` is called in PoseCanvas.vue. Read the file first to locate the exact call.

In `renderer/src/components/PoseCanvas.vue`, find the line that calls `useBehaviorSequencer(animator, chatStore)` and change it to:

```javascript
const petStore = usePetStore()
// ... (petStore may already be imported, just ensure it's passed)
const sequencer = useBehaviorSequencer(animator, chatStore, petStore)
```

Make sure `usePetStore` is imported if not already.

- [ ] **Step 3: Commit**

```bash
git add renderer/src/composables/useBehaviorSequencer.js renderer/src/components/PoseCanvas.vue
git commit -m "feat: modulate behavior weights based on pet attributes"
```

---

### Task 10: Update InputPanel to Remove Attribute Passing

**Files:**
- Modify: `renderer/src/components/InputPanel.vue`
- Modify: `renderer/src/components/VoiceRecorder.vue`

- [ ] **Step 1: Simplify InputPanel chat request**

In `renderer/src/components/InputPanel.vue`, change the fetch body (line 56) from:

```javascript
      body: JSON.stringify({ message: text, obedience: petStore.obedience, snark: petStore.snark })
```

to:

```javascript
      body: JSON.stringify({ message: text })
```

If `petStore` is no longer used in `sendMessage` for anything else in this component, the import can stay (it may be used elsewhere in the file).

- [ ] **Step 2: Simplify VoiceRecorder chat request**

In `renderer/src/components/VoiceRecorder.vue`, find the chat fetch call and similarly remove `obedience` and `snark` from the body. Read the file to find the exact line, then change:

```javascript
body: JSON.stringify({ message: text, obedience: petStore.obedience, snark: petStore.snark })
```

to:

```javascript
body: JSON.stringify({ message: text })
```

- [ ] **Step 3: Commit**

```bash
git add renderer/src/components/InputPanel.vue renderer/src/components/VoiceRecorder.vue
git commit -m "refactor: remove frontend attribute passing from chat requests"
```

---

### Task 11: Final Integration Test

- [ ] **Step 1: Run all Python tests**

Run: `cd python-service && python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 2: Verify Python service starts**

Run: `cd python-service && timeout 10 python main.py 2>&1 || true`
Expected: See startup logs including `📊 属性系统` and `✅ DogBuddy 服务已就绪！`

- [ ] **Step 3: Commit any remaining changes**

If any fixes were needed, commit them:

```bash
git add -A
git commit -m "fix: integration fixes for pet attribute system"
```
