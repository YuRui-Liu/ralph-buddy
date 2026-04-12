#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DogBuddy Python 服务 - FastAPI 后端
提供 LLM 对话、STT、TTS、记忆系统等功能
"""

import os
import sys
import io
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
from memory.memory_system import MemorySystem
from tts.edge_engine import EdgeTTSEngine
from tts.gpt_sovits_engine import GptSoVITSEngine
from tts.voice_manager import VoiceManager, get_manager
from stt.whisper_engine import WhisperEngine

# 全局实例
agent: Optional[DogBuddyAgent] = None
memory: Optional[MemorySystem] = None
tts_engine = None          # EdgeTTSEngine | GptSoVITSEngine
stt_engine: Optional[WhisperEngine] = None
voice_manager: Optional[VoiceManager] = None
gsv_engine: Optional[GptSoVITSEngine] = None  # 来福克隆引擎单例

def _laifu_clone_dir() -> Optional[str]:
    """返回 laifu-clone 目录绝对路径（不存在则返回 None）"""
    here = os.path.dirname(os.path.abspath(__file__))
    d = os.path.join(here, "data", "voices", "laifu-clone")
    cfg = os.path.join(d, "config.json")
    return d if os.path.exists(cfg) else None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """生命周期管理"""
    global agent, memory, tts_engine, stt_engine, voice_manager, gsv_engine

    print("🐕 DogBuddy 服务启动中...")

    # 记忆系统
    memory = MemorySystem()
    await memory.initialize()

    # AI Agent
    agent = DogBuddyAgent(memory)
    await agent.initialize()

    # 语音管理器
    voice_manager = get_manager()

    # TTS 引擎：优先使用来福克隆，降级到 Edge TTS
    clone_dir = _laifu_clone_dir()
    if clone_dir:
        try:
            gsv_engine = GptSoVITSEngine(clone_dir)
            await gsv_engine.start()
            tts_engine = gsv_engine
            print("🎙️  TTS: 来福克隆 (GPT-SoVITS)")
        except Exception as e:
            print(f"⚠️  来福克隆启动失败，降级到 Edge TTS: {e}")
            gsv_engine = None
            tts_engine = EdgeTTSEngine("xiaoxiao")
            print(f"🔊 TTS: Edge TTS (xiaoxiao)")
    else:
        active_voice = voice_manager.get_active_package()
        voice_name = (active_voice.voice_name if active_voice and active_voice.type == "edge-tts"
                      else "xiaoxiao")
        tts_engine = EdgeTTSEngine(voice_name)
        print(f"🔊 TTS: Edge TTS ({voice_name})")

    # STT 引擎
    local_model = os.path.expanduser(r"E:\LLM\backbone\Voice\faster-whisper-small")
    if not os.path.exists(local_model):
        local_model = None

    stt_engine = WhisperEngine(model_size="small", local_model_path=local_model)

    print("✅ DogBuddy 服务已就绪！")
    print(f"   🎤 STT: Whisper (small), 路径：{local_model}")

    yield

    # 关闭
    print("🛑 DogBuddy 服务关闭中...")
    if memory:
        await memory.close()
    if gsv_engine:
        gsv_engine.close()

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
        tts_ready=tts_engine is not None,
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


@app.post("/api/tts")
async def text_to_speech(
    text: str = Form(...),
    voice_id: Optional[str] = Form(None)
):
    """
    文字转语音 (Form Data 格式，兼容 Windows curl)
    
    Args:
        text: 要合成的文字
        voice_id: 可选，语音包 ID
    
    Returns:
        音频流 (MP3)
    """
    global tts_engine
    
    if not tts_engine:
        raise HTTPException(status_code=503, detail="TTS 引擎未初始化")
    
    try:
        print(f"🎤 TTS 请求: text='{text[:30]}...', voice_id={voice_id}")

        if not text:
            raise HTTPException(status_code=400, detail="text 字段不能为空")

        # 确定本次使用的引擎
        engine = tts_engine

        if voice_id:
            if voice_id == "laifu-clone" and gsv_engine:
                engine = gsv_engine
            else:
                pkg = voice_manager.get_package(voice_id)
                if pkg and pkg.type == "edge-tts":
                    engine = EdgeTTSEngine(pkg.voice_name)
                    print(f"🎵 切换到语音包: {pkg.name}")
                else:
                    raise HTTPException(status_code=404, detail=f"语音包不存在: {voice_id}")

        # 合成语音
        audio_bytes = await engine.synthesize(text)
        print(f"✅ TTS 合成完成: {len(audio_bytes)} bytes")

        # 根据引擎类型返回对应格式
        is_gsv = isinstance(engine, GptSoVITSEngine)
        media_type = "audio/wav" if is_gsv else "audio/mpeg"
        filename = "speech.wav" if is_gsv else "speech.mp3"

        return StreamingResponse(
            io.BytesIO(audio_bytes),
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
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
    """激活指定语音包"""
    if not voice_manager:
        raise HTTPException(status_code=503, detail="语音管理器未初始化")
    
    success = voice_manager.set_active_voice(voice_id)
    if not success:
        raise HTTPException(status_code=404, detail="语音包不存在")
    
    # 更新 TTS 引擎
    global tts_engine
    if voice_id == "laifu-clone" and gsv_engine:
        tts_engine = gsv_engine
    else:
        pkg = voice_manager.get_active_package()
        if pkg and pkg.type == "edge-tts":
            tts_engine = EdgeTTSEngine(pkg.voice_name)

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
