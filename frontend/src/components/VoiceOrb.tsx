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
