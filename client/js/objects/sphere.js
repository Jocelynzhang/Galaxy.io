// A rotating, lit globe drawn by a fragment shader from an equirectangular surface map.
import { Geometry, GlProgram, Mesh, Shader } from 'https://cdn.jsdelivr.net/npm/pixi.js@8.21.0/dist/pixi.min.mjs';

const vertex = `
in vec2 aPosition;
in vec2 aUV;
out vec2 vUV;
uniform mat3 uProjectionMatrix;
uniform mat3 uWorldTransformMatrix;
uniform mat3 uTransformMatrix;
void main() {
  mat3 mvp = uProjectionMatrix * uWorldTransformMatrix * uTransformMatrix;
  gl_Position = vec4((mvp * vec3(aPosition, 1.0)).xy, 0.0, 1.0);
  vUV = aUV;
}`;

const fragment = `precision highp float;
in vec2 vUV;
out vec4 finalColor;
uniform sampler2D uTexture;
uniform float uRot;       // longitude offset (radians): spinning
uniform float uTilt;      // axial tilt toward the viewer (radians)
uniform vec3 uTint;       // multiplies the surface colour (stars use grey maps + tint)
uniform vec4 uAtmo;       // rim glow colour + strength
uniform float uEmissive;  // 0 = lit by a distant light, 1 = glows by itself (stars)
uniform float uAA;        // edge softness, ~1.5 screen pixels in radius units
const float PI = 3.14159265;
void main() {
  vec2 p = vUV;
  float d = length(p);
  float alpha = 1.0 - smoothstep(1.0 - uAA, 1.0, d);
  if (alpha <= 0.0) discard;
  float z = sqrt(max(0.0, 1.0 - d * d));
  vec3 n = vec3(p.x, -p.y, z);
  // tilt the globe a little so the poles show
  float ct = cos(uTilt), st = sin(uTilt);
  vec3 m = vec3(n.x, n.y * ct - n.z * st, n.y * st + n.z * ct);
  float lon = atan(m.x, m.z) + uRot;
  float lat = asin(clamp(m.y, -1.0, 1.0));
  vec2 uv = vec2(lon / (2.0 * PI), 0.5 - lat / PI);
  vec4 s = texture(uTexture, uv);
  vec3 col = s.rgb * uTint;
  if (uEmissive > 0.5) {
    col *= 0.72 + 0.5 * pow(z, 0.4);                 // bright centre, darker limb
  } else {
    vec3 light = normalize(vec3(-0.55, 0.45, 0.7));
    col *= 0.16 + 0.9 * max(dot(n, light), 0.0);
  }
  col += uAtmo.rgb * pow(1.0 - z, 2.5) * uAtmo.a;   // atmosphere / corona rim
  float a = alpha * s.a;
  finalColor = vec4(col * a, a);
}`;

let program = null;
let quad = null;

function shared() {
  if (!program) {
    program = new GlProgram({ vertex, fragment, name: 'sphere' });
    quad = new Geometry({
      attributes: {
        aPosition: [-1, -1, 1, -1, 1, 1, -1, 1],
        aUV: [-1, -1, 1, -1, 1, 1, -1, 1],
      },
      indexBuffer: [0, 1, 2, 0, 2, 3],
    });
  }
  return { program, quad };
}

// Returns a Mesh of radius 1 (scale it to the object's radius) with a `.sphere` uniform block.
export function makeSphere(texture, { tint = [1, 1, 1], atmo = [0, 0, 0, 0], emissive = 0, tilt = 0.25 } = {}) {
  const { program: glProgram, quad: geometry } = shared();
  const shader = new Shader({
    glProgram,
    resources: {
      uTexture: texture.source,
      sphere: {
        uRot: { value: 0, type: 'f32' },
        uTilt: { value: tilt, type: 'f32' },
        uTint: { value: new Float32Array(tint), type: 'vec3<f32>' },
        uAtmo: { value: new Float32Array(atmo), type: 'vec4<f32>' },
        uEmissive: { value: emissive, type: 'f32' },
        uAA: { value: 0.02, type: 'f32' },
      },
    },
  });
  const mesh = new Mesh({ geometry, shader });
  mesh.sphere = shader.resources.sphere.uniforms;
  return mesh;
}
