import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.agent.state_machine import ConversationStage
from app.services.redis_client import RedisService
from app.voice.pipeline import CallConfig, VoicePipeline
from app.voice.realtime import RealtimeSession, SessionConfig

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws/voice/{call_id}")
async def voice_websocket(ws: WebSocket, call_id: str):
    """
    WebSocket endpoint bridging browser audio to OpenAI Realtime API.

    Browser sends JSON messages:
      - {"type": "start", "target_profile": {...}}
      - {"type": "audio", "audio": "<base64 PCM16 24kHz>"}
      - {"type": "text", "text": "hello"}
      - {"type": "stop"}

    Backend sends JSON messages:
      - {"type": "audio", "audio": "<base64 PCM16 24kHz>"}
      - {"type": "transcript", "role": "agent"|"user", "text": "..."}
      - {"type": "stage", "stage": "intro"|"pitch"|...}
      - {"type": "error", "message": "..."}
    """
    await ws.accept()
    redis = RedisService()
    pipeline: VoicePipeline | None = None
    realtime: RealtimeSession | None = None

    try:
        # Wait for the "start" message to initialize the session
        raw = await ws.receive_text()
        start_msg = json.loads(raw)

        if start_msg.get("type") != "start":
            await ws.send_json({"type": "error", "message": "First message must be type 'start'"})
            await ws.close()
            return

        target_profile = start_msg.get("target_profile", {})
        target_name = target_profile.get("name", "Unknown")

        # Create pipeline and supervisor
        config = CallConfig(
            call_id=call_id,
            target_name=target_name,
            target_profile=target_profile,
            mode="browser",
        )
        pipeline = VoicePipeline(config, redis=redis)
        pipeline.is_active = True
        pipeline.state_machine.transition(ConversationStage.INTRO)

        # Build realtime session with tools
        # Realtime API uses a flat tool format: name/description/parameters
        # sit at the top level alongside "type", NOT nested in a "function" key.
        session_config = SessionConfig(
            instructions=pipeline._build_realtime_instructions(),
            tools=[
                {
                    "type": "function",
                    "name": "delegate_to_supervisor",
                    "description": "Delegate a strategic decision to the supervisor model for better reasoning.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "question": {
                                "type": "string",
                                "description": "What you need the supervisor to decide",
                            },
                            "context": {
                                "type": "string",
                                "description": "Relevant conversation context",
                            },
                        },
                        "required": ["question"],
                    },
                },
            ],
        )
        realtime = RealtimeSession(config=session_config)
        await realtime.connect()

        # Publish call.started event
        await redis.publish_event("call.started", {
            "call_id": call_id,
            "target": target_name,
            "mode": "browser",
        })

        # Send initial stage to browser
        await ws.send_json({"type": "stage", "stage": pipeline.state_machine.current_stage.value})

        # Run inbound and outbound loops concurrently
        inbound_task = asyncio.create_task(
            _inbound_loop(ws, realtime, pipeline, redis)
        )
        outbound_task = asyncio.create_task(
            _outbound_loop(ws, realtime, pipeline, redis)
        )

        # Wait for either task to finish (one finishing means session is over)
        done, pending = await asyncio.wait(
            [inbound_task, outbound_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

        # Cancel the remaining task
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        # Re-raise exceptions from completed tasks
        for task in done:
            if task.exception() and not isinstance(task.exception(), (WebSocketDisconnect, asyncio.CancelledError)):
                logger.error(f"Voice WS task error for {call_id}: {task.exception()}")

    except WebSocketDisconnect:
        logger.info(f"Voice WebSocket disconnected: {call_id}")
    except Exception:
        logger.exception(f"Voice WebSocket error for {call_id}")
        try:
            await ws.send_json({"type": "error", "message": "Internal server error"})
        except Exception:
            pass
    finally:
        # Clean up
        if realtime:
            try:
                await realtime.disconnect()
            except Exception:
                pass
        if pipeline and pipeline.is_active:
            pipeline.is_active = False
            await redis.publish_event("call.ended", {
                "call_id": call_id,
                "stage": pipeline.state_machine.current_stage.value if pipeline else "unknown",
                "transcript_length": len(pipeline._transcript) if pipeline else 0,
            })


async def _inbound_loop(
    ws: WebSocket,
    realtime: RealtimeSession,
    pipeline: VoicePipeline,
    redis: RedisService,
) -> None:
    """Receive messages from the browser and forward to OpenAI Realtime API."""
    while pipeline.is_active:
        raw = await ws.receive_text()
        msg = json.loads(raw)
        msg_type = msg.get("type")

        if msg_type == "audio":
            audio_b64 = msg.get("audio", "")
            if audio_b64:
                await realtime.send_audio(audio_b64)

        elif msg_type == "text":
            text = msg.get("text", "")
            if text:
                pipeline._transcript.append({"role": "student", "content": text})
                await redis.publish_event("transcript.update", {
                    "call_id": pipeline.config.call_id,
                    "stage": pipeline.state_machine.current_stage.value,
                    "message": {"role": "user", "content": text},
                })
                await ws.send_json({"type": "transcript", "role": "user", "text": text})
                await realtime.send_text(text)

        elif msg_type == "stop":
            pipeline.is_active = False
            return

        else:
            logger.warning(f"Unknown inbound message type: {msg_type}")


async def _outbound_loop(
    ws: WebSocket,
    realtime: RealtimeSession,
    pipeline: VoicePipeline,
    redis: RedisService,
) -> None:
    """Receive events from OpenAI Realtime API and forward to the browser."""
    async for event in realtime.receive_events():
        event_type = event.get("type", "")

        if event_type == "response.output_audio.delta":
            # Forward audio chunk to browser (GA event name)
            audio_b64 = event.get("delta", "")
            if audio_b64:
                await ws.send_json({"type": "audio", "audio": audio_b64})

        elif event_type == "response.output_audio_transcript.delta":
            # Audio plays in real-time; full transcript sent on .done
            pass

        elif event_type == "response.output_audio_transcript.done":
            # Full agent transcript completed (GA event name) — send as single message
            transcript = event.get("transcript", "")
            if transcript:
                pipeline._transcript.append({"role": "agent", "content": transcript})
                await ws.send_json({"type": "transcript", "role": "agent", "text": transcript})
                await redis.publish_event("transcript.update", {
                    "call_id": pipeline.config.call_id,
                    "stage": pipeline.state_machine.current_stage.value,
                    "message": {"role": "agent", "content": transcript},
                })

        elif event_type == "input_audio_buffer.speech_started":
            # User started speaking — browser can use this to show visual feedback
            pass

        elif event_type == "conversation.item.input_audio_transcription.completed":
            # User speech transcribed
            user_text = event.get("transcript", "")
            if user_text:
                pipeline._transcript.append({"role": "student", "content": user_text})
                await ws.send_json({"type": "transcript", "role": "user", "text": user_text})
                await redis.publish_event("transcript.update", {
                    "call_id": pipeline.config.call_id,
                    "stage": pipeline.state_machine.current_stage.value,
                    "message": {"role": "user", "content": user_text},
                })

        elif event_type == "response.function_call_arguments.done":
            # Handle tool call via Supervisor
            await _handle_tool_call(event, realtime, pipeline, ws, redis)

        elif event_type == "response.done":
            # Response complete — nothing special needed
            pass

        elif event_type == "error":
            error_msg = event.get("error", {}).get("message", "Unknown OpenAI error")
            logger.error(f"OpenAI Realtime error for {pipeline.config.call_id}: {error_msg}")
            await ws.send_json({"type": "error", "message": error_msg})

        elif event_type == "session.created" or event_type == "session.updated":
            logger.info(f"Realtime session event: {event_type}")


async def _handle_tool_call(
    event: dict,
    realtime: RealtimeSession,
    pipeline: VoicePipeline,
    ws: WebSocket,
    redis: RedisService,
) -> None:
    """Handle a tool call from OpenAI Realtime (delegate_to_supervisor)."""
    fn_name = event.get("name", "")
    call_id = event.get("call_id", "")
    raw_args = event.get("arguments", "{}")

    try:
        args = json.loads(raw_args)
    except json.JSONDecodeError:
        args = {}

    if fn_name == "delegate_to_supervisor":
        question = args.get("question", "")
        context = args.get("context", "")
        prompt = f"Question from the voice agent: {question}"
        if context:
            prompt += f"\nContext: {context}"

        # Capture stage before supervisor call to detect transitions
        stage_before = pipeline.state_machine.current_stage.value

        # Get supervisor's response
        supervisor_response = await pipeline.supervisor.get_response(prompt)

        # Check if the supervisor triggered a stage transition
        stage_after = pipeline.state_machine.current_stage.value
        if stage_before != stage_after:
            await ws.send_json({"type": "stage", "stage": stage_after})
            await redis.publish_event("stage.changed", {
                "call_id": pipeline.config.call_id,
                "stage": stage_after,
            })

        # Send tool result back to OpenAI Realtime
        await realtime.send_tool_result(call_id, supervisor_response)
    else:
        # Unknown tool — send error result
        await realtime.send_tool_result(call_id, f"Unknown tool: {fn_name}")
