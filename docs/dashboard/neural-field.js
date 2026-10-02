const canvas = document.createElement("canvas");
canvas.id = "neural-field";
canvas.setAttribute("aria-hidden", "true");
document.body.prepend(canvas);

const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const automatedBrowser = navigator.webdriver || /HeadlessChrome/i.test(navigator.userAgent);
const staticRendering = reducedMotion || automatedBrowser;
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
  uniform float u_activity;
  out vec4 fragColor;

  float hash21(vec2 p) {
    p = fract(p * vec2(123.34, 345.45));
    p += dot(p, p + 34.345);
    return fract(p.x * p.y);
  }

  float line(float value, float width) {
    return 1.0 - smoothstep(0.0, width, abs(value));
  }

  float sparkleLayer(vec2 uv, float scale, float speed) {
    vec2 p = uv * scale;
    vec2 id = floor(p);
    vec2 cell = fract(p) - 0.5;
    float rnd = hash21(id);
    vec2 offset = vec2(hash21(id + 7.1), hash21(id + 19.7)) - 0.5;
    float dist = length(cell - offset * 0.58);
    float sparkle = smoothstep(0.055, 0.0, dist);
    float gate = step(0.84, rnd);
    float pulse = 0.35 + 0.65 * sin(u_time * speed + rnd * 24.0) * 0.5 + 0.5;
    return sparkle * gate * pulse;
  }

  void main() {
    vec2 frag = gl_FragCoord.xy;
    vec2 uv = (frag * 2.0 - u_resolution.xy) / min(u_resolution.x, u_resolution.y);
    vec2 pointer = (u_pointer * 2.0 - 1.0);
    pointer.x *= u_resolution.x / max(u_resolution.y, 1.0);

    float flowTime = u_time * (0.025 + 0.975 * clamp(u_activity, 0.0, 1.0));
    vec3 col = vec3(0.965, 0.988, 1.0);

    float atmosphere = smoothstep(1.7, 0.08, length(uv * vec2(0.72, 0.9)));
    col += vec3(0.018, 0.055, 0.065) * atmosphere;

    float cyanCloud = exp(-1.8 * length(uv - vec2(-0.72, 0.72)));
    float violetCloud = exp(-2.2 * length(uv - vec2(0.86, 0.38)));
    col += cyanCloud * vec3(0.02, 0.095, 0.12);
    col += violetCloud * vec3(0.045, 0.035, 0.085);

    float sparks = sparkleLayer(uv + vec2(flowTime * 0.005, 0.0), 18.0, 0.9 + u_activity)
                 + sparkleLayer(uv * 1.18 - vec2(0.0, flowTime * 0.003), 29.0, 1.2 + u_activity) * 0.55;
    col -= sparks * vec3(0.03, 0.085, 0.09);
    col += sparks * vec3(0.0, 0.055, 0.075);

    vec2 gridUv = uv;
    gridUv.y += 0.18;
    float depth = max(0.18, gridUv.y + 1.35);
    vec2 projected = vec2(gridUv.x / depth, 1.0 / depth + flowTime * 0.028);
    float gridX = line(fract(projected.x * 7.0) - 0.5, 0.03);
    float gridY = line(fract(projected.y * 2.1) - 0.5, 0.021);
    float horizon = smoothstep(-0.76, 0.58, gridUv.y) * (1.0 - smoothstep(0.48, 1.28, gridUv.y));
    col -= (gridX + gridY) * horizon * vec3(0.025, 0.075, 0.09);

    float beam = line(uv.y - 0.17 * sin(uv.x * 2.2 + flowTime * 0.42), 0.010);
    beam *= smoothstep(1.55, 0.0, abs(uv.x));
    col -= beam * vec3(0.018, 0.075, 0.09);

    float pointerGlow = exp(-3.3 * length(uv - pointer));
    col += pointerGlow * vec3(0.018, 0.065, 0.075);

    float ringDistance = abs(length(uv - pointer * 0.16) - (0.38 + 0.026 * sin(flowTime * 0.68)));
    float ring = smoothstep(0.016, 0.0, ringDistance);
    col -= ring * vec3(0.018, 0.072, 0.085);

    float scan = 0.004 * sin(frag.y * 0.82 + flowTime * 2.6);
    col -= scan * vec3(0.25, 0.48, 0.55);

    col = clamp(col, 0.0, 1.0);
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
    const activityLocation = gl.getUniformLocation(program, "u_activity");
    const pointer = { x: 0.5, y: 0.42 };
    let animationFrame = 0;
    let visible = !document.hidden;

    function resize() {
      const pixelRatio = automatedBrowser
        ? 0.75
        : Math.min(window.devicePixelRatio || 1, compactMode ? 1.2 : 1.55);
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
      gl.uniform1f(timeLocation, staticRendering ? 12.0 : now * 0.001);
      const activity = Number.parseFloat(document.documentElement.dataset.factoryActivity || "0");
      gl.uniform1f(activityLocation, Number.isFinite(activity) ? Math.min(1, Math.max(0, activity)) : 0);
      gl.drawArrays(gl.TRIANGLES, 0, 3);
      if (!staticRendering && visible) animationFrame = requestAnimationFrame(render);
    }

    function restart() {
      cancelAnimationFrame(animationFrame);
      if (visible) render(performance.now());
    }

    if (!staticRendering) {
      window.addEventListener("pointermove", (event) => {
        pointer.x += (event.clientX / Math.max(window.innerWidth, 1) - pointer.x) * 0.14;
        pointer.y += (1.0 - event.clientY / Math.max(window.innerHeight, 1) - pointer.y) * 0.14;
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
