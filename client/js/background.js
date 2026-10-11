// Full-screen background: faint starfield + light grid, bent by gravitational lensing.
// Each massive object acts as a point lens: a ray seen at screen position θ comes from source
// position β = θ - θE² (θ - L) / |θ - L|² (the lens equation), so lines bend around heavy
// objects and close into an Einstein ring around black holes.
import { Geometry, GlProgram, Mesh, Shader } from 'https://cdn.jsdelivr.net/npm/pixi.js@8.21.0/dist/pixi.min.mjs';

export const MAX_LENSES = 16;
const GRID = 100;   // world units between grid lines

const vertex = `
in vec2 aPosition;
out vec2 vUV;
uniform mat3 uProjectionMatrix;
uniform mat3 uWorldTransformMatrix;
uniform mat3 uTransformMatrix;
void main() {
  mat3 mvp = uProjectionMatrix * uWorldTransformMatrix * uTransformMatrix;
  gl_Position = vec4((mvp * vec3(aPosition, 1.0)).xy, 0.0, 1.0);
  vUV = aPosition;
}`;

// Written to compile on WebGL1 too: no fwidth(); derivatives are taken by evaluating the
// lens map at neighbouring pixels instead.
const fragment = `precision highp float;
in vec2 vUV;
out vec4 finalColor;
uniform vec2 uScreen;     // CSS pixels
uniform vec2 uCam;        // world position at the screen centre
uniform float uZoom;      // screen px per world unit
uniform float uTime;
uniform vec4 uLenses[${MAX_LENSES}];   // xy: screen px, z: Einstein radius px
uniform int uCount;

float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }

float stars(vec2 sky, float cellSize, float density) {
  vec2 c = floor(sky / cellSize);
  vec2 f = fract(sky / cellSize);
  float h = hash(c);
  vec2 sp = vec2(hash(c + 1.37), hash(c + 7.13)) * 0.8 + 0.1;
  float d = length(f - sp) * cellSize;
  float tw = 0.75 + 0.25 * sin(uTime * (1.0 + 2.0 * h) + h * 40.0);
  return step(1.0 - density, h) * smoothstep(1.4, 0.0, d) * (0.35 + 0.65 * hash(c + 3.3)) * tw;
}

vec2 lensMap(vec2 p) {
  vec2 beta = p;
  for (int i = 0; i < ${MAX_LENSES}; i++) {
    if (i >= uCount) break;
    vec4 L = uLenses[i];
    vec2 d = p - L.xy;
    float soft = 0.08 * L.z;
    beta -= d * (L.z * L.z) / (dot(d, d) + soft * soft);
  }
  return beta;
}

vec2 gridCoord(vec2 beta) {
  return (uCam + (beta - 0.5 * uScreen) / uZoom) / ${GRID.toFixed(1)};
}

void main() {
  vec2 p = vUV * uScreen;
  vec2 beta = lensMap(p);

  // grid at the lensed world position; fw = how much grid space one screen pixel covers
  vec2 g = gridCoord(beta);
  vec2 gx = gridCoord(lensMap(p + vec2(1.0, 0.0))) - g;
  vec2 gy = gridCoord(lensMap(p + vec2(0.0, 1.0))) - g;
  vec2 fw = max(abs(gx) + abs(gy), vec2(1e-5));
  vec2 dist = abs(fract(g - 0.5) - 0.5) / fw;
  float line = 1.0 - min(min(dist.x, dist.y), 1.0);
  // where lensing squeezes many lines into one pixel, fade them instead of aliasing
  line *= 1.0 - smoothstep(0.18, 0.5, max(fw.x, fw.y));

  // two parallax star layers, also lensed
  vec2 sky = beta - 0.5 * uScreen;
  float s = stars(sky + uCam * uZoom * 0.12, 46.0, 0.16) + 0.6 * stars(sky * 1.7 + uCam * uZoom * 0.05 + 300.0, 38.0, 0.2);

  vec3 col = vec3(0.043, 0.063, 0.149);
  col += vec3(0.62, 0.72, 1.0) * line * 0.2;
  col += vec3(0.9, 0.94, 1.0) * s * 0.75;
  finalColor = vec4(col, 1.0);
}`;

export class LensBackground {
  constructor() {
    const geometry = new Geometry({
      attributes: { aPosition: [0, 0, 1, 0, 1, 1, 0, 1] },
      indexBuffer: [0, 1, 2, 0, 2, 3],
    });
    this.lensData = new Float32Array(MAX_LENSES * 4);
    const shader = new Shader({
      glProgram: new GlProgram({ vertex, fragment, name: 'lens-background' }),
      resources: {
        bg: {
          uScreen: { value: new Float32Array([1, 1]), type: 'vec2<f32>' },
          uCam: { value: new Float32Array([0, 0]), type: 'vec2<f32>' },
          uZoom: { value: 1, type: 'f32' },
          uTime: { value: 0, type: 'f32' },
          uLenses: { value: this.lensData, type: 'vec4<f32>', size: MAX_LENSES },
          uCount: { value: 0, type: 'i32' },
        },
      },
    });
    this.group = shader.resources.bg;
    this.u = this.group.uniforms;
    this.view = new Mesh({ geometry, shader });
  }

  // lenses: [{x, y, e}] in screen px (e = Einstein radius in px), any order
  update(w, h, camX, camY, zoom, time, lenses) {
    this.view.scale.set(w, h);
    this.u.uScreen[0] = w;
    this.u.uScreen[1] = h;
    this.u.uCam[0] = camX;
    this.u.uCam[1] = camY;
    this.u.uZoom = zoom;
    this.u.uTime = time;
    const top = lenses.filter((l) => l.e > 0.5).sort((a, b) => b.e - a.e).slice(0, MAX_LENSES);
    top.forEach((l, i) => this.lensData.set([l.x, l.y, l.e, 0], i * 4));
    this.u.uCount = top.length;
    this.group.update();
  }
}
