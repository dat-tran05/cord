"use client";
import { useEffect, useRef } from "react";
import * as THREE from "three";
import { createNoise3D } from "simplex-noise";

interface VoiceOrbProps {
  outputVolume: number;
  inputVolume: number;
  isSpeaking: boolean;
  ended: boolean;
}

export function VoiceOrb({
  outputVolume,
  inputVolume,
  isSpeaking,
  ended,
}: VoiceOrbProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const groupRef = useRef<THREE.Group | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const ballRef = useRef<THREE.Mesh | null>(null);
  const originalPositionsRef = useRef<Float32Array | null>(null);
  const noiseRef = useRef(createNoise3D());
  const animFrameRef = useRef<number>(0);

  // Store latest props in refs so the render loop always reads current values
  const outputVolumeRef = useRef(outputVolume);
  const inputVolumeRef = useRef(inputVolume);
  const isSpeakingRef = useRef(isSpeaking);
  const endedRef = useRef(ended);

  useEffect(() => {
    outputVolumeRef.current = outputVolume;
  }, [outputVolume]);
  useEffect(() => {
    inputVolumeRef.current = inputVolume;
  }, [inputVolume]);
  useEffect(() => {
    isSpeakingRef.current = isSpeaking;
  }, [isSpeaking]);
  useEffect(() => {
    endedRef.current = ended;
  }, [ended]);

  useEffect(() => {
    if (!containerRef.current) return;

    const container = containerRef.current;
    const noise = noiseRef.current;

    // Scene setup
    const scene = new THREE.Scene();
    const group = new THREE.Group();
    const camera = new THREE.PerspectiveCamera(
      20,
      container.clientWidth / container.clientHeight,
      0.5,
      100
    );
    camera.position.set(0, 0, 100);
    camera.lookAt(scene.position);
    scene.add(camera);

    sceneRef.current = scene;
    groupRef.current = group;
    cameraRef.current = camera;

    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
    renderer.setSize(container.clientWidth, container.clientHeight);
    renderer.setPixelRatio(window.devicePixelRatio);
    rendererRef.current = renderer;

    // Icosahedron with wireframe
    const geometry = new THREE.IcosahedronGeometry(10, 8);
    const material = new THREE.MeshLambertMaterial({
      color: 0x3b82f6,
      wireframe: true,
    });
    const ball = new THREE.Mesh(geometry, material);
    ball.position.set(0, 0, 0);
    ballRef.current = ball;

    originalPositionsRef.current = new Float32Array(
      ball.geometry.attributes.position.array
    );

    group.add(ball);

    // Lighting
    const ambientLight = new THREE.AmbientLight(0x60a5fa, 0.5);
    scene.add(ambientLight);

    const spotLight = new THREE.SpotLight(0x06b6d4);
    spotLight.intensity = 0.9;
    spotLight.position.set(-10, 40, 20);
    spotLight.lookAt(ball.position);
    scene.add(spotLight);

    scene.add(group);
    container.appendChild(renderer.domElement);

    // Animation loop
    const render = () => {
      if (!groupRef.current || !ballRef.current || !cameraRef.current || !rendererRef.current || !sceneRef.current) return;

      groupRef.current.rotation.y += 0.005;

      const speaking = isSpeakingRef.current;
      const endedNow = endedRef.current;
      const volume = speaking
        ? outputVolumeRef.current
        : inputVolumeRef.current * 0.3;

      if (!endedNow && ballRef.current) {
        // Morph the ball with audio volume
        const geo = ballRef.current.geometry as THREE.BufferGeometry;
        const posAttr = geo.getAttribute("position");

        for (let i = 0; i < posAttr.count; i++) {
          const vertex = new THREE.Vector3(
            posAttr.getX(i),
            posAttr.getY(i),
            posAttr.getZ(i)
          );

          const offset = 10;
          const amp = 2.5;
          const time = window.performance.now();
          vertex.normalize();
          const rf = 0.00001;
          const distance =
            offset +
            volume * 4 +
            noise(
              vertex.x + time * rf * 7,
              vertex.y + time * rf * 8,
              vertex.z + time * rf * 9
            ) *
              amp *
              (volume + 0.1); // +0.1 for subtle idle animation

          vertex.multiplyScalar(distance);
          posAttr.setXYZ(i, vertex.x, vertex.y, vertex.z);
        }

        posAttr.needsUpdate = true;
        geo.computeVertexNormals();
      } else if (endedNow && ballRef.current && originalPositionsRef.current) {
        // Reset to original shape
        const geo = ballRef.current.geometry as THREE.BufferGeometry;
        const posAttr = geo.getAttribute("position");
        const orig = originalPositionsRef.current;

        for (let i = 0; i < posAttr.count; i++) {
          posAttr.setXYZ(i, orig[i * 3], orig[i * 3 + 1], orig[i * 3 + 2]);
        }
        posAttr.needsUpdate = true;
        geo.computeVertexNormals();
      }

      rendererRef.current.render(sceneRef.current, cameraRef.current);
      animFrameRef.current = requestAnimationFrame(render);
    };

    render();

    // Resize handler
    const onResize = () => {
      if (!cameraRef.current || !rendererRef.current || !container) return;
      cameraRef.current.aspect = container.clientWidth / container.clientHeight;
      cameraRef.current.updateProjectionMatrix();
      rendererRef.current.setSize(container.clientWidth, container.clientHeight);
    };

    window.addEventListener("resize", onResize);

    return () => {
      window.removeEventListener("resize", onResize);
      cancelAnimationFrame(animFrameRef.current);
      renderer.dispose();
      geometry.dispose();
      material.dispose();
      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
    };
  }, []);

  const statusText = ended
    ? "Call ended"
    : isSpeaking
      ? "Speaking..."
      : "Listening...";

  return (
    <div
      className="flex h-full flex-col items-center justify-center"
      style={{ background: "#09090b" }}
    >
      <div ref={containerRef} className="w-full flex-1 min-h-0" />
      <p className="pb-6 text-xs font-medium tracking-wider uppercase text-muted-foreground">
        {statusText}
      </p>
    </div>
  );
}
