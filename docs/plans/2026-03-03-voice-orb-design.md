# Voice Orb UI Design

## Summary

Add a WebGL-rendered glowing orb animation to the voice chat UI that reacts to audio activity in real-time. The orb serves as a visual indicator of AI voice state (idle, listening, speaking) alongside the existing transcript view.

## Layout

Two-panel layout (35% orb / 65% transcript) replaces the current single-column VoiceChat:

```
┌──────────────────────────────────────────────┐
│  ← Voice Call  ●  Connected          [End]   │
├──────────────┬───────────────────────────────┤
│              │  Agent: Hello, I'm calling... │
│              │          You: Hi there        │
│   ✦ ORB ✦    │  Agent: So about this pen...  │
│              │          You: I don't need... │
│  status      │  Agent: But consider this...  │
│  label       │                               │
│   ~35%       │          ~65%                 │
├──────────────┴───────────────────────────────┤
│  [🎤 Mic]  [Type a message...] [Send]        │
└──────────────────────────────────────────────┘
```

- Left panel: near-black background (#09090b), orb centered vertically, status label below ("Listening...", "Speaking...")
- Right panel: existing transcript chat bubbles (scrollable)
- Bottom bar: full width — mic toggle, text input, send, end call
- Mobile/narrow: stacks vertically (orb on top, smaller) or compact orb in header

## Orb Component

### Technology

- Three.js + React Three Fiber + @react-three/drei
- @react-three/postprocessing (UnrealBloomEffect for glow)
- simplex-noise (vertex displacement)

### Geometry & Material

- IcosahedronGeometry with 6-8 subdivisions (sphere-like, deformable)
- Custom shader material: blue-to-cyan gradient (cooler at top, warmer at bottom)
- Vertices displaced per-frame using 3D simplex noise, amplitude driven by audio volume

### Animation States

| State | Visual | Trigger |
|---|---|---|
| Idle/Connecting | Gentle breathing pulse (scale 0.98→1.02 over 3s), soft blue glow | Default |
| Listening | Deeper blue, subtle shimmer, low-amplitude vertex noise | Mic active, AI not speaking |
| Speaking | Brighter cyan shift, vertices displace with audio volume (4x amplified), glow intensifies | Audio chunks arriving from WebSocket |
| Ended | Shrinks and fades out, glow dissipates | Call ends |

### Color Palette

- Primary: #3B82F6 (blue-500)
- Secondary: #06B6D4 (cyan-500)
- Glow: #60A5FA (blue-400) at 30% opacity
- Background: #09090b (zinc-950)

### Glow/Bloom

UnrealBloomEffect from @react-three/postprocessing. Bloom intensity maps to audio level — brighter when speaking, dimmer when idle.

## Audio Data Pipeline

### Volume Extraction

Compute RMS (root mean square) of audio samples to derive volume level (0→1):

- **AI output**: Extract from existing `playAudioChunk` (PCM16 → Float32 already decoded). Compute RMS of Float32 buffer.
- **User mic**: Extract from existing `onaudioprocess` handler (Float32 already available). Compute RMS of input buffer.

### Smoothing

Apply exponential moving average (EMA, decay ~0.85) to prevent jittery animation:
```
smoothedVolume = decay * previousVolume + (1 - decay) * rawVolume
```

### New Hook State

`useVoiceChat` exposes three new values:
- `outputVolume: number` — 0-1, smoothed AI speaking level
- `inputVolume: number` — 0-1, smoothed user mic level
- `isSpeaking: boolean` — true when audio chunks are arriving

## Component Architecture

### New Files

- `frontend/src/components/VoiceOrb.tsx` — React Three Fiber canvas, icosahedron mesh, custom shader, bloom post-processing. Props: `outputVolume`, `inputVolume`, `isSpeaking`, `ended`.
- `frontend/src/components/OrbMaterial.tsx` — Custom shader material with vertex displacement + blue/cyan gradient.

### Modified Files

- `frontend/src/hooks/useVoiceChat.ts` — Add `outputVolume`, `inputVolume`, `isSpeaking` state with RMS + EMA smoothing.
- `frontend/src/components/VoiceChat.tsx` — Refactor from single-column to two-panel layout; render `VoiceOrb` in left panel, transcript in right panel.

### New Dependencies

- `three` + `@types/three`
- `@react-three/fiber`
- `@react-three/drei`
- `@react-three/postprocessing`
- `simplex-noise`

### No Changes To

Backend, API, WebSocket protocol, or any other frontend files.
