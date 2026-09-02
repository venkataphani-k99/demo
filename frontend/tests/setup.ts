import '@testing-library/jest-dom';

// Mock WebGL and ResizeObserver for Three.js in test environment
global.ResizeObserver = class {
  observe() {}
  unobserve() {}
  disconnect() {}
};

HTMLCanvasElement.prototype.getContext = (() => {
  return {
    fillRect: () => {},
    clearRect: () => {},
    getImageData: (x: number, y: number, w: number, h: number) => ({ data: new Array(w * h * 4) }),
    putImageData: () => {},
    createImageData: () => [],
    setTransform: () => {},
    drawImage: () => {},
    save: () => {},
    fillText: () => {},
    restore: () => {},
    beginPath: () => {},
    moveTo: () => {},
    lineTo: () => {},
    closePath: () => {},
    stroke: () => {},
    translate: () => {},
    scale: () => {},
    rotate: () => {},
    arc: () => {},
    fill: () => {},
    measureText: () => ({ width: 0 }),
    transform: () => {},
    rect: () => {},
    clip: () => {},
  } as unknown as RenderingContext;
}) as unknown as typeof HTMLCanvasElement.prototype.getContext;
