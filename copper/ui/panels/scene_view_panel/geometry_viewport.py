from PyQt5 import QtWidgets, QtGui, QtCore, QtOpenGL, Qt
from OpenGL.GL import *
from OpenGL import GL
from OpenGL.GLU import *

import time
import logging
import numpy as np
from copper import hou
import math
from PIL import Image

import moderngl

from copper.core.op.op_node import OP_Node
from copper.obj import ObjNode
from copper.ui.utils import clearLayout
from copper.ui.signals import signals
from copper.ui.widgets import PathBarWidget, CollapsableWidget
from copper.ui.panels.base_panel import PathBasedPaneTab

from copper.core.vmath import Matrix4, Vector3
from .camera import Camera
from .scene_manager import OGL_Scene_Manager, scene_manager

from .scene_manager.drawable import SimpleBackground
from .layouts import viewport_layout_types

logger = logging.getLogger(__name__)


from pyrr import Matrix44

from .qmodernglwidget import QModernGLWidget

from moderngl_window.opengl.vao import VAO

def quad_fs(ctx, size=(1.0, 1.0), pos=(0.0, 0.0), name=None):
    """
    Creates a 2D quad VAO using 2 triangles with normals and texture coordinates.
    """
    width, height = size
    xpos, ypos = pos

    shader_program = ctx.program(
            vertex_shader='''
                #version 330
                
                in vec3 in_position;
                in vec2 in_texcoord_0;

                uniform mat4 m_proj;
                uniform mat4 m_model;
                uniform mat4 m_view;
                uniform float aa_passes;
                uniform float aa_pass;

                out vec2 uv;
                out float passes;
                out float pass;

                void main() {
                    gl_Position = m_proj * m_view * m_model * vec4(in_position, 1.0);
                    uv = in_texcoord_0;
                    passes = aa_passes;
                    pass = aa_pass;
                }
            ''',
            fragment_shader='''
                #version 330
                
                uniform sampler2D texture0;

                out vec4 fragColor;
                
                in vec2 uv;
                in float passes;
                in float pass;

                void main() {
                    vec4 color = texture(texture0, uv);
                    color.a *= 1.0 - (pass / passes);
                    fragColor = color;
                }
            ''',
        )

    print("Program %s " % shader_program)

    pos_data = np.array([
        xpos - width / 1.0, ypos + height / 1.0, -1.0,
        xpos - width / 1.0, ypos - height / 1.0, -1.0,
        xpos + width / 1.0, ypos - height / 1.0, -1.0,
        xpos + width / 1.0, ypos + height / 1.0, -1.0,
    ], dtype=np.float32)

    normal_data = np.array([
        0.0, 0.0, 1.0,
        0.0, 0.0, 1.0,
        0.0, 0.0, 1.0,
        0.0, 0.0, 1.0,
    ], dtype=np.float32)

    uv_data = np.array([
        0.0, 0.0,
        0.0, 1.0,
        1.0, 1.0,
        1.0, 0.0,
    ], dtype=np.float32)

    ibo = ctx.buffer(np.array([0,1,2,0,2,3]).astype('i4').tobytes())

    vbo1 = ctx.buffer(pos_data.astype('f4').tobytes())
    #vbo2 = ctx.buffer(normal_data.astype('f4').tobytes())
    vbo3 = ctx.buffer(uv_data.astype('f4').tobytes())


    vao_content = [
        (vbo1, "3f", "in_position"),
        #(vbo2, "3f", "in_normal"),
        (vbo3, "2f", "in_texcoord_0")
    ]

    vao = ctx.vertex_array(shader_program, vao_content, index_buffer=ibo)

    return vao

class HUD_Info():
    def __init__(self):
        self.fps = 0

class Pixmap_Overlay(QtWidgets.QWidget):
    def __init__(self):
        QtWidgets.QWidget.__init__(self)
        self.setPixmap()
        self.setAttribute(Qt.Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.Qt.WA_TranslucentBackground, True) 

    def setPixmap(self, pixmap=None):
        if pixmap:
            self._pixmap = pixmap
            self.paintEvent = self._paintEvent
        else:
            self.paintEvent = self._paintEventNull

    def _paintEventNull(self, event):
        pass

    def _paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.drawPixmap(0, 0, self._pixmap)
        painter.end()

class Signals(QtCore.QObject):
    request_aa_pass = QtCore.pyqtSignal(int)

    def __init__(self, parent=None):  
        QtCore.QObject.__init__(self, parent)

class GeometryViewport(QModernGLWidget):

    test = None
    
    def __init__(self, parent, panel=None, share_widget=None, scene_manager=None):
        super(GeometryViewport, self).__init__(parent)

        # panel section
        self.panel = panel
        self.setMinimumSize(160, 160)

        # mouse interactions
        self.orbit_mode = False
        self.old_mouse_x = self.old_mouse_y = 0

        # some viewport stuff
        self.cameras = {
            'persp': Camera(),
            'top': Camera(position=[10,0,0]),
            'left': Camera(position=[0,0,10])
        }

        self.current_camera = 'persp'
        self._show_points = None
        self._init_done = False

        self.scene_manager = OGL_Scene_Manager()

        # offscreen render target / offscreen HUD pixmap
        self.offscreen = None
        self.hud_pixmap = None

        # aa stuff
        self.aa_buffer = None
        self.max_aa_samples = 16
        self.aa_pass_num = 0

        # helpers
        self.m_identity = Matrix44.identity() # just a helper

        # HUD seciton
        self.hud_font = QtGui.QFont("verdana", 8)
        self.hud_info = HUD_Info()
        self.hud_overlay = Pixmap_Overlay()
        self.hud_overlay.setParent(self)
        self.hud_overlay.show()

        # connect panel signals
        self.panel.signals.copperNodeModified[OP_Node].connect(self.updateNodeDisplay)

        # connect panel buttons signals
        self.panel.display_options.toggle_points_btn.pressed.connect(self.toggleShowPoints)

        # aa signalling
        self.signals = Signals(self)
        self.signals.request_aa_pass.connect(self.doAAPass)

        logger.debug("GeometryViewport widget created")

    def minimumSizeHint(self):
        return QtCore.QSize(200, 200)

    def sizeHint(self):
        return QtCore.QSize(400, 400)

    def drawSceneObjects(self, m_view, m_proj):
        for drawable in self.scene_manager.objects():
            # draw polygons
            drawable.model.write(self.m_identity.astype('f4').tobytes())
            drawable.view.write(m_view.astype('f4').tobytes())
            drawable.projection.write(m_proj.astype('f4').tobytes())
            drawable.draw(show_points = self._show_points)

    @QtCore.pyqtSlot(int)
    def doAAPass(self, aa_pass_num):
        self.update()
        
    @QtCore.pyqtSlot()
    def toggleShowPoints(self):
        self._show_points = not self._show_points
        self.update()

    @QtCore.pyqtSlot(OP_Node)
    def updateNodeDisplay(self, node):
        # Now using quick and dirty hack to check that only geometry nodes changes reflected in scene view
        if node.path().startswith("/obj"):
            print("!!!!!!!!!!!!!!!!!!!")
            self.update()

    def initAA(self, num_samples=16):
        import ghalton

        self.max_aa_samples = num_samples
        self.aa_pass_num = 0
        
        dim = 2
        sequencer = ghalton.GeneralizedHalton(ghalton.EA_PERMS[:dim])
        self.aa_points = sequencer.get(num_samples)

        if self.quad_fs:
            self.quad_fs.program['aa_passes'].value = num_samples

    def init(self):
        self.makeCurrent()
        self.ctx.point_size = 2.0
        self.scope = None
        
        self.buildOffscreen(self.ctx.viewport[2], self.ctx.viewport[3])
        self.scene_manager.init()

        # A fullscreen quad just for rendering one pass to offscreen textures
        self.quad_fs = quad_fs(self.ctx)
        self.quad_fs.program['aa_passes'].value = self.max_aa_samples
        self.quad_fs.program['m_model'].write(Matrix44.identity().astype('f4').tobytes())
        self.quad_fs.program['m_view'].write(Matrix44.identity().astype('f4').tobytes())


        # init AA
        self.initAA(16)

        self._init_done = True

    def renderHUD(self, aa_pass_num):
        if aa_pass_num == 0:
            # render aa pass independent HUD info
            self.hud_pixmap.fill(QtGui.QColor(0, 0, 0, 0))
            painter = QtGui.QPainter(self.hud_pixmap)
            painter.setPen(QtGui.QColor(255, 128, 16))
            painter.setFont(self.hud_font)
            painter.drawText(10, 10, "FPS: %.1f" % self.hud_info.fps)
            painter.end()
            self.hud_overlay.update()
        else:
            # render aa pass dependent HUD info
            pass

    def render(self):
        start_time = time.time()

        m_view = self.activeCamera.getTransform()
        m_proj = self.activeCamera.getProjection(jittered=True, point=self.aa_points[self.aa_pass_num])

        # Render the scene to offscreen buffer
        self.offscreen.use()
        self.offscreen.clear(1.0, 0.0, 0.0, 0.0)
    

        self.ctx.multisample = False
        self.ctx.disable(moderngl.DEPTH_TEST)

        # Render the scene
        self.scene_manager.background.draw()

        self.ctx.enable(moderngl.DEPTH_TEST)
        # TODO: we might also want to pass model matrix so we can get different grid orientations instead of rebuilding grid
        self.scene_manager.grid.view.write(m_view.astype('f4').tobytes())
        self.scene_manager.grid.projection.write(m_proj.astype('f4').tobytes())
        self.scene_manager.grid.draw()

        self.scene_manager.origin.model.write(Matrix44.identity().astype('f4').tobytes())
        self.scene_manager.origin.view.write(m_view.astype('f4').tobytes())
        self.scene_manager.origin.projection.write(m_proj.astype('f4').tobytes())
        self.scene_manager.origin.draw()

        # geometry
        self.drawSceneObjects(m_view, m_proj)

        # Activate the window screen as the render target
        self.screen.use()
        if self.aa_pass_num == 0:
            self.screen.clear(0.0, 0.0, 1.0, 0.0)

        # render hud surface
        self.renderHUD(self.aa_pass_num)

        # Render aa buffer to screen
        self.ctx.disable(moderngl.DEPTH_TEST)
        self.offscreen_diffuse.use(location=0)
        prog = self.quad_fs.program
        prog['m_proj'].write(Matrix44.orthogonal_projection(-1, 1, 1, -1, 1, 10).astype('f4').tobytes())
        prog['aa_pass'].value = self.aa_pass_num
        
        self.ctx.enable(moderngl.BLEND)
        self.ctx.blend_equation = moderngl.FUNC_ADD
        self.ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA
        self.quad_fs.render(moderngl.TRIANGLES)
        self.ctx.disable(moderngl.BLEND)
        self.ctx.finish()

        time_now = time.time()
        self.hud_info.fps = 1.0 / (time_now - start_time)

        # do aa passes
        if self.aa_pass_num < (self.max_aa_samples-1):
            print("aa pass %s" % self.aa_pass_num)
            self.signals.request_aa_pass.emit(self.aa_pass_num)
            self.aa_pass_num += 1
        else:
            self.aa_pass_num = 0

    def draw(self):
        self.render()

    def buildOffscreen(self, width, height):
        # offscreen render target
        if self.offscreen:
            self.offscreen.release()
            self.offscreen_diffuse.release()
            self.offscreen_normals.release()
            self.offscreen_depth.release()
            self.offscreen = None
            self.offscreen_diffuse = None
            self.offscreen_normals = None
            self.offscreen_depth = None

        if not self.offscreen:
            buffer_size = (width, height)
            # RGBA color/diffuse layer
            self.offscreen_diffuse = self.ctx.texture(buffer_size, 4)

            # Textures for storing normals (16 bit floats)
            self.offscreen_normals = self.ctx.texture(buffer_size, 4, dtype='f2')
            
            # Texture for storing depth values
            self.offscreen_depth = self.ctx.depth_texture(buffer_size)

            # create a framebuffer we can render to
            self.offscreen = self.ctx.framebuffer(
                color_attachments=[
                    self.offscreen_diffuse,
                    self.offscreen_normals
                ],
                depth_attachment=self.offscreen_depth,
            )
            self.offscreen.viewport = (0, 0, width, height)

        # offscreen hud pixmap
        if self.hud_pixmap:
            self.hud_pixmap = None

        if not self.hud_pixmap:
            self.hud_pixmap = QtGui.QPixmap(width, height)
            self.hud_overlay.setPixmap(self.hud_pixmap)

    def resize(self, width, height):
        self.aa_pass_num = 0
        self.makeCurrent()

        self.activeCamera.setViewportDimensions(width, height)
        self.ctx.viewport = (0, 0, width, height)

        self.screen = self.ctx.detect_framebuffer(self.defaultFramebufferObject())

        self.buildOffscreen(width, height)
        self.hud_overlay.resize(width, height)

    @property
    def activeCamera(self):
        return self.cameras[self.current_camera]


    def mousePressEvent(self, mouseEvent):
        self.orbit_mode = True
        self.old_mouse_x = mouseEvent.x()
        self.old_mouse_y = mouseEvent.y()
        self.setCursor(QtCore.Qt.ClosedHandCursor)


    def mouseReleaseEvent(self, mouseEvent):
        self.orbit_mode = False
        self.setCursor(QtCore.Qt.OpenHandCursor)


    def mouseMoveEvent(self, mouseEvent):
        if int(mouseEvent.buttons()) != QtCore.Qt.NoButton :
            # user is orbiting camera
            delta_x = mouseEvent.x() - self.old_mouse_x
            delta_y = self.old_mouse_y - mouseEvent.y()
            
            if int(mouseEvent.buttons()) & QtCore.Qt.LeftButton :
                if mouseEvent.modifiers() == QtCore.Qt.AltModifier :
                    # pan camera
                    self.activeCamera.pan( delta_x, delta_y )
                else:
                    # orbit camera
                    self.activeCamera.orbit(delta_x, delta_y)
            elif int(mouseEvent.buttons()) & QtCore.Qt.RightButton :
                # dolly camera
                self.activeCamera.dolly( 3*(delta_x + delta_y), False )
            elif int(mouseEvent.buttons()) & QtCore.Qt.MidButton :
                # pan camera
                self.activeCamera.pan( delta_x, delta_y )
            
            self.aa_pass_num = 0
            self.update()
        
            self.old_mouse_x = mouseEvent.x()
            self.old_mouse_y = mouseEvent.y()


    # hou module stuff
    def camera(self) -> ObjNode or None:
        '''
        If the viewport is currently looking through a camera or light (not necessarily locked to it), this returns an object representing the camera/light’s node. 
        Returns None if the viewport is not looking through a camera/light.
        '''
        return None