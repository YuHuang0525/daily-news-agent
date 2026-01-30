/**
 * Main entry point for the application
 * Imports and initializes the Hyperspeed background
 */

import { Hyperspeed } from './hyperspeed.js';

// Initialize Hyperspeed background when DOM is ready
function initHyperspeed() {
  const container = document.getElementById('grid-background');
  if (container) {
    // Create Hyperspeed instance with custom options
    window.hyperspeedBackground = new Hyperspeed(container, {
      distortion: 'turbulentDistortion',
      length: 400,
      roadWidth: 10,
      islandWidth: 2,
      lanesPerRoad: 3,
      fov: 90,
      fovSpeedUp: 150,
      speedUp: 2,
      carLightsFade: 0.4,
      totalSideLightSticks: 20,
      lightPairsPerRoadWay: 30, // Reduced from 40 for fewer cars
      shoulderLinesWidthPercentage: 0.05,
      brokenLinesWidthPercentage: 0.1,
      brokenLinesLengthPercentage: 0.5,
      lightStickWidth: [0.12, 0.5],
      lightStickHeight: [1.3, 1.7],
      movingAwaySpeed: [8, 12], // Even slower for calm effect
      movingCloserSpeed: [-12, -18], // Even slower for calm effect
      carLightsLength: [12, 80],
      carLightsRadius: [0.05, 0.14],
      carWidthPercentage: [0.3, 0.5],
      carShiftX: [-0.8, 0.8],
      carFloorSeparation: [0, 5],
      colors: {
        roadColor: 0xd0d0d0,
        islandColor: 0xc0c0c0,
        background: 0xe8e8e8,
        shoulderLines: 0xa0a0a0,
        brokenLines: 0xa0a0a0,
        leftCars: [0x2563eb, 0x4f46e5, 0x3b82f6],
        rightCars: [0x059669, 0x0891b2, 0x06b6d4],
        sticks: 0x2563eb
      }
    });
    
    console.log('Hyperspeed background initialized');
  }
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initHyperspeed);
} else {
  initHyperspeed();
}

// Export for external use
export { Hyperspeed };
