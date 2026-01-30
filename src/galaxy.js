/**
 * Galaxy Background using OGL
 * Beautiful animated starfield with customizable properties
 */

import { Renderer, Camera, Transform, Geometry, Program, Mesh, Color, Vec3 } from 'ogl';

export class Galaxy {
  constructor(container, options = {}) {
    this.container = container;
    
    // Default options
    this.options = {
      mouseRepulsion: options.mouseRepulsion !== undefined ? options.mouseRepulsion : false,
      mouseInteraction: options.mouseInteraction !== undefined ? options.mouseInteraction : true,
      density: options.density || 1,
      glowIntensity: options.glowIntensity || 0.3,
      saturation: options.saturation || 0,
      hueShift: options.hueShift || 140,
      twinkleIntensity: options.twinkleIntensity || 0.3,
      rotationSpeed: options.rotationSpeed || 0.1,
      repulsionStrength: options.repulsionStrength || 2,
      autoCenterRepulsion: options.autoCenterRepulsion || 0,
      starSpeed: options.starSpeed || 0.5,
      speed: options.speed || 1,
    };

    this.mouse = { x: 0, y: 0 };
    this.time = 0;
    this.raf = null;

    this.init();
  }

  init() {
    const width = this.container.clientWidth;
    const height = this.container.clientHeight;

    // Create renderer
    this.renderer = new Renderer({ 
      alpha: true,
      antialias: true,
      dpr: Math.min(window.devicePixelRatio, 2)
    });
    
    this.gl = this.renderer.gl;
    this.gl.clearColor(0, 0, 0, 0);
    
    this.renderer.setSize(width, height);
    this.container.appendChild(this.gl.canvas);

    // Style canvas
    Object.assign(this.gl.canvas.style, {
      position: 'absolute',
      inset: '0',
      width: '100%',
      height: '100%',
      display: 'block'
    });

    // Create camera
    this.camera = new Camera(this.gl, { fov: 75 });
    this.camera.position.z = 5;

    // Create scene
    this.scene = new Transform();

    // Create stars
    this.createStars();

    // Setup event listeners
    this.setupEventListeners();

    // Setup resize observer
    this.resizeObserver = new ResizeObserver(() => this.resize());
    this.resizeObserver.observe(this.container);

    // Start animation
    this.startAnimation();
  }

  createStars() {
    const numStars = Math.floor(2000 * this.options.density);
    const positions = new Float32Array(numStars * 3);
    const colors = new Float32Array(numStars * 3);
    const sizes = new Float32Array(numStars);
    const velocities = new Float32Array(numStars * 3);
    const phases = new Float32Array(numStars);

    // Color based on hue shift
    const baseColor = new Color();
    const hue = this.options.hueShift / 360;
    
    for (let i = 0; i < numStars; i++) {
      const i3 = i * 3;
      
      // Random spherical distribution
      const radius = 5 + Math.random() * 15;
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      
      positions[i3] = radius * Math.sin(phi) * Math.cos(theta);
      positions[i3 + 1] = radius * Math.sin(phi) * Math.sin(theta);
      positions[i3 + 2] = radius * Math.cos(phi);

      // Velocities for movement
      velocities[i3] = (Math.random() - 0.5) * 0.002 * this.options.starSpeed;
      velocities[i3 + 1] = (Math.random() - 0.5) * 0.002 * this.options.starSpeed;
      velocities[i3 + 2] = (Math.random() - 0.5) * 0.002 * this.options.starSpeed;

      // Random phase for twinkling
      phases[i] = Math.random() * Math.PI * 2;

      // Star colors with hue shift
      const colorVariation = Math.random() * 0.2;
      const h = (hue + colorVariation) % 1;
      const s = this.options.saturation;
      const l = 0.8 + Math.random() * 0.2;

      // Convert HSL to RGB
      const rgb = this.hslToRgb(h, s, l);
      colors[i3] = rgb[0];
      colors[i3 + 1] = rgb[1];
      colors[i3 + 2] = rgb[2];

      // Star sizes
      sizes[i] = 2 + Math.random() * 4;
    }

    // Create geometry
    this.geometry = new Geometry(this.gl, {
      position: { size: 3, data: positions },
      color: { size: 3, data: colors },
      size: { size: 1, data: sizes },
      velocity: { size: 3, data: velocities },
      phase: { size: 1, data: phases }
    });

    // Create shader program
    const vertex = `
      attribute vec3 position;
      attribute vec3 color;
      attribute float size;
      attribute float phase;
      
      uniform mat4 modelViewMatrix;
      uniform mat4 projectionMatrix;
      uniform float uTime;
      uniform float uTwinkle;
      uniform float uGlow;
      uniform vec2 uMouse;
      uniform float uRepulsion;
      uniform bool uMouseRepulsion;
      
      varying vec3 vColor;
      varying float vAlpha;
      
      void main() {
        vec3 pos = position;
        
        // Mouse repulsion effect
        if (uMouseRepulsion && uRepulsion > 0.0) {
          vec2 mousePos = uMouse;
          float dist = distance(pos.xy, mousePos);
          float repulsionRadius = 3.0;
          
          if (dist < repulsionRadius) {
            float strength = (1.0 - dist / repulsionRadius) * uRepulsion;
            vec2 dir = normalize(pos.xy - mousePos);
            pos.xy += dir * strength * 0.5;
          }
        }
        
        vec4 mvPosition = modelViewMatrix * vec4(pos, 1.0);
        gl_Position = projectionMatrix * mvPosition;
        
        // Twinkling effect
        float twinkle = 1.0 + sin(uTime * 2.0 + phase) * uTwinkle;
        
        // Size based on distance
        float distanceScale = 300.0 / length(mvPosition.xyz);
        gl_PointSize = size * distanceScale * twinkle * (1.0 + uGlow);
        
        vColor = color;
        vAlpha = twinkle * 0.8;
      }
    `;

    const fragment = `
      precision highp float;
      
      varying vec3 vColor;
      varying float vAlpha;
      
      void main() {
        // Circular star shape with glow
        vec2 center = gl_PointCoord - 0.5;
        float dist = length(center);
        
        // Soft circular gradient
        float alpha = 1.0 - smoothstep(0.0, 0.5, dist);
        alpha = pow(alpha, 2.0) * vAlpha;
        
        // Add bright center
        float core = 1.0 - smoothstep(0.0, 0.1, dist);
        
        vec3 color = vColor * (0.7 + core * 0.3);
        gl_FragColor = vec4(color, alpha);
      }
    `;

    this.program = new Program(this.gl, {
      vertex,
      fragment,
      uniforms: {
        uTime: { value: 0 },
        uTwinkle: { value: this.options.twinkleIntensity },
        uGlow: { value: this.options.glowIntensity },
        uMouse: { value: [0, 0] },
        uRepulsion: { value: this.options.repulsionStrength },
        uMouseRepulsion: { value: this.options.mouseRepulsion }
      },
      transparent: true,
      depthTest: false,
      depthWrite: false
    });

    // Create mesh
    this.mesh = new Mesh(this.gl, { 
      mode: this.gl.POINTS, 
      geometry: this.geometry, 
      program: this.program 
    });
    this.mesh.setParent(this.scene);
  }

  hslToRgb(h, s, l) {
    let r, g, b;

    if (s === 0) {
      r = g = b = l;
    } else {
      const hue2rgb = (p, q, t) => {
        if (t < 0) t += 1;
        if (t > 1) t -= 1;
        if (t < 1 / 6) return p + (q - p) * 6 * t;
        if (t < 1 / 2) return q;
        if (t < 2 / 3) return p + (q - p) * (2 / 3 - t) * 6;
        return p;
      };

      const q = l < 0.5 ? l * (1 + s) : l + s - l * s;
      const p = 2 * l - q;
      r = hue2rgb(p, q, h + 1 / 3);
      g = hue2rgb(p, q, h);
      b = hue2rgb(p, q, h - 1 / 3);
    }

    return [r, g, b];
  }

  setupEventListeners() {
    if (!this.options.mouseInteraction) return;

    this.onMouseMove = (e) => {
      const rect = this.container.getBoundingClientRect();
      // Normalize to -1 to 1 range and scale to scene space
      this.mouse.x = ((e.clientX - rect.left) / rect.width) * 10 - 5;
      this.mouse.y = -(((e.clientY - rect.top) / rect.height) * 10 - 5);
    };

    this.container.addEventListener('mousemove', this.onMouseMove);
  }

  resize() {
    const width = this.container.clientWidth || 1;
    const height = this.container.clientHeight || 1;
    
    this.renderer.setSize(width, height);
    this.camera.perspective({ 
      aspect: width / height,
      fov: 75
    });
  }

  render(now) {
    this.time += 0.016 * this.options.speed; // Approximately 60fps baseline
    
    // Update uniforms
    this.program.uniforms.uTime.value = this.time;
    this.program.uniforms.uMouse.value = [this.mouse.x, this.mouse.y];

    // Rotate scene
    this.scene.rotation.y = this.time * this.options.rotationSpeed * 0.05;
    this.scene.rotation.x = Math.sin(this.time * 0.1) * 0.1;

    // Update star positions
    const positions = this.geometry.attributes.position.data;
    const velocities = this.geometry.attributes.velocity.data;
    
    for (let i = 0; i < positions.length; i += 3) {
      positions[i] += velocities[i];
      positions[i + 1] += velocities[i + 1];
      positions[i + 2] += velocities[i + 2];

      // Wrap around
      const radius = Math.sqrt(
        positions[i] ** 2 + 
        positions[i + 1] ** 2 + 
        positions[i + 2] ** 2
      );
      
      if (radius > 20) {
        // Reset to inner sphere
        const scale = 5 / radius;
        positions[i] *= scale;
        positions[i + 1] *= scale;
        positions[i + 2] *= scale;
      }
    }
    
    this.geometry.attributes.position.needsUpdate = true;

    // Render
    this.renderer.render({ 
      scene: this.scene, 
      camera: this.camera 
    });

    this.raf = requestAnimationFrame((t) => this.render(t));
  }

  startAnimation() {
    if (this.raf) return;
    this.raf = requestAnimationFrame((t) => this.render(t));
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

    if (this.onMouseMove) {
      this.container.removeEventListener('mousemove', this.onMouseMove);
    }

    if (this.geometry) {
      this.geometry.remove();
    }

    if (this.program) {
      this.gl.deleteProgram(this.program.program);
    }

    if (this.gl.canvas.parentElement) {
      this.container.removeChild(this.gl.canvas);
    }
  }
}

export default Galaxy;
