/**
 * Hyperspeed Highway Effect using Three.js
 * Creates a futuristic highway with moving lights and cars
 */

import * as THREE from 'three';
import { EffectComposer } from 'postprocessing';

export class Hyperspeed {
  constructor(container, options = {}) {
    this.container = container;
    
    // Default options matching the provided config
    this.options = {
      distortion: options.distortion || 'turbulentDistortion',
      length: options.length || 400,
      roadWidth: options.roadWidth || 10,
      islandWidth: options.islandWidth || 2,
      lanesPerRoad: options.lanesPerRoad || 3,
      fov: options.fov || 90,
      fovSpeedUp: options.fovSpeedUp || 150,
      speedUp: options.speedUp || 2,
      carLightsFade: options.carLightsFade || 0.4,
      totalSideLightSticks: options.totalSideLightSticks || 20,
      lightPairsPerRoadWay: options.lightPairsPerRoadWay || 40,
      shoulderLinesWidthPercentage: options.shoulderLinesWidthPercentage || 0.05,
      brokenLinesWidthPercentage: options.brokenLinesWidthPercentage || 0.1,
      brokenLinesLengthPercentage: options.brokenLinesLengthPercentage || 0.5,
      lightStickWidth: options.lightStickWidth || [0.12, 0.5],
      lightStickHeight: options.lightStickHeight || [1.3, 1.7],
      movingAwaySpeed: options.movingAwaySpeed || [60, 80],
      movingCloserSpeed: options.movingCloserSpeed || [-120, -160],
      carLightsLength: options.carLightsLength || [12, 80],
      carLightsRadius: options.carLightsRadius || [0.05, 0.14],
      carWidthPercentage: options.carWidthPercentage || [0.3, 0.5],
      carShiftX: options.carShiftX || [-0.8, 0.8],
      carFloorSeparation: options.carFloorSeparation || [0, 5],
      colors: {
        roadColor: options.colors?.roadColor || 0x080808,
        islandColor: options.colors?.islandColor || 0x0a0a0a,
        background: options.colors?.background || 0x000000,
        shoulderLines: options.colors?.shoulderLines || 0x131318,
        brokenLines: options.colors?.brokenLines || 0x131318,
        leftCars: options.colors?.leftCars || [0xd856bf, 0x6750a2, 0xc247ac],
        rightCars: options.colors?.rightCars || [0x03b3c3, 0x0e5c75, 0x324555],
        sticks: options.colors?.sticks || 0x03b3c3
      }
    };

    this.time = 0;
    this.raf = null;
    this.lightSticks = [];
    this.carLights = [];

    this.init();
  }

  init() {
    const width = this.container.clientWidth;
    const height = this.container.clientHeight;

    // Create scene
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(this.options.colors.background);
    this.scene.fog = new THREE.Fog(this.options.colors.background, 10, this.options.length * 0.8);

    // Create camera
    this.camera = new THREE.PerspectiveCamera(
      this.options.fov,
      width / height,
      0.1,
      this.options.length * 2
    );
    this.camera.position.set(0, 1.5, 0);
    this.camera.rotation.x = -0.05;

    // Create renderer
    this.renderer = new THREE.WebGLRenderer({ 
      antialias: true,
      alpha: false
    });
    this.renderer.setSize(width, height);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    
    Object.assign(this.renderer.domElement.style, {
      position: 'absolute',
      inset: '0',
      width: '100%',
      height: '100%',
      display: 'block'
    });

    this.container.appendChild(this.renderer.domElement);

    // Create road
    this.createRoad();
    
    // Create light sticks
    this.createLightSticks();
    
    // Create car lights
    this.createCarLights();

    // Setup resize observer
    this.resizeObserver = new ResizeObserver(() => this.resize());
    this.resizeObserver.observe(this.container);

    // Start animation
    this.startAnimation();
  }

  createRoad() {
    const roadWidth = this.options.roadWidth;
    const islandWidth = this.options.islandWidth;
    const length = this.options.length;
    
    // Left road
    const leftRoadGeometry = new THREE.PlaneGeometry(roadWidth, length, 20, 200);
    const leftRoadMaterial = new THREE.MeshBasicMaterial({ 
      color: this.options.colors.roadColor,
      side: THREE.DoubleSide
    });
    const leftRoad = new THREE.Mesh(leftRoadGeometry, leftRoadMaterial);
    leftRoad.rotation.x = -Math.PI / 2;
    leftRoad.position.set(-(roadWidth / 2 + islandWidth / 2), 0, -length / 2);
    this.scene.add(leftRoad);

    // Right road
    const rightRoad = leftRoad.clone();
    rightRoad.position.set(roadWidth / 2 + islandWidth / 2, 0, -length / 2);
    this.scene.add(rightRoad);

    // Center island
    const islandGeometry = new THREE.PlaneGeometry(islandWidth, length, 1, 200);
    const islandMaterial = new THREE.MeshBasicMaterial({ 
      color: this.options.colors.islandColor,
      side: THREE.DoubleSide
    });
    const island = new THREE.Mesh(islandGeometry, islandMaterial);
    island.rotation.x = -Math.PI / 2;
    island.position.set(0, 0, -length / 2);
    this.scene.add(island);

    // Lane lines
    this.createLaneLines(leftRoad, rightRoad);
  }

  createLaneLines(leftRoad, rightRoad) {
    const roadWidth = this.options.roadWidth;
    const length = this.options.length;
    const lanesPerRoad = this.options.lanesPerRoad;
    
    // Broken center lines for lanes
    const laneSpacing = roadWidth / lanesPerRoad;
    const lineLength = length * this.options.brokenLinesLengthPercentage;
    const lineWidth = roadWidth * this.options.brokenLinesWidthPercentage;
    
    for (let lane = 1; lane < lanesPerRoad; lane++) {
      const xOffset = -roadWidth / 2 + lane * laneSpacing;
      
      // Left road lanes
      this.createDashedLine(
        xOffset - (roadWidth / 2 + this.options.islandWidth / 2),
        lineLength,
        lineWidth,
        this.options.colors.brokenLines
      );
      
      // Right road lanes
      this.createDashedLine(
        xOffset + (roadWidth / 2 + this.options.islandWidth / 2),
        lineLength,
        lineWidth,
        this.options.colors.brokenLines
      );
    }

    // Shoulder lines
    const shoulderWidth = roadWidth * this.options.shoulderLinesWidthPercentage;
    
    // Left road shoulders
    this.createSolidLine(
      -(roadWidth + this.options.islandWidth / 2),
      length,
      shoulderWidth,
      this.options.colors.shoulderLines
    );
    
    // Right road shoulders
    this.createSolidLine(
      (roadWidth + this.options.islandWidth / 2),
      length,
      shoulderWidth,
      this.options.colors.shoulderLines
    );
  }

  createDashedLine(x, segmentLength, width, color) {
    const length = this.options.length;
    const gap = segmentLength * 1.5;
    const numSegments = Math.floor(length / (segmentLength + gap));
    
    for (let i = 0; i < numSegments; i++) {
      const z = -i * (segmentLength + gap) - segmentLength / 2;
      const geometry = new THREE.PlaneGeometry(width, segmentLength);
      const material = new THREE.MeshBasicMaterial({ color, side: THREE.DoubleSide });
      const line = new THREE.Mesh(geometry, material);
      line.rotation.x = -Math.PI / 2;
      line.position.set(x, 0.01, z);
      line.userData.isDashedLine = true;
      line.userData.initialZ = z;
      this.scene.add(line);
    }
  }

  createSolidLine(x, length, width, color) {
    const geometry = new THREE.PlaneGeometry(width, length);
    const material = new THREE.MeshBasicMaterial({ color, side: THREE.DoubleSide });
    const line = new THREE.Mesh(geometry, material);
    line.rotation.x = -Math.PI / 2;
    line.position.set(x, 0.01, -length / 2);
    this.scene.add(line);
  }

  createLightSticks() {
    const roadWidth = this.options.roadWidth;
    const islandWidth = this.options.islandWidth;
    const length = this.options.length;
    const spacing = length / this.options.totalSideLightSticks;
    
    for (let i = 0; i < this.options.totalSideLightSticks; i++) {
      const z = -i * spacing;
      const height = THREE.MathUtils.randFloat(...this.options.lightStickHeight);
      const width = THREE.MathUtils.randFloat(...this.options.lightStickWidth);
      
      // Left side light sticks
      this.createLightStick(
        -(roadWidth + islandWidth / 2 + 1),
        height,
        z,
        width,
        this.options.colors.sticks
      );
      
      // Right side light sticks
      this.createLightStick(
        (roadWidth + islandWidth / 2 + 1),
        height,
        z,
        width,
        this.options.colors.sticks
      );
    }
  }

  createLightStick(x, height, z, width, color) {
    const geometry = new THREE.BoxGeometry(width, height, width);
    const material = new THREE.MeshBasicMaterial({ color });
    const stick = new THREE.Mesh(geometry, material);
    stick.position.set(x, height / 2, z);
    stick.userData.isLightStick = true;
    stick.userData.initialZ = z;
    
    // Add glow
    const glowGeometry = new THREE.SphereGeometry(width * 2, 8, 8);
    const glowMaterial = new THREE.MeshBasicMaterial({ 
      color,
      transparent: true,
      opacity: 0.3
    });
    const glow = new THREE.Mesh(glowGeometry, glowMaterial);
    glow.position.set(0, height / 2, 0);
    stick.add(glow);
    
    this.lightSticks.push(stick);
    this.scene.add(stick);
  }

  createCarLights() {
    const roadWidth = this.options.roadWidth;
    const islandWidth = this.options.islandWidth;
    
    // Left road cars (moving away)
    for (let i = 0; i < this.options.lightPairsPerRoadWay; i++) {
      this.createCarLight(
        -(roadWidth / 2 + islandWidth / 2),
        'left',
        THREE.MathUtils.randFloat(...this.options.movingAwaySpeed)
      );
    }
    
    // Right road cars (moving closer)
    for (let i = 0; i < this.options.lightPairsPerRoadWay; i++) {
      this.createCarLight(
        (roadWidth / 2 + islandWidth / 2),
        'right',
        THREE.MathUtils.randFloat(...this.options.movingCloserSpeed)
      );
    }
  }

  createCarLight(baseX, direction, speed) {
    const roadWidth = this.options.roadWidth;
    const length = THREE.MathUtils.randFloat(...this.options.carLightsLength);
    const radius = THREE.MathUtils.randFloat(...this.options.carLightsRadius);
    const laneWidth = roadWidth / this.options.lanesPerRoad;
    const lane = Math.floor(Math.random() * this.options.lanesPerRoad);
    const x = baseX + (lane - this.options.lanesPerRoad / 2 + 0.5) * laneWidth + 
              THREE.MathUtils.randFloat(...this.options.carShiftX);
    const y = THREE.MathUtils.randFloat(...this.options.carFloorSeparation);
    const z = Math.random() * -this.options.length;
    
    const colors = direction === 'left' ? 
      this.options.colors.leftCars : 
      this.options.colors.rightCars;
    const color = colors[Math.floor(Math.random() * colors.length)];
    
    const geometry = new THREE.CylinderGeometry(radius, radius, length, 8);
    const material = new THREE.MeshBasicMaterial({ 
      color,
      transparent: true,
      opacity: 0.8
    });
    const light = new THREE.Mesh(geometry, material);
    light.rotation.x = Math.PI / 2;
    light.position.set(x, y, z);
    
    light.userData.isCarLight = true;
    light.userData.speed = speed;
    light.userData.initialZ = z;
    light.userData.direction = direction;
    
    this.carLights.push(light);
    this.scene.add(light);
  }

  resize() {
    const width = this.container.clientWidth || 1;
    const height = this.container.clientHeight || 1;
    
    this.renderer.setSize(width, height);
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
  }

  render() {
    const delta = 0.016; // ~60fps
    this.time += delta;
    
    // Update light sticks (very slow)
    this.lightSticks.forEach(stick => {
      stick.position.z += delta * 8; // Reduced to 8 for very calm effect
      
      if (stick.position.z > 10) {
        stick.position.z = -this.options.length;
      }
    });
    
    // Update car lights
    this.carLights.forEach(light => {
      light.position.z += delta * light.userData.speed;
      
      // Wrap around
      if (light.userData.direction === 'left' && light.position.z > 10) {
        light.position.z = -this.options.length;
      } else if (light.userData.direction === 'right' && light.position.z < -this.options.length) {
        light.position.z = 10;
      }
      
      // Fade based on distance
      const distance = Math.abs(light.position.z);
      const fade = 1 - (distance / this.options.length) * this.options.carLightsFade;
      light.material.opacity = Math.max(0.2, fade);
    });
    
    // Update dashed lines (very slow)
    this.scene.children.forEach(child => {
      if (child.userData.isDashedLine) {
        child.position.z += delta * 8; // Reduced to 8 for very calm effect
        
        if (child.position.z > 10) {
          child.position.z = child.userData.initialZ;
        }
      }
    });
    
    // Render
    this.renderer.render(this.scene, this.camera);
    this.raf = requestAnimationFrame(() => this.render());
  }

  startAnimation() {
    if (this.raf) return;
    this.raf = requestAnimationFrame(() => this.render());
  }

  stopAnimation() {
    if (this.raf) {
      cancelAnimationFrame(this.raf);
      this.raf = null;
    }
  }

  destroy() {
    this.stopAnimation();

    if (this.resizeObserver) {
      this.resizeObserver.disconnect();
    }

    // Clean up Three.js objects
    this.scene.traverse((object) => {
      if (object.geometry) object.geometry.dispose();
      if (object.material) {
        if (Array.isArray(object.material)) {
          object.material.forEach(material => material.dispose());
        } else {
          object.material.dispose();
        }
      }
    });

    if (this.renderer.domElement.parentElement) {
      this.container.removeChild(this.renderer.domElement);
    }
    
    this.renderer.dispose();
  }
}

export default Hyperspeed;
