"use client";
import { useEffect, useRef, useState, useCallback } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function getWsUrl(callId: string): string {
  const base = API_BASE.replace(/^http/, "ws");
  return `${base}/ws/voice/${callId}`;
}

const EMA_DECAY = 0.85;

function computeRMS(samples: Float32Array): number {
  let sum = 0;
  for (let i = 0; i < samples.length; i++) {
    sum += samples[i] * samples[i];
  }
  return Math.sqrt(sum / samples.length);
}

function smooth(previous: number, current: number): number {
  return EMA_DECAY * previous + (1 - EMA_DECAY) * current;
}

export interface TranscriptEntry {
  role: "agent" | "user";
  text: string;
}

interface TargetProfile {
  [key: string]: unknown;
}

export function useVoiceChat(callId: string) {
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [transcript, setTranscript] = useState<TranscriptEntry[]>([]);

  const [micActive, setMicActive] = useState(false);
  const [outputVolume, setOutputVolume] = useState(0);
  const [inputVolume, setInputVolume] = useState(0);
  const [isSpeaking, setIsSpeaking] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const micStreamRef = useRef<MediaStream | null>(null);
  const micContextRef = useRef<AudioContext | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const playbackContextRef = useRef<AudioContext | null>(null);
  const playbackTimeRef = useRef(0);
  const activeSourcesRef = useRef<AudioBufferSourceNode[]>([]);
  const startedRef = useRef(false);
  const outputVolumeRef = useRef(0);
  const inputVolumeRef = useRef(0);
  const speakingTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Connect WebSocket
  useEffect(() => {
    const ws = new WebSocket(getWsUrl(callId));
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      setError(null);
    };

    ws.onclose = () => {
      setConnected(false);
    };

    ws.onerror = () => {
      setError("WebSocket connection failed");
    };

    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        switch (data.type) {
          case "transcript":
            setTranscript((prev) => [
              ...prev,
              { role: data.role, text: data.text },
            ]);
            break;

          case "audio":
            playAudioChunk(data.audio);
            break;
          case "clear_audio":
            clearAudio();
            break;
          case "error":
            setError(data.message);
            break;
        }
      } catch {
        // ignore malformed messages
      }
    };

    return () => {
      ws.close();
      wsRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [callId]);

  // Clean up mic and audio contexts on unmount
  useEffect(() => {
    return () => {
      stopMicCapture();
      micContextRef.current?.close();
      playbackContextRef.current?.close();
      if (speakingTimeoutRef.current) clearTimeout(speakingTimeoutRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Play received audio chunk
  const playAudioChunk = useCallback((base64Audio: string) => {
    if (!playbackContextRef.current) {
      playbackContextRef.current = new AudioContext({ sampleRate: 24000 });
      playbackTimeRef.current = 0;
    }
    const ctx = playbackContextRef.current;

    const binaryStr = atob(base64Audio);
    const bytes = new Uint8Array(binaryStr.length);
    for (let i = 0; i < binaryStr.length; i++) {
      bytes[i] = binaryStr.charCodeAt(i);
    }

    // PCM16 little-endian to Float32
    const pcm16 = new Int16Array(bytes.buffer);
    const float32 = new Float32Array(pcm16.length);
    for (let i = 0; i < pcm16.length; i++) {
      float32[i] = pcm16[i] / 32768;
    }

    // Compute output volume from decoded audio
    const rms = computeRMS(float32);
    const smoothed = smooth(outputVolumeRef.current, Math.min(rms * 5, 1));
    outputVolumeRef.current = smoothed;
    setOutputVolume(smoothed);

    // Mark as speaking, reset timeout
    setIsSpeaking(true);
    if (speakingTimeoutRef.current) clearTimeout(speakingTimeoutRef.current);
    speakingTimeoutRef.current = setTimeout(() => {
      setIsSpeaking(false);
      outputVolumeRef.current = 0;
      setOutputVolume(0);
    }, 300);

    const buffer = ctx.createBuffer(1, float32.length, 24000);
    buffer.copyToChannel(float32, 0);

    const source = ctx.createBufferSource();
    source.buffer = buffer;
    source.connect(ctx.destination);

    const now = ctx.currentTime;
    const startTime = Math.max(now, playbackTimeRef.current);
    source.start(startTime);
    playbackTimeRef.current = startTime + buffer.duration;

    // Track for interruption flushing
    activeSourcesRef.current.push(source);
    source.onended = () => {
      activeSourcesRef.current = activeSourcesRef.current.filter(
        (s) => s !== source
      );
    };
  }, []);

  // Flush all queued audio (called on user interruption)
  const clearAudio = useCallback(() => {
    activeSourcesRef.current.forEach((s) => {
      try {
        s.stop();
      } catch {
        // already stopped
      }
    });
    activeSourcesRef.current = [];
    playbackTimeRef.current = 0;
  }, []);

  // Start mic capture
  const startMicCapture = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: 24000,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });
      micStreamRef.current = stream;

      const ctx = new AudioContext({ sampleRate: 24000 });
      micContextRef.current = ctx;

      const source = ctx.createMediaStreamSource(stream);
      // 4096 buffer size, mono in, mono out
      const processor = ctx.createScriptProcessor(4096, 1, 1);
      processorRef.current = processor;

      processor.onaudioprocess = (e) => {
        if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;

        const float32 = e.inputBuffer.getChannelData(0);

        // Compute input volume from mic audio
        const micRms = computeRMS(float32);
        const micSmoothed = smooth(inputVolumeRef.current, Math.min(micRms * 5, 1));
        inputVolumeRef.current = micSmoothed;
        setInputVolume(micSmoothed);

        // Float32 to PCM16 little-endian
        const pcm16 = new Int16Array(float32.length);
        for (let i = 0; i < float32.length; i++) {
          const s = Math.max(-1, Math.min(1, float32[i]));
          pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
        }

        const bytes = new Uint8Array(pcm16.buffer);
        let binary = "";
        for (let i = 0; i < bytes.length; i++) {
          binary += String.fromCharCode(bytes[i]);
        }
        const base64 = btoa(binary);

        wsRef.current.send(JSON.stringify({ type: "audio", audio: base64 }));
      };

      source.connect(processor);
      processor.connect(ctx.destination);
      setMicActive(true);
    } catch {
      setError("Microphone access denied");
    }
  }, []);

  // Stop mic capture
  const stopMicCapture = useCallback(() => {
    processorRef.current?.disconnect();
    processorRef.current = null;

    micStreamRef.current?.getTracks().forEach((t) => t.stop());
    micStreamRef.current = null;

    micContextRef.current?.close();
    micContextRef.current = null;

    inputVolumeRef.current = 0;
    setInputVolume(0);
    setMicActive(false);
  }, []);

  // Toggle mic
  const toggleMic = useCallback(() => {
    if (micActive) {
      stopMicCapture();
    } else {
      startMicCapture();
    }
  }, [micActive, startMicCapture, stopMicCapture]);

  // Send start message
  const start = useCallback(
    (targetProfile: TargetProfile) => {
      if (
        startedRef.current ||
        !wsRef.current ||
        wsRef.current.readyState !== WebSocket.OPEN
      )
        return;
      startedRef.current = true;
      wsRef.current.send(
        JSON.stringify({ type: "start", target_profile: targetProfile })
      );
    },
    []
  );

  // Send text message
  const sendText = useCallback((text: string) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    wsRef.current.send(JSON.stringify({ type: "text", text }));
  }, []);

  // Stop call
  const stop = useCallback(() => {
    stopMicCapture();
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "stop" }));
    }
  }, [stopMicCapture]);

  return {
    connected,
    error,
    transcript,
    micActive,
    toggleMic,
    sendText,
    start,
    stop,
    outputVolume,
    inputVolume,
    isSpeaking,
  };
}
