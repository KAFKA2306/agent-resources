const canvas = document.createElement("canvas");
canvas.id = "neural-field";
canvas.setAttribute("aria-hidden", "true");
document.body.prepend(canvas);

const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const compactMode = window.matchMedia("(max-width: 760px)").matches;
const gl = canvas.getContext("webgl2", {
  alpha: true,
  antialias: false,
  depth: false,
  stencil: false,
  premultipliedAlpha: false,
  powerPreference: "high-performance",
});

if (!gl) {
  canvas.hidden = true;
  document.documentElement.dataset.webgl = "unavailable";
} else {
  document.documentElement.dataset.webgl = "active";

  const vertexSource = `#version 300 es
  precision highp float;
  void main() {
    vec2 positions[3] = vec2[](
      vec2(-1.0, -1.0),
      vec2( 3.0, -1.0),
      vec2(-1.0,  3.0)
    );
    gl_Position = vec4(positions[gl_VertexID], 0.0, 1.0);
  }`;

  const fragmentSource = `#version 300 es
  precision highp float;

  uniform vec2 u_resolution;
  uniform vec2 u_pointer;
  uniform float u_time;
  out vec4 fragColor;

  float hash21(vec2 p) {
    p = fract(p * vec2(123.34, 345.45));
    p += dot(p, p + 34.345);
    return fract(p.x * p.y);
  }

  float line(float value, float width) {
    return 1.0 - smoothstep(0.0, width, abs(value));
  }

  float starLayer(vec2 uv, float scale, float speed) {
    vec2 p = uv * scale;
    vec2 id = floor(p);
    vec2 cell = fract(p) - 0.5;
    float rnd = hash21(id);
    vec2 offset = vec2(hash21(id + 7.1), hash21(id + 19.7)) - 0.5;
    float dist = length(cell - offset * 0.62);
    float sparkle = smoothstep(0.06, 0.0, dist);
    float gate = step(0.82, rnd);
    float pulse = 0.45 + 0.55 * sin(u_time * speed + rnd * 24.0);
    return sparkle * gate * pulse;
  }

  void main() {
    vec2 frag = gl_FragCoord.xy;
    vec2 uv = (frag * 2.0 - u_resolution.xy) / min(u_resolution.x, u_resolution.y);
    vec2 pointer = (u_pointer * 2.0 - 1.0);
    pointer.x *= u_resolution.x / max(u_resolution.y, 1.0);

    vec3 col = vec3(0.006, 0.014, 0.035);

    float vignette = smoothstep(1.7, 0.1, length(uv * vec2(0.72, 0.9)));
    col += vec3(0.005, 0.035, 0.075) * vignette;

    float stars = starLayer(uv + vec2(u_time * 0.006, 0.0), 18.0, 1.7)
                + starLayer(uv * 1.21 - vec2(0.0, u_time * 0.004), 28.0, 2.3) * 0.55;
    col += stars * vec3(0.12, 0.62, 1.0);

    vec2 gridUv = uv;
    gridUv.y += 0.22;
    float depth = max(0.16, gridUv.y + 1.32);
    vec2 projected = vec2(gridUv.x / depth, 1.0 / depth + u_time * 0.035);
    float gridX = line(fract(projected.x * 7.0) - 0.5, 0.035);
    float gridY = line(fract(projected.y * 2.2) - 0.5, 0.025);
    float horizon = smoothstep(-0.72, 0.62, gridUv.y) * (1.0 - smoothstep(0.45, 1.3, gridUv.y));
    col += (gridX + gridY) * horizon * vec3(0.0, 0.19, 0.34);

    float beam = line(uv.y - 0.18 * sin(uv.x * 2.2 + u_time * 0.45), 0.012);
    beam *= smoothstep(1.55, 0.0, abs(uv.x));
    col += beam * vec3(0.04, 0.46, 0.72) * 0.22;

    float pointerGlow = exp(-3.2 * length(uv - pointer));
    col += pointerGlow * vec3(0.05, 0.24, 0.42);

    float ringDistance = abs(length(uv - pointer * 0.18) - (0.38 + 0.03 * sin(u_time * 0.7)));
    float ring = smoothstep(0.018, 0.0, ringDistance);
    col += ring * vec3(0.12, 0.42, 0.68) * 0.2;

    float scan = 0.018 * sin(frag.y * 0.95 + u_time * 3.0);
    col += scan * vec3(0.02, 0.08, 0.11);

    col *= 0.92 + 0.08 * vignette;
    fragColor = vec4(col, 1.0);
  }`;

  function compileShader(type, source) {
    const shader = gl.createShader(type);
    gl.shaderSource(shader, source);
    gl.compileShader(shader);
    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
      const message = gl.getShaderInfoLog(shader) || "unknown shader error";
      gl.deleteShader(shader);
      throw new Error(message);
    }
    return shader;
  }

  try {
    const program = gl.createProgram();
    gl.attachShader(program, compileShader(gl.VERTEX_SHADER, vertexSource));
    gl.attachShader(program, compileShader(gl.FRAGMENT_SHADER, fragmentSource));
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
      throw new Error(gl.getProgramInfoLog(program) || "WebGL program link failed");
    }

    gl.useProgram(program);
    const resolutionLocation = gl.getUniformLocation(program, "u_resolution");
    const pointerLocation = gl.getUniformLocation(program, "u_pointer");
    const timeLocation = gl.getUniformLocation(program, "u_time");
    const pointer = { x: 0.5, y: 0.42 };
    let animationFrame = 0;
    let visible = !document.hidden;

    function resize() {
      const pixelRatio = Math.min(window.devicePixelRatio || 1, compactMode ? 1.2 : 1.55);
      const width = Math.max(1, Math.floor(window.innerWidth * pixelRatio));
      const height = Math.max(1, Math.floor(window.innerHeight * pixelRatio));
      if (canvas.width !== width || canvas.height !== height) {
        canvas.width = width;
        canvas.height = height;
        canvas.style.width = `${window.innerWidth}px`;
        canvas.style.height = `${window.innerHeight}px`;
      }
      gl.viewport(0, 0, canvas.width, canvas.height);
    }

    function render(now = 0) {
      resize();
      gl.useProgram(program);
      gl.uniform2f(resolutionLocation, canvas.width, canvas.height);
      gl.uniform2f(pointerLocation, pointer.x, pointer.y);
      gl.uniform1f(timeLocation, reducedMotion ? 12.0 : now * 0.001);
      gl.drawArrays(gl.TRIANGLES, 0, 3);
      if (!reducedMotion && visible) animationFrame = requestAnimationFrame(render);
    }

    function restart() {
      cancelAnimationFrame(animationFrame);
      if (visible) render(performance.now());
    }

    if (!reducedMotion) {
      window.addEventListener("pointermove", (event) => {
        pointer.x += (event.clientX / Math.max(window.innerWidth, 1) - pointer.x) * 0.16;
        pointer.y += (1.0 - event.clientY / Math.max(window.innerHeight, 1) - pointer.y) * 0.16;
      }, { passive: true });
    }

    window.addEventListener("resize", restart, { passive: true });
    document.addEventListener("visibilitychange", () => {
      visible = !document.hidden;
      if (visible) restart();
      else cancelAnimationFrame(animationFrame);
    });

    canvas.addEventListener("webglcontextlost", (event) => {
      event.preventDefault();
      document.documentElement.dataset.webgl = "lost";
      cancelAnimationFrame(animationFrame);
    });

    render();
  } catch (error) {
    canvas.hidden = true;
    document.documentElement.dataset.webgl = "failed";
    console.warn("Decorative WebGL layer disabled", error);
  }
}
