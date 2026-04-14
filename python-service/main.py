#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DogBuddy Python 服务 - FastAPI 后端
提供 LLM 对话、STT、TTS、记忆系统等功能
"""

import os
import sys
import io
import re
import json
from typing import Optional, List, Dict
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# 确保能正确导入本地模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent.dog_agent import DogBuddyAgent
from agent.pet_attributes import PetAttributeManager
from agent.dream_engine import DreamEngine
from memory.memory_system import MemorySystem, DB_PATH
from tts.edge_engine import EdgeTTSEngine
from tts.embedded_engine import EmbeddedTTSEngine
from tts.router import TTSRouter
from tts.voice_manager import VoiceManager, get_manager
from stt.whisper_engine import WhisperEngine
from stt.mic_recorder import MicRecorder
from emotion.detector import EmotionDetector

# 全局实例
agent: Optional[DogBuddyAgent] = None
memory: Optional[MemorySystem] = None
tts_router: Optional[TTSRouter] = None
embedded_engine: Optional[EmbeddedTTSEngine] = None
stt_engine: Optional[WhisperEngine] = None
voice_manager: Optional[VoiceManager] = None
attr_manager: Optional[PetAttributeManager] = None
dream_engine: Optional[DreamEngine] = None
emotion_detector: Optional[EmotionDetector] = None
mic_recorder: Optional[MicRecorder] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """生命周期管理"""
    global agent, memory, tts_router, embedded_engine, stt_engine, voice_manager, attr_manager, dream_engine, emotion_detector

    print("🐕 DogBuddy 服务启动中...")

    # 记忆系统
    memory = MemorySystem()
    await memory.initialize()

    # 属性系统
    attr_manager = PetAttributeManager(DB_PATH)
    attr_manager.load()
    last_dream = attr_manager.get_last_dream_time()
    if last_dream:
        offline_hours = (datetime.now() - last_dream).total_seconds() / 3600
        if offline_hours > 0.5:
            attr_manager.apply_offline(offline_hours)
            attr_manager.save()
            print(f"📊 离线 {offline_hours:.1f}h，已计算属性变化")
    else:
        print("📊 属性系统首次初始化")

    # AI Agent
    agent = DogBuddyAgent(memory, attr_manager)
    await agent.initialize()

    # 做梦引擎
    dream_engine = DreamEngine(memory, attr_manager, agent._call_single_llm)

    # 语音管理器
    voice_manager = get_manager()

    # 若 laifu-clone 目录存在则注册为 gpt-sovits 包并激活
    here = os.path.dirname(os.path.abspath(__file__))
    clone_dir = os.path.join(here, "data", "voices", "laifu-clone")
    if os.path.exists(os.path.join(clone_dir, "config.json")):
        clone_pkg = voice_manager.register_voice_dir(
            clone_dir, "laifu-clone", "来福克隆 (GPT-SoVITS)"
        )
        voice_manager.set_active_voice(clone_pkg.id)

    # 组装 TTSRouter
    cache_dir = os.path.join(here, "data", "tts_cache")
    tts_router, embedded_engine = voice_manager.build_router(cache_dir=cache_dir)

    # 后台预热内嵌推理引擎（warmup 内部已做异常处理，失败时自动降级）
    if embedded_engine:
        import asyncio as _asyncio
        _asyncio.create_task(embedded_engine.warmup())
        print("🎙️  TTS: GPT-SoVITS 预热中（后台），期间使用 Edge TTS 兜底...")
    else:
        active = voice_manager.get_active_package()
        vname = active.voice_name if active else "xiaoxiao"
        print(f"🔊 TTS: Edge TTS ({vname})")

    # STT 引擎
    local_model = os.path.expanduser(r"E:\LLM\backbone\Voice\faster-whisper-small")
    if not os.path.exists(local_model):
        local_model = None

    stt_engine = WhisperEngine(model_size="small", local_model_path=local_model)

    # 麦克风录音器（绕过 Electron getUserMedia 限制）
    global mic_recorder
    mic_recorder = MicRecorder()
    print("🎤 MicRecorder: 探测最佳麦克风设备...")
    mic_recorder.probe_best_device()

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
            try:
                return _json.loads(raw)
            except _json.JSONDecodeError:
                return {"description": raw, "suggested_action": "comfort", "suggested_speech": ""}
        return None

    emotion_detector = EmotionDetector(deep_llm_call=_deep_llm_call)

    print("✅ DogBuddy 服务已就绪！")
    print(f"   🎤 STT: Whisper (small), 路径：{local_model}")

    yield

    # 关闭
    print("🛑 DogBuddy 服务关闭中...")
    if memory:
        await memory.close()

# 创建 FastAPI 应用
app = FastAPI(
    title="DogBuddy API",
    description="桌面AI陪伴宠物 - 来福 的后端服务",
    version="0.1.0",
    lifespan=lifespan
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制为 Electron 应用
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============ 数据模型 ============

class ChatRequest(BaseModel):
    message: str
    stream: bool = False

class ChatResponse(BaseModel):
    reply: str
    emotion: Optional[str] = None
    action: Optional[str] = None

class MemoryItem(BaseModel):
    content: str
    importance: int = 1

class TTSSettings(BaseModel):
    text: str
    voice_id: Optional[str] = None

class STTResponse(BaseModel):
    text: str
    confidence: float

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

class StatusResponse(BaseModel):
    status: str
    version: str
    llm_ready: bool
    tts_ready: bool
    stt_ready: bool



# ============ API 端点 ============

@app.get("/")
async def root():
    """根路径 - 服务健康检查"""
    return {
        "name": "DogBuddy API",
        "version": "0.1.0",
        "status": "running",
        "pet_name": "来福",
        "docs": "/docs"
    }

@app.get("/api/status", response_model=StatusResponse)
async def get_status():
    """获取服务状态"""
    return StatusResponse(
        status="running",
        version="0.1.0",
        llm_ready=agent is not None and agent.llm_ready,
        tts_ready=tts_router is not None,
        stt_ready=stt_engine is not None
    )

@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """发送对话消息"""
    if not agent:
        raise HTTPException(status_code=503, detail="Agent 未初始化")
    
    try:
        result = await agent.chat(request.message)
        return ChatResponse(
            reply=result["reply"],
            emotion=result.get("emotion"),
            action=result.get("action")
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"对话失败: {str(e)}")

@app.post("/api/emotion", response_model=EmotionResponse)
async def detect_emotion(
    image: UploadFile = File(...),
    deep: bool = Form(False),
):
    """情绪检测 — 摄像头截帧 → 本地快速识别 + 可选深度分析"""
    if not emotion_detector:
        raise HTTPException(status_code=503, detail="情绪检测器未初始化")

    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="图像为空")

    result = await emotion_detector.detect(image_bytes)
    print(f"👁️ 情绪检测: has_face={result['has_face']}, "
          f"emotion={result['local']['emotion'] if result['local'] else 'N/A'}, "
          f"changed={result['changed']}")

    if result["has_face"] and (deep or emotion_detector.should_trigger_deep(result)):
        deep_result = await emotion_detector.analyze_deep(image_bytes, result)
        result["deep"] = deep_result
        if deep_result:
            print(f"🧠 深度分析: {deep_result.get('description', '')[:50]}")
            if agent:
                agent.owner_emotion_context = deep_result.get("description", "")

    return result


@app.post("/api/stt")
async def speech_to_text(
    audio: UploadFile = File(...),
    language: str = Form("zh")
):
    """
    语音转文字
    
    Args:
        audio: 音频文件 (webm/wav/mp3/m4a)
        language: 语言代码 (zh, en, ja, etc.)
    
    Returns:
        STTResponse: 识别结果
    """
    if not stt_engine:
        raise HTTPException(status_code=503, detail="STT 引擎未初始化")
    
    try:
        # 读取音频数据
        audio_bytes = await audio.read()
        
        if len(audio_bytes) == 0:
            raise HTTPException(status_code=400, detail="音频文件为空")
        
        # 获取文件格式
        source_format = audio.filename.split('.')[-1].lower() if '.' in audio.filename else "webm"
        
        print(f"📥 收到音频: {audio.filename}, 格式: {source_format}, 大小: {len(audio_bytes)} bytes")
        
        # 执行识别
        text, confidence = await stt_engine.transcribe(
            audio_bytes, 
            source_format=source_format,
            language=language if language != "auto" else None
        )
        
        return STTResponse(text=text, confidence=confidence)
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_detail = f"语音识别失败: {str(e)}\n{traceback.format_exc()}"
        print(f"❌ {error_detail}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ 麦克风录音 API（绕过 Electron getUserMedia） ============

@app.get("/api/mic/devices")
async def mic_devices():
    """列出可用麦克风设备"""
    if not mic_recorder:
        raise HTTPException(status_code=503, detail="MicRecorder 未初始化")
    return {"devices": mic_recorder.list_devices()}

@app.post("/api/mic/start")
async def mic_start():
    """开始录音"""
    if not mic_recorder:
        raise HTTPException(status_code=503, detail="MicRecorder 未初始化")
    if mic_recorder.is_recording:
        return {"status": "already_recording"}
    mic_recorder.start()
    return {"status": "recording"}

@app.post("/api/mic/stop")
async def mic_stop():
    """停止录音并返回 STT 结果"""
    if not mic_recorder:
        raise HTTPException(status_code=503, detail="MicRecorder 未初始化")
    if not mic_recorder.is_recording:
        print("[mic/stop] not recording")
        return {"status": "not_recording", "text": "", "confidence": 0}

    wav_bytes = mic_recorder.stop()
    print(f"[mic/stop] wav_bytes={len(wav_bytes) if wav_bytes else 0}")
    if not wav_bytes or len(wav_bytes) < 100:
        return {"status": "empty", "text": "", "confidence": 0}

    # 直接用 STT 引擎识别
    if not stt_engine:
        raise HTTPException(status_code=503, detail="STT 引擎未初始化")

    try:
        text, confidence = await stt_engine.transcribe(
            wav_bytes, source_format="wav", language="zh"
        )
        return {"status": "ok", "text": text, "confidence": confidence}
    except Exception as e:
        import traceback
        print(f"❌ 录音 STT 失败: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/mic/cancel")
async def mic_cancel():
    """取消录音（丢弃数据）"""
    if mic_recorder and mic_recorder.is_recording:
        mic_recorder.stop()  # 丢弃数据
    return {"status": "cancelled"}


@app.post("/api/tts")
async def text_to_speech(
    text: str = Form(...),
    voice_id: Optional[str] = Form(None),
    hint: Optional[str] = Form(None),
):
    """
    文字转语音 (Form Data 格式)

    Args:
        text:     要合成的文字
        voice_id: 可选，强制指定 edge-tts 语音包 ID（忽略路由器）
        hint:     可选，路由提示，如 "barks.short"，默认 "llm"

    Returns:
        音频流 (WAV 或 MP3)
    """
    if not tts_router:
        raise HTTPException(status_code=503, detail="TTS 引擎未初始化")

    if not text and hint == "llm":
        raise HTTPException(status_code=400, detail="text 字段不能为空")

    try:
        print(f"🎤 TTS 请求: text='{text[:30]}...', voice_id={voice_id}, hint={hint}")

        # 过滤括号中的表情/动作描述，如（歪着头）、(摇尾巴)
        text = re.sub(r'[（(][^）)]*[）)]', '', text).strip()
        if not text:
            raise HTTPException(status_code=400, detail="过滤表情/动作后文本为空")

        # voice_id 指定时绕过路由器，直接用 EdgeTTS
        if voice_id:
            pkg = voice_manager.get_package(voice_id) if voice_manager else None
            if pkg and pkg.type == "edge-tts":
                audio_bytes = await EdgeTTSEngine(pkg.voice_name).synthesize(text)
                return StreamingResponse(
                    io.BytesIO(audio_bytes),
                    media_type="audio/mpeg",
                    headers={"Content-Disposition": "attachment; filename=speech.mp3"},
                )
            raise HTTPException(status_code=404, detail=f"语音包不存在: {voice_id}")

        audio_bytes = await tts_router.synthesize(text, hint=hint or "llm")
        print(f"✅ TTS 合成完成: {len(audio_bytes)} bytes")

        # 自动检测格式
        if audio_bytes[:4] == b"RIFF":
            media_type, filename = "audio/wav", "speech.wav"
        else:
            media_type, filename = "audio/mpeg", "speech.mp3"

        return StreamingResponse(
            io.BytesIO(audio_bytes),
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"❌ TTS 失败: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"语音合成失败: {str(e)}")


@app.get("/api/tts/voices")
async def list_voices():
    """获取可用语音列表"""
    if not voice_manager:
        raise HTTPException(status_code=503, detail="语音管理器未初始化")
    
    packages = voice_manager.list_packages()
    return {
        "packages": [pkg.to_dict() for pkg in packages],
        "active_voice_id": voice_manager.active_voice_id
    }


@app.post("/api/tts/voices/{voice_id}/activate")
async def activate_voice(voice_id: str):
    """激活指定语音包并重建 TTS 路由器"""
    if not voice_manager:
        raise HTTPException(status_code=503, detail="语音管理器未初始化")

    success = voice_manager.set_active_voice(voice_id)
    if not success:
        raise HTTPException(status_code=404, detail="语音包不存在")

    global tts_router, embedded_engine
    here = os.path.dirname(os.path.abspath(__file__))
    cache_dir = os.path.join(here, "data", "tts_cache")
    tts_router, new_embedded = voice_manager.build_router(voice_id, cache_dir=cache_dir)
    if new_embedded and new_embedded is not embedded_engine:
        import asyncio as _asyncio
        _asyncio.create_task(new_embedded.warmup())
    embedded_engine = new_embedded

    return {"status": "success", "active_voice_id": voice_id}


@app.post("/api/voice-clone/upload")
async def upload_voice_sample(
    audio: UploadFile = File(...),
    name: str = Form(...),
    description: str = Form("")
):
    """
    上传声音样本用于克隆
    
    Args:
        audio: 参考音频文件 (建议 30秒-1分钟，wav格式)
        name: 语音包名称
        description: 描述
    
    Returns:
        上传结果，包含临时文件路径
    """
    try:
        # 保存上传的音频
        upload_dir = os.path.join(voice_manager.data_dir, "uploads")
        os.makedirs(upload_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        filename = f"sample_{timestamp}_{audio.filename}"
        file_path = os.path.join(upload_dir, filename)
        
        with open(file_path, "wb") as f:
            f.write(await audio.read())
        
        return {
            "status": "success",
            "temp_path": file_path,
            "name": name,
            "description": description
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")


@app.post("/api/voice-clone/train")
async def train_voice_clone(
    temp_path: str = Form(...),
    name: str = Form(...),
    description: str = Form("")
):
    """
    训练声音克隆模型（GPT-SoVITS）
    
    注意：这是一个异步长任务，实际实现需要任务队列
    """
    # TODO: 集成 GPT-SoVITS 训练流程
    # 由于训练时间较长，这里返回一个任务ID，客户端需要轮询状态
    
    raise HTTPException(
        status_code=501, 
        detail="GPT-SoVITS 训练功能正在开发中。请使用 Edge TTS 作为替代方案。"
    )

# ============ 记忆系统 API ============

@app.get("/api/memory/summary")
async def get_memory_summary():
    """获取记忆摘要"""
    if not memory:
        raise HTTPException(status_code=503, detail="记忆系统未初始化")
    
    summary = await memory.get_user_profile()
    return summary

@app.post("/api/memory/add")
async def add_memory(item: MemoryItem):
    """手动添加记忆"""
    if not memory:
        raise HTTPException(status_code=503, detail="记忆系统未初始化")
    
    await memory.add_manual_memory(item.content, item.importance)
    return {"status": "success"}

@app.delete("/api/memory/clear")
async def clear_memory():
    """清除所有记忆"""
    if not memory:
        raise HTTPException(status_code=503, detail="记忆系统未初始化")

    await memory.clear_all()
    return {"status": "success"}


@app.get("/api/memory/events")
async def list_memory_events():
    """列出所有手动添加的重要记忆"""
    if not memory:
        raise HTTPException(status_code=503, detail="记忆系统未初始化")
    events = await memory.list_events()
    return {"events": events}


@app.delete("/api/memory/events/{event_id}")
async def delete_memory_event(event_id: int):
    """删除单条重要记忆"""
    if not memory:
        raise HTTPException(status_code=503, detail="记忆系统未初始化")
    success = await memory.delete_event(event_id)
    if not success:
        raise HTTPException(status_code=404, detail="记忆不存在")
    return {"status": "success"}


@app.get("/api/memory/search")
async def search_memory(query: str, top_k: int = 5):
    """搜索记忆"""
    if not memory:
        raise HTTPException(status_code=503, detail="记忆系统未初始化")
    
    results = await memory.search(query, top_k)
    return {"results": results}

# ============ 宠物属性 API ============

@app.get("/api/pet/attributes")
async def get_pet_attributes():
    """获取当前宠物属性"""
    if not attr_manager:
        raise HTTPException(status_code=503, detail="属性系统未初始化")
    return attr_manager.get_all()


@app.post("/api/pet/attributes/set")
async def set_pet_attributes(request: Request):
    """
    直接设置宠物属性（后门 / 调试用）

    Body JSON: {"snark": 80, "obedience": 40, ...}
    只传需要改的字段，不传的保持不变。
    """
    if not attr_manager:
        raise HTTPException(status_code=503, detail="属性系统未初始化")
    body = await request.json()
    valid_keys = {"health", "mood", "energy", "affection", "obedience", "snark"}
    changed = {}
    for k, v in body.items():
        if k in valid_keys:
            attr_manager.attrs[k] = max(0.0, min(100.0, float(v)))
            changed[k] = attr_manager.attrs[k]
    attr_manager.save()
    print(f"[pet/attributes/set] {changed}")
    return attr_manager.get_all()


@app.post("/api/pet/interact/{action}")
async def pet_interact(action: str):
    """
    触发互动：play / feed / responded / ignored

    示例: POST /api/pet/interact/play
    """
    if not attr_manager:
        raise HTTPException(status_code=503, detail="属性系统未初始化")
    from agent.pet_attributes import INTERACTION_DELTAS
    if action not in INTERACTION_DELTAS:
        raise HTTPException(status_code=400,
                            detail=f"未知互动类型: {action}，可选: {list(INTERACTION_DELTAS.keys())}")
    attr_manager.apply_interaction(action)
    attr_manager.save()
    print(f"[pet/interact] {action} → {attr_manager.get_all()}")
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

# ============ 主入口 ============

if __name__ == "__main__":
    import uvicorn
    
    port = int(os.environ.get("PORT", 18765))
    
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=port,
        log_level="info"
    )
