import sys
import time
import numpy as np
from PySide6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, 
                             QWidget, QLabel, QTextEdit, QPushButton, 
                             QFrame, QMessageBox, QSplitter)
from PySide6.QtCore import Qt, QTimer, QPointF
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from OpenGL.GL import *
from OpenGL.GL import shaders

# --- SHADERTOY-STYLE BOILERPLATE ---
# This shader implements a 3D Sphere using a Raymarching algorithm
DEFAULT_FRAGMENT_SHADER = """
#version 330 core
out vec4 FragColor;

uniform float iTime;
uniform vec2 iResolution;
uniform vec2 iMouse;

// Signed Distance Function for a Sphere
float sdSphere(vec3 p, float s) {
    return length(p) - s;
}

// The "Scene" - this defines what objects exist in the world
float map(vec3 p) {
    // Move the sphere based on time and mouse
    vec3 center = vec3(sin(iTime)*0.5, cos(iTime)*0.5, 0.0);
    float sphere = sdSphere(p - center, 0.5);
    return sphere;
}

void main() {
    // Normalize coordinates to -1.0 to 1.0
    vec2 uv = (gl_FragCoord.xy * 2.0 - iResolution.xy) / iResolution.y;
    
    // Raymarching setup
    vec3 ro = vec3(0.0, 0.0, -3.0); // Ray Origin (Camera)
    vec3 rd = normalize(vec3(uv, 1.0)); // Ray Direction
    
    float t = 0.0; // Distance traveled
    for(int i=0; i<64; i++) {
        vec3 p = ro + rd * t;
        float d = map(p);
        if(d < 0.001 || t > 10.0) break;
        t += d;
    }
    
    // Shading
    vec3 color = vec3(0.0);
    if(t < 10.0) {
        float diff = dot(normalize(vec3(1,1,-1)), vec3(0,0,1)); // Fake light
        color = vec3(0.2, 0.5, 0.9) * (diff + 0.2);
        color *= 1.0 / (1.0 + t * t * 0.1); // Fog/Depth
    }
    
    // Background gradient
    color += vec3(0.1, 0.1, 0.2) * (1.0 - length(uv)*0.5);
    
    FragColor = vec4(color, 1.0);
}
"""

DEFAULT_VERTEX_SHADER = """
#version 330 core
layout (location = 0) in vec3 aPos;
void main() {
    gl_Position = vec4(aPos, 1.0);
}
"""

class ShaderToyCanvas(QOpenGLWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.time_val = 0.0
        self.mouse_pos = [0.0, 0.0]
        self.shader_program = None
        self.vao = None
        self.vbo = None

    def initializeGL(self):
        glEnable(GL_DEPTH_TEST)
        glClearColor(0, 0, 0, 1)
        
        # Full screen quad (Triangle Strip)
        vertices = np.array([-1, -1, 0, 1, -1, 0, -1, 1, 0, 1, 1, 0], dtype='float32')
        self.vao = glGenVertexArrays(1)
        glBindVertexArray(self.vao)
        self.vbo = glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL_STATIC_DRAW)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 0, None)
        glEnableVertexAttribArray(0)
        self.compile_shaders(DEFAULT_VERTEX_SHADER, DEFAULT_FRAGMENT_SHADER)

    def compile_shaders(self, vert_src, frag_src):
        try:
            vs = shaders.compileShader(vert_src, GL_VERTEX_SHADER)
            fs = shaders.compileShader(frag_src, GL_FRAGMENT_SHADER)
            self.shader_program = shaders.compileProgram(vs, fs)
            return True
        except Exception as e:
            print(f"GLSL Error: {e}")
            return False

    def mouseMoveEvent(self, event):
        # Update mouse uniform (normalized to resolution)
        self.mouse_pos[0] = event.position().x()
        self.mouse_pos[1] = event.position().y()
        self.update()

    def paintGL(self):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        if not self.shader_program: return

        glUseProgram(self.shader_program)
        
        # ShaderToy Standard Uniforms
        self.time_val += 0.016
        glUniform1f(glGetUniformLocation(self.shader_program, "iTime"), self.time_val)
        glUniform2f(glGetUniformLocation(self.shader_program, "iResolution"), 
                    float(self.width()), float(self.height()))
        glUniform2f(glGetUniformLocation(self.shader_program, "iMouse"), 
                    self.mouse_pos[0], self.mouse_pos[1])

        glBindVertexArray(self.vao)
        glDrawArrays(GL_TRIANGLE_STRIP, 0, 4)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Pro Shader Studio")
        self.resize(1280, 720)
        self.setStyleSheet("background-color: #121212; color: #eee;")

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QHBoxLayout(main_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Splitter allows the user to resize the editor vs the canvas
        self.splitter = QSplitter(Qt.Horizontal)

        # --- EDITOR PANEL ---
        editor_frame = QFrame()
        editor_frame.setStyleSheet("background-color: #1e1e1e; border-right: 1px solid #333;")
        editor_layout = QVBoxLayout(editor_frame)
        
        header = QLabel("FRAGMENT SHADER EDITOR")
        header.setStyleSheet("font-weight: bold; color: #888; font-size: 10px; margin-bottom: 0px;")
        editor_layout.addWidget(header)

        self.frag_edit = QTextEdit()
        self.frag_edit.setPlainText(DEFAULT_FRAGMENT_SHADER)
        self.frag_edit.setStyleSheet("""
            QTextEdit { 
                background-color: #1e1e1e; 
                color: #dcdcaa; 
                font-family: 'Consolas', 'Monaco', monospace; 
                font-size: 13px; 
                border: none; 
            }
        """)
        editor_layout.addWidget(self.frag_edit)

        self.run_btn = QPushButton("RUN SHADER")
        self.run_btn.setFixedHeight(40)
        self.run_btn.setCursor(Qt.PointingHandCursor)
        self.run_btn.setStyleSheet("""
            QPushButton { 
                background-color: #333; color: white; font-weight: bold; border: 1px solid #555; 
            }
            QPushButton:hover { background-color: #444; }
            QPushButton:pressed { background-color: #222; }
        """)
        self.run_btn.clicked.connect(self.apply_shaders)
        editor_layout.addWidget(self.run_btn)

        # --- CANVAS PANEL ---
        self.canvas = ShaderToyCanvas()
        
        # Add to splitter
        self.splitter.addWidget(editor_frame)
        self.splitter.addWidget(self.canvas)
        self.splitter.setStretchFactor(1, 2) # Give more space to the canvas

        layout.addWidget(self.splitter)

        # Timer for animation
        self.timer = QTimer()
        self.timer.timeout.connect(self.canvas.update)
        self.timer.start(16)

    def apply_shaders(self):
        f_code = self.frag_edit.toPlainText()
        if self.canvas.compile_shaders(DEFAULT_VERTEX_SHADER, f_code):
            self.canvas.update()
        else:
            QMessageBox.critical(self, "GLSL Syntax Error", "Check the terminal for compilation errors.")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
