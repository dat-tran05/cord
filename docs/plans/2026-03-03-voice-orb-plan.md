# Voice Orb Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a WebGL glowing orb animation to the voice chat UI that reacts to audio in real-time, displayed in a two-panel layout (35% orb / 65% transcript).

**Architecture:** Custom Three.js orb rendered via React Three Fiber in the left panel of a refactored VoiceChat component. Audio volume levels are extracted from existing PCM16 streams in `useVoiceChat` and fed to the orb as props. Simplex noise drives vertex displacement; bloom post-processing creates the glow.

**Tech Stack:** Three.js, React Three Fiber, @react-three/postprocessing, simplex-noise, Next.js 16, React 19, Tailwind v4

**Design doc:** `docs/plans/2026-03-03-voice-orb-design.md`

---

### Task 1: Install Dependencies

**Files:**
- Modify: `frontend/package.json`

**Step 1: Install Three.js and React Three Fiber packages**

Run from `frontend/`:
```bash
npm install three @react-three/fiber @react-three/drei @react-three/postprocessing simplex-noise postprocessing
npm install -D @types/three
```

**Step 2: Verify install**

Run: `cd frontend && npx next build`
Expected: Build succeeds with no errors.

**Step 3: Commit**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "chore: add three.js, react-three-fiber, postprocessing, simplex-noise deps"
```

---

### Task 2: Add Volume Tracking to useVoiceChat

**Files:**
- Modify: `frontend/src/hooks/useVoiceChat.ts`

This task adds `outputVolume`, `inputVolume`, and `isSpeaking` to the hook by computing RMS from existing audio buffers and applying EMA smoothing.

**Step 1: Add volume state and refs**

At the top of `useVoiceChat` (after existing state on line 25), add:

```typescript
const [outputVolume, setOutputVolume] = useState(0);
const [inputVolume, setInputVolume] = useState(0);
const [isSpeaking, setIsSpeaking] = useState(false);

const outputVolumeRef = useRef(0);
const inputVolumeRef = useRef(0);
const speakingTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
```

**Step 2: Add RMS helper function**

Above the `useVoiceChat` function (after the `getWsUrl` function, around line 9), add:

```typescript
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
```

**Step 3: Tap into playAudioChunk for output volume**

Inside `playAudioChunk` (currently at line 94), after the Float32 conversion loop (line 111) and before `ctx.createBuffer` (line 114), add:

```typescript
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
```

The `* 5` amplification and `Math.min(..., 1)` clamp ensures the 0-1 range is well-utilized since PCM16 voice audio tends to have low RMS values.

**Step 4: Tap into mic processor for input volume**

Inside `startMicCapture`, within the `processor.onaudioprocess` handler (currently at line 148), after `const float32 = e.inputBuffer.getChannelData(0);` (line 151), add:

```typescript
// Compute input volume from mic audio
const micRms = computeRMS(float32);
const micSmoothed = smooth(inputVolumeRef.current, Math.min(micRms * 5, 1));
inputVolumeRef.current = micSmoothed;
setInputVolume(micSmoothed);
```

**Step 5: Reset input volume on mic stop**

Inside `stopMicCapture` (currently at line 178), before `setMicActive(false)` (line 188), add:

```typescript
inputVolumeRef.current = 0;
setInputVolume(0);
```

**Step 6: Clean up speaking timeout on unmount**

Inside the cleanup useEffect (currently at line 84), in the return function, add:

```typescript
if (speakingTimeoutRef.current) clearTimeout(speakingTimeoutRef.current);
```

**Step 7: Expose new values in return object**

Update the return statement (currently at line 231) to include the new values:

```typescript
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
```

**Step 8: Verify build**

Run: `cd frontend && npx next build`
Expected: Build succeeds with no type errors.

**Step 9: Commit**

```bash
git add frontend/src/hooks/useVoiceChat.ts
git commit -m "feat: add audio volume tracking to useVoiceChat hook"
```

---

### Task 3: Create the VoiceOrb Component

**Files:**
- Create: `frontend/src/components/VoiceOrb.tsx`

This is the core visual component. It renders a Three.js canvas with an icosahedron whose vertices are displaced by simplex noise modulated by audio volume, with bloom post-processing for the glow.

**Step 1: Create VoiceOrb.tsx**

Create `frontend/src/components/VoiceOrb.tsx` with the following content:

```tsx
"use client";
import { useRef, useMemo } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { Bloom, EffectComposer } from "@react-three/postprocessing";
import { createNoise3D } from "simplex-noise";
import * as THREE from "three";

interface VoiceOrbProps {
  outputVolume: number;
  inputVolume: number;
  isSpeaking: boolean;
  ended: boolean;
}

// Colors
const PRIMARY_BLUE = new THREE.Color("#3B82F6");
const SECONDARY_CYAN = new THREE.Color("#06B6D4");

function OrbMesh({
  outputVolume,
  inputVolume,
  isSpeaking,
  ended,
}: VoiceOrbProps) {
  const meshRef = useRef<THREE.Mesh>(null);
  const geometryRef = useRef<THREE.IcosahedronGeometry>(null);
  const noise3D = useMemo(() => createNoise3D(), []);

  // Store original vertex positions
  const originalPositions = useRef<Float32Array | null>(null);

  useFrame(({ clock }) => {
    if (!meshRef.current || !geometryRef.current) return;

    const geo = geometryRef.current;
    const positions = geo.attributes.position;

    // Initialize original positions on first frame
    if (!originalPositions.current) {
      originalPositions.current = new Float32Array(positions.array);
    }

    const time = clock.elapsedTime;
    const orig = originalPositions.current;

    // Determine displacement amplitude based on state
    let amplitude: number;
    if (ended) {
      amplitude = 0;
    } else if (isSpeaking) {
      amplitude = 0.05 + outputVolume * 0.4; // Strong displacement when speaking
    } else {
      amplitude = 0.02 + inputVolume * 0.15; // Subtle when listening
    }

    // Breathing effect (always present unless ended)
    const breathe = ended ? 0 : Math.sin(time * 0.8) * 0.015;

    // Displace vertices using simplex noise
    for (let i = 0; i < positions.count; i++) {
      const ox = orig[i * 3];
      const oy = orig[i * 3 + 1];
      const oz = orig[i * 3 + 2];

      // Normalize to get direction
      const len = Math.sqrt(ox * ox + oy * oy + oz * oz);
      const nx = ox / len;
      const ny = oy / len;
      const nz = oz / len;

      // 3D noise based on vertex position + time
      const noiseVal = noise3D(
        nx * 1.5 + time * 0.3,
        ny * 1.5 + time * 0.3,
        nz * 1.5
      );

      const displacement = noiseVal * amplitude + breathe;

      positions.setXYZ(
        i,
        ox + nx * displacement,
        oy + ny * displacement,
        oz + nz * displacement
      );
    }

    positions.needsUpdate = true;
    geo.computeVertexNormals();

    // Ended state: shrink
    if (ended) {
      meshRef.current.scale.lerp(new THREE.Vector3(0, 0, 0), 0.03);
    } else {
      const s = 1 + breathe;
      meshRef.current.scale.lerp(new THREE.Vector3(s, s, s), 0.1);
    }
  });

  // Emissive color shifts between blue (idle/listening) and cyan (speaking)
  const emissiveColor = isSpeaking
    ? SECONDARY_CYAN
    : PRIMARY_BLUE;
  const emissiveIntensity = ended
    ? 0
    : isSpeaking
      ? 1.5 + outputVolume * 2
      : 0.8 + inputVolume * 0.5;

  return (
    <mesh ref={meshRef}>
      <icosahedronGeometry ref={geometryRef} args={[1, 6]} />
      <meshStandardMaterial
        color={PRIMARY_BLUE}
        emissive={emissiveColor}
        emissiveIntensity={emissiveIntensity}
        roughness={0.3}
        metalness={0.1}
        toneMapped={false}
      />
    </mesh>
  );
}

function OrbScene(props: VoiceOrbProps) {
  const bloomIntensity = props.ended
    ? 0
    : props.isSpeaking
      ? 0.8 + props.outputVolume * 1.2
      : 0.4;

  return (
    <>
      <ambientLight intensity={0.3} />
      <pointLight position={[5, 5, 5]} intensity={0.8} color="#60A5FA" />
      <pointLight position={[-5, -3, 3]} intensity={0.4} color="#06B6D4" />

      <OrbMesh {...props} />

      <EffectComposer>
        <Bloom
          mipmapBlur
          luminanceThreshold={0.4}
          luminanceSmoothing={0.6}
          intensity={bloomIntensity}
        />
      </EffectComposer>
    </>
  );
}

export function VoiceOrb(props: VoiceOrbProps) {
  // Status label text
  const statusText = props.ended
    ? "Call ended"
    : props.isSpeaking
      ? "Speaking..."
      : "Listening...";

  return (
    <div className="flex h-full flex-col items-center justify-center gap-4"
      style={{ background: "#09090b" }}
    >
      <div className="w-full flex-1 min-h-0">
        <Canvas
          camera={{ position: [0, 0, 3.5], fov: 45 }}
          gl={{ antialias: true, alpha: true }}
          style={{ background: "transparent" }}
        >
          <OrbScene {...props} />
        </Canvas>
      </div>
      <p className="pb-6 text-xs font-medium tracking-wider uppercase text-muted-foreground">
        {statusText}
      </p>
    </div>
  );
}
```

**Step 2: Verify build**

Run: `cd frontend && npx next build`
Expected: Build succeeds. The component isn't rendered yet (that's Task 4), but types and imports must resolve.

**Step 3: Commit**

```bash
git add frontend/src/components/VoiceOrb.tsx
git commit -m "feat: add VoiceOrb component with Three.js audio-reactive animation"
```

---

### Task 4: Refactor VoiceChat to Two-Panel Layout

**Files:**
- Modify: `frontend/src/components/VoiceChat.tsx`

This task refactors the existing single-column VoiceChat into a side-by-side layout: orb on the left (35%), transcript on the right (65%). The VoiceOrb component is dynamically imported with `ssr: false` since Three.js requires a browser context.

**Step 1: Add dynamic import for VoiceOrb**

At the top of `VoiceChat.tsx`, after the existing imports (line 9), add:

```tsx
import dynamic from "next/dynamic";

const VoiceOrb = dynamic(
  () => import("@/components/VoiceOrb").then((mod) => mod.VoiceOrb),
  { ssr: false }
);
```

**Step 2: Destructure new hook values**

Update the `useVoiceChat` destructuring (currently lines 19-28) to include the new values:

```tsx
const {
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
} = useVoiceChat(callId);
```

**Step 3: Refactor the JSX return to two-panel layout**

Replace the entire return statement (lines 87-194) with:

```tsx
return (
  <div className="flex h-screen flex-col bg-background">
    {/* Header */}
    <header className="sticky top-0 z-10 flex items-center justify-between border-b border-border/60 bg-background/80 backdrop-blur-lg px-4 h-14">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon-sm" onClick={handleBackArrow}>
          <ArrowLeft className="size-4" />
        </Button>
        <h1 className="text-sm font-semibold">Voice Call</h1>
        <span
          className={cn(
            "size-2 rounded-full",
            connected ? "bg-green-500 animate-pulse" : "bg-red-500"
          )}
          title={connected ? "Connected" : "Disconnected"}
        />
      </div>
      {!ended && (
        <Button variant="destructive" size="sm" onClick={handleEnd}>
          <PhoneOff className="size-3.5" />
          End Call
        </Button>
      )}
    </header>

    {/* Error banner */}
    {error && (
      <div className="border-b border-destructive/30 bg-destructive/10 px-4 py-2 text-sm text-destructive">
        {error}
      </div>
    )}

    {/* Two-panel body: orb (35%) | transcript (65%) */}
    <div className="flex flex-1 min-h-0">
      {/* Orb panel */}
      <div className="w-[35%] border-r border-border/60">
        <VoiceOrb
          outputVolume={outputVolume}
          inputVolume={inputVolume}
          isSpeaking={isSpeaking}
          ended={ended}
        />
      </div>

      {/* Transcript panel */}
      <div className="w-[65%] overflow-y-auto px-4 py-6">
        <div className="mx-auto max-w-2xl space-y-4">
          {transcript.length === 0 && !ended && (
            <p className="text-center text-sm text-muted-foreground pt-12">
              {connected
                ? "Waiting for conversation to begin..."
                : "Connecting to voice service..."}
            </p>
          )}
          {transcript.map((msg, i) => (
            <div
              key={i}
              className={cn(
                "flex",
                msg.role === "agent" ? "justify-start" : "justify-end"
              )}
            >
              <div
                className={cn(
                  "max-w-[80%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed",
                  msg.role === "agent"
                    ? "bg-card text-card-foreground border border-border/50"
                    : "bg-primary text-primary-foreground"
                )}
              >
                {msg.text}
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>
      </div>
    </div>

    {/* Controls */}
    {!ended && (
      <div className="border-t border-border/60 bg-background/80 backdrop-blur-lg p-4">
        <div className="mx-auto flex max-w-2xl items-center gap-2">
          {/* Mic toggle */}
          <Button
            variant={micActive ? "destructive" : "outline"}
            size="icon"
            onClick={toggleMic}
            className={cn(
              "shrink-0 transition-shadow",
              micActive && "shadow-[0_0_16px_rgba(239,68,68,0.3)]"
            )}
            title={micActive ? "Mute microphone" : "Unmute microphone"}
          >
            {micActive ? (
              <Mic className="size-4" />
            ) : (
              <MicOff className="size-4" />
            )}
          </Button>

          {/* Text input */}
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSend()}
            placeholder="Type a message..."
            className="flex-1"
          />
          <Button
            onClick={handleSend}
            disabled={!input.trim()}
            size="icon"
          >
            <Send className="size-4" />
          </Button>
        </div>
      </div>
    )}
  </div>
);
```

The key change is the middle section: instead of a single `flex-1 overflow-y-auto` div, it's now a `flex flex-1 min-h-0` container with two children (35%/65% split). The orb panel gets `h-full` via the VoiceOrb's own flex layout.

**Step 4: Remove unused import**

The `useState` import at line 2 is still used, but verify no other imports became unused.

**Step 5: Verify build**

Run: `cd frontend && npx next build`
Expected: Build succeeds with no type errors.

**Step 6: Commit**

```bash
git add frontend/src/components/VoiceChat.tsx
git commit -m "feat: refactor VoiceChat to two-panel layout with voice orb"
```

---

### Task 5: Visual Tuning and Manual Testing

**Files:**
- Potentially adjust: `frontend/src/components/VoiceOrb.tsx`
- Potentially adjust: `frontend/src/hooks/useVoiceChat.ts`

This task is for manual testing and fine-tuning the visual parameters.

**Step 1: Start the dev environment**

Run in separate terminals:
```bash
# Terminal 1
redis-server

# Terminal 2
cd backend && uvicorn app.main:app --reload --port 8000

# Terminal 3
cd frontend && npm run dev
```

**Step 2: Test the voice call flow**

1. Navigate to the dashboard at `http://localhost:3000`
2. Create a target (or use an existing one)
3. Start a new call
4. Verify: two-panel layout appears with orb on left, transcript on right
5. Verify: orb has a gentle breathing animation in idle/connecting state
6. Verify: when AI speaks, orb vertices displace and glow intensifies
7. Verify: when mic is active, orb shows subtle response to input volume
8. Verify: ending the call causes the orb to shrink and fade
9. Verify: status label below orb updates ("Listening...", "Speaking...", "Call ended")

**Step 3: Tune parameters if needed**

Key knobs to adjust in `VoiceOrb.tsx`:
- `args={[1, 6]}` on `icosahedronGeometry` — change `6` to `7` or `8` for smoother sphere (at cost of more vertices)
- `amplitude` values in `OrbMesh` — increase/decrease the `0.4` multiplier for speaking displacement
- `emissiveIntensity` ranges — controls brightness of the glow
- `bloomIntensity` ranges — controls how much the glow spreads
- `luminanceThreshold` on `Bloom` — lower = more glow, higher = more selective
- `EMA_DECAY` in `useVoiceChat.ts` — higher (0.9) = smoother but laggier, lower (0.7) = more responsive but jittery
- `* 5` volume amplification — adjust based on actual audio levels

**Step 4: Final build check**

Run: `cd frontend && npx next build`
Expected: Build succeeds.

**Step 5: Commit any tuning changes**

```bash
git add -A
git commit -m "fix: tune voice orb visual parameters"
```

---

## Summary of Changes

| File | Action | Description |
|---|---|---|
| `frontend/package.json` | Modify | Add three, @react-three/fiber, @react-three/drei, @react-three/postprocessing, simplex-noise, postprocessing deps |
| `frontend/src/hooks/useVoiceChat.ts` | Modify | Add `outputVolume`, `inputVolume`, `isSpeaking` with RMS + EMA |
| `frontend/src/components/VoiceOrb.tsx` | Create | Three.js orb with simplex noise displacement + bloom glow |
| `frontend/src/components/VoiceChat.tsx` | Modify | Refactor to 35/65 two-panel layout, integrate VoiceOrb |

Total: 1 new file, 3 modified files. No backend changes.
