export const DEFAULT_VIEW = Object.freeze({ yaw: 0, pitch: 0, fov: 75 });
export const MIN_FOV = 25;
export const MAX_FOV = 110;
export const MAX_PITCH = Math.PI / 2 - 0.01;
export const MIN_PITCH = -MAX_PITCH;

const VERTEX_SHADER = `#version 300 es
in vec2 a_position;

void main() {
    gl_Position = vec4(a_position, 0.0, 1.0);
}
`;

const FRAGMENT_SHADER = `#version 300 es
precision highp float;

uniform sampler2D u_panorama;
uniform vec2 u_resolution;
uniform float u_yaw;
uniform float u_pitch;
uniform float u_fov;

out vec4 output_color;

mat3 rotate_x(float angle) {
    float c = cos(angle);
    float s = sin(angle);
    return mat3(
        1.0, 0.0, 0.0,
        0.0, c, s,
        0.0, -s, c
    );
}

mat3 rotate_y(float angle) {
    float c = cos(angle);
    float s = sin(angle);
    return mat3(
        c, 0.0, -s,
        0.0, 1.0, 0.0,
        s, 0.0, c
    );
}

void main() {
    vec2 point = (gl_FragCoord.xy / u_resolution) * 2.0 - 1.0;
    point.x *= u_resolution.x / u_resolution.y;

    float tangent = tan(radians(u_fov) * 0.5);
    vec3 ray = normalize(vec3(point.x * tangent, point.y * tangent, -1.0));
    ray = rotate_y(u_yaw) * rotate_x(u_pitch) * ray;

    float longitude = atan(ray.x, -ray.z);
    float latitude = asin(clamp(ray.y, -1.0, 1.0));
    vec2 uv = vec2(
        fract(longitude / 6.28318530718 + 0.5),
        0.5 - latitude / 3.14159265359
    );

    output_color = texture(u_panorama, uv);
}
`;

export function clamp(value, min, max) {
    return Math.min(max, Math.max(min, value));
}

export function degrees(radians) {
    return radians * 180 / Math.PI;
}

export function normalizeYaw(yaw) {
    const circle = Math.PI * 2;
    return ((yaw + Math.PI) % circle + circle) % circle - Math.PI;
}

function compileShader(gl, type, source) {
    const shader = gl.createShader(type);
    gl.shaderSource(shader, source);
    gl.compileShader(shader);
    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
        const message = gl.getShaderInfoLog(shader) || "Unknown shader compilation error";
        gl.deleteShader(shader);
        throw new Error(message);
    }
    return shader;
}

function createProgram(gl) {
    const vertex = compileShader(gl, gl.VERTEX_SHADER, VERTEX_SHADER);
    const fragment = compileShader(gl, gl.FRAGMENT_SHADER, FRAGMENT_SHADER);
    const program = gl.createProgram();
    gl.attachShader(program, vertex);
    gl.attachShader(program, fragment);
    gl.linkProgram(program);
    gl.deleteShader(vertex);
    gl.deleteShader(fragment);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
        const message = gl.getProgramInfoLog(program) || "Unknown shader link error";
        gl.deleteProgram(program);
        throw new Error(message);
    }
    return program;
}

export class PanoramaRenderer {
    constructor(canvas) {
        this.canvas = canvas;
        this.gl = canvas.getContext("webgl2", {
            alpha: false,
            antialias: true,
            preserveDrawingBuffer: true,
        });
        if (!this.gl) {
            throw new Error("WebGL 2 is unavailable in this browser.");
        }

        const gl = this.gl;
        this.program = createProgram(gl);
        this.position = gl.getAttribLocation(this.program, "a_position");
        this.resolution = gl.getUniformLocation(this.program, "u_resolution");
        this.yaw = gl.getUniformLocation(this.program, "u_yaw");
        this.pitch = gl.getUniformLocation(this.program, "u_pitch");
        this.fov = gl.getUniformLocation(this.program, "u_fov");

        this.buffer = gl.createBuffer();
        gl.bindBuffer(gl.ARRAY_BUFFER, this.buffer);
        gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([
            -1, -1, 1, -1, -1, 1,
            -1, 1, 1, -1, 1, 1,
        ]), gl.STATIC_DRAW);

        this.texture = gl.createTexture();
        gl.bindTexture(gl.TEXTURE_2D, this.texture);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.REPEAT);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
        gl.texImage2D(
            gl.TEXTURE_2D,
            0,
            gl.RGBA,
            1,
            1,
            0,
            gl.RGBA,
            gl.UNSIGNED_BYTE,
            new Uint8Array([24, 24, 28, 255]),
        );
        this.hasImage = false;
    }

    setImage(image) {
        const gl = this.gl;
        gl.bindTexture(gl.TEXTURE_2D, this.texture);
        gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, false);
        gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, false);
        gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, image);
        this.hasImage = true;
    }

    resize() {
        const dpr = Math.min(globalThis.devicePixelRatio || 1, 2);
        const width = Math.max(1, Math.round(this.canvas.clientWidth * dpr));
        const height = Math.max(1, Math.round(this.canvas.clientHeight * dpr));
        if (this.canvas.width !== width || this.canvas.height !== height) {
            this.canvas.width = width;
            this.canvas.height = height;
        }
    }

    render(view) {
        this.resize();
        const gl = this.gl;
        gl.viewport(0, 0, this.canvas.width, this.canvas.height);
        gl.clearColor(0.055, 0.055, 0.07, 1);
        gl.clear(gl.COLOR_BUFFER_BIT);
        if (!this.hasImage) {
            return;
        }

        gl.useProgram(this.program);
        gl.bindBuffer(gl.ARRAY_BUFFER, this.buffer);
        gl.enableVertexAttribArray(this.position);
        gl.vertexAttribPointer(this.position, 2, gl.FLOAT, false, 0, 0);
        gl.activeTexture(gl.TEXTURE0);
        gl.bindTexture(gl.TEXTURE_2D, this.texture);
        gl.uniform2f(this.resolution, this.canvas.width, this.canvas.height);
        gl.uniform1f(this.yaw, view.yaw);
        gl.uniform1f(this.pitch, view.pitch);
        gl.uniform1f(this.fov, view.fov);
        gl.drawArrays(gl.TRIANGLES, 0, 6);
    }

    destroy() {
        const gl = this.gl;
        gl.deleteTexture(this.texture);
        gl.deleteBuffer(this.buffer);
        gl.deleteProgram(this.program);
    }
}
