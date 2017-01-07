from PyQt4 import QtGui, QtCore, QtOpenGL, Qt
from OpenGL.GL import *
from OpenGL import GL
from OpenGL.GLU import *

import numpy
import copper
import math

from gui.signals import signals
from gui.widgets import PathBarWidget
from gui.panels.base_panel import NetworkPanel

from copper.vmath import Matrix4, Vector3
from .camera import Camera
from .ogl_objcache import OGL_ObjCacheManager

class SceneViewPanel(NetworkPanel):
    def __init__(self):  
        NetworkPanel.__init__(self) 

        self.scene_view_widget = SceneViewWidget(self, self)
        self.addWidget(self.scene_view_widget)

    @classmethod
    def panelTypeName(cls):
        return "Scene View"


class SceneViewWidget(QtOpenGL.QGLWidget):

    ObjCache = OGL_ObjCacheManager()
    
    def __init__(self, parent, panel):
        format = QtOpenGL.QGLFormat.defaultFormat()
        format.setSampleBuffers(True)
        format.setSamples(16)
        QtOpenGL.QGLWidget.__init__(self, format, parent)
        self.panel = panel
        self.width = 1920
        self.height = 1200
        self.setMinimumSize(640, 360)
        self.orbit_mode = False
        self.old_mouse_x = self.old_mouse_y = 0
        self.cameras = {
            'persp': Camera(),
        }

        self.current_camera = 'persp'

        # connect panel signals
        self.panel.signals.copperNodeModified[str].connect(self.updateNodeDisplay)

    def drawBackground(self, background_image_name=""):
        glDisable(GL_DEPTH_TEST)
        glBegin(GL_QUADS)
        glColor3f(0.39, 0.50, 0.55)
        glVertex2f(0.0, 0.0)
        glVertex2f(self.width, 0.0)

        glColor3f(0.75, 0.78, 0.78)
        glVertex2f(self.width, self.height)
        glVertex2f(0.0, self.height)
        glEnd()
        glEnable(GL_DEPTH_TEST)

    def drawSceneGrid(self):
        grid_step = 0.1
        grid_size = 4.0
        grid_half_size = grid_size / 2.0

        # Minor lines
        lines_quantity = int(grid_size / grid_step) + 1
        glColor3f( 0.35, 0.35, 0.35 )
        glLineWidth(0.5)

        # Draw minor lines
        glBegin(GL_LINES)
        x_coord = - grid_half_size
        for x in range(lines_quantity):
            glVertex3f(x_coord, 0.0, -grid_half_size)
            glVertex3f(x_coord, 0.0, grid_half_size)
            x_coord += grid_step

        z_coord = - grid_half_size
        for z in range(lines_quantity):
            glVertex3f(-grid_half_size, 0.0, z_coord)
            glVertex3f(grid_half_size, 0.0, z_coord)
            z_coord += grid_step

        glEnd()

        # Major lines
        grid_step *= 10
        lines_quantity = int(grid_size / grid_step) + 1
        glLineWidth(1.0)

        # Draw major lines
        glBegin(GL_LINES)
        x_coord = - grid_half_size
        for x in range(lines_quantity):
            glVertex3f(x_coord, 0.0, -grid_half_size)
            glVertex3f(x_coord, 0.0, grid_half_size)
            x_coord += grid_step

        z_coord = - grid_half_size
        for z in range(lines_quantity):
            glVertex3f(-grid_half_size, 0.0, z_coord)
            glVertex3f(grid_half_size, 0.0, z_coord)
            z_coord += grid_step

        glEnd()

        # Draw Origin
        glDisable(GL_DEPTH_TEST)
        glLineWidth(1.0)
        glBegin(GL_LINES)
        # X axis
        glColor3f( 0.95, 0.05, 0.05 )
        glVertex3f(0.0, 0.0, 0.0)
        glVertex3f(0.8, 0.0, 0.0)
        # Y axis
        glColor3f( 0.05, 0.95, 0.05 )
        glVertex3f(0.0, 0.0, 0.0)
        glVertex3f(0.0, 0.8, 0.0)
        # z axis
        glColor3f( 0.05, 0.05, 0.95 )
        glVertex3f(0.0, 0.0, 0.0)
        glVertex3f(0.0, 0.0, 0.8)
        glEnd()

        glEnable(GL_DEPTH_TEST)

    def drawSceneObjects(self):
        glTranslatef(0.0, 0.0, 0.0)

        glPointSize( 3.0 )
        for node in copper.engine.node("/obj").children():
            ogl_obj_cache = SceneViewWidget.ObjCache.getObjNodeGeometry(node)

            if ogl_obj_cache:
                print "Drawing node: %s" % node.path()

                transform = node.worldTransform()
                glPushMatrix()
                glMultMatrixf(transform.m)

                glEnableClientState(GL_VERTEX_ARRAY)
                glBindBuffer (GL_ARRAY_BUFFER, ogl_obj_cache.vbo)
                
                glVertexPointer (3, GL_FLOAT, 0, None)
                glDrawArrays (GL_POINTS, 0, ogl_obj_cache.n_points)
                
                glBindBuffer(GL_ELEMENT_ARRAY_BUFFER,0) # reset
                glDisableClientState(GL_VERTEX_ARRAY)
                glPopMatrix()

            #display_node = node.displayNode()
            #if display_node:
            #    print "Drawing sop node: %s" % display_node.path()
            #    geometry = display_node.geometry()
            #    if geometry:
            #        print "Drawing geometry for sop node: %s" % display_node.path()
            #        glColor3f(0.2,0.3,0.9)
            #        glBegin(GL_POINTS)
            #
            #        for point in geometry.raw_points():
            #            glVertex3f(point[0], point[1], point[2])

            #        glEnd()

    @QtCore.pyqtSlot(str)
    def updateNodeDisplay(self, node_path=None):
        # Now using quick and dirty hack to check that only geometry nodes changes reflected in scene view
        if str(node_path).startswith("/obj"):
            self.updateGL()

    def paintGL(self):
        if not self.isValid():
            return

        glClearColor(0.5, 0.5, 0.5, 1.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        # Drab back plane elements
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        glOrtho(0.0, self.width, self.height, 0.0, -100.0, 100.0)

        # Background
        self.drawBackground(background_image_name = self.viewport.getBackgroundImageName())

        # Draw scene
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()

        self.viewport.buildFrustum()
        M = self.viewport.getTransform()

        glMultMatrixf(M.m)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

        # Grid
        self.drawSceneGrid()

        # Scene objects
        self.drawSceneObjects()

        glFlush()


    def resizeGL(self, widthInPixels, heightInPixels):
        self.width = widthInPixels
        self.height = heightInPixels
        self.viewport.setViewportDimensions(widthInPixels, heightInPixels)

        if self.isValid():
            glViewport(0, 0, widthInPixels, heightInPixels)
        

    def initializeGL(self):
        glClearDepth( 1.0 )              
        glDepthFunc( GL_LESS )
        glEnable( GL_DEPTH_TEST )
        glEnable( GL_POINT_SMOOTH )
        #glEnable(GL_MULTISAMPLE)
        #glEnable(GL_LINE_SMOOTH)
        glShadeModel( GL_SMOOTH )

        #glMatrixMode(GL_PROJECTION)
        ##lLoadIdentity()                    
        #gluPerspective(45.0,1.33,0.1, 100.0) 
        #glMatrixMode(GL_MODELVIEW)

    @property
    def viewport(self):
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
                    self.cameras[self.current_camera].pan( delta_x, delta_y )
                else:
                    # orbit camera
                    self.cameras[self.current_camera].orbit(delta_x, delta_y)
            elif int(mouseEvent.buttons()) & QtCore.Qt.RightButton :
                # dolly camera
                self.cameras[self.current_camera].dolly( 3*(delta_x + delta_y), False )
            elif int(mouseEvent.buttons()) & QtCore.Qt.MidButton :
                # pan camera
                self.cameras[self.current_camera].pan( delta_x, delta_y )
            
        self.update()
        
        self.old_mouse_x = mouseEvent.x()
        self.old_mouse_y = mouseEvent.y()


