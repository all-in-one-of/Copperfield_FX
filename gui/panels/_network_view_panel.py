import logging

from PyQt5 import QtWidgets, QtGui, QtCore, QtOpenGL, Qt
from OpenGL.GL import *
from OpenGL import GL
from OpenGL.GLU import *

import numpy
import copper
import math

from copper import hou as engine
from copper.op.base import OpRegistry
from gui.signals import signals
from gui.widgets import PathBarWidget, CollapsableWidget

from .base_panel import NetworkPanel

logger = logging.getLogger(__name__)


def next_greater_power_of_2(x):  
    return 2**(x-1).bit_length()

class NetworkViewPanel(NetworkPanel):
    def __init__(self):  
        NetworkPanel.__init__(self) 

        self.network_view_controls = NetworkViewControls(self)
        self.network_view_widget = NetworkViewWidget(self)

        self.addWidget(self.network_view_controls)
        self.addWidget(self.network_view_widget)

    @classmethod
    def panelTypeName(cls):
        return "Network View"


class NetworkViewControls(CollapsableWidget):
    def __init__(self, parent=None):
        CollapsableWidget.__init__(self, parent)

        self.snap_to_grid_btn = QtWidgets.QPushButton()
        self.snap_to_grid_btn.setCheckable(True)
        self.snap_to_grid_btn.setIcon(QtGui.QIcon('gui/icons/main/network_view/snap_to_grid.svg'))
        self.snap_to_grid_btn.setStatusTip('Show/hide grid and enable/disable snapping')

        self.addWidget(self.snap_to_grid_btn)
        self.addStretch(1)


class NodeLinkItem(QtWidgets.QGraphicsItem):
    def __init__(self, parent, socket_from, socket_to):
        QtWidgets.QGraphicsItem.__init__(self, parent)

        self._socket_from = socket_from
        self._socket_to = socket_to

    def paint(self, painter, option, widget=None):
        painter.drawLine(self._socket_from.pos(), self._socket_to.pos())



class NodeSocketItem(QtWidgets.QGraphicsItem):
    INPUT_SOCKET = 1
    OUTPUT_SOCKET = 2

    STACK_LEFT = 1
    STACK_RIGHT = 2
    STACK_TOP = 3
    STACK_BOTTOM = 4

    def __init__(self, parent, socket_type=None, stack_side=STACK_TOP):
        QtWidgets.QGraphicsItem.__init__(self, parent)
        self.stack_side = stack_side
        self.node = parent.node
        self._socket_type = socket_type
        self.socket_color = QtGui.QColor(128, 128, 128)
        self.setAcceptHoverEvents(True)
        self.setZValue(self.parentItem().zValue() - 100)
        self.putInPlace()

    def paint(self, painter, option, widget=None):
        # LOD here. Do not draw socket if the viewport scale factor is less than 0.5
        device_transfrom = 1.0 / painter.deviceTransform().m11()
        socket_rect = self.boundingRect()
        socket_outline_rect = self.boundingRect().adjusted(-device_transfrom, -device_transfrom, device_transfrom, device_transfrom)

        painter.fillRect(socket_outline_rect, QtGui.QColor(16, 16, 16))
        painter.fillRect(socket_rect, self.socket_color)

    def boundingRect(self):
        # LOD here. Do not draw socket if the viewport scale factor is less than 0.5
        socket_width = self.size().width()
        socket_height = self.size().height()
        return QtCore.QRectF(-socket_width/2, -socket_height/2, socket_width, socket_height)

    def size(self):
        if self.stack_side in [NodeSocketItem.STACK_TOP, NodeSocketItem.STACK_BOTTOM]:
            return QtCore.QSizeF(9, 2.25)
        else:
            return QtCore.QSizeF(2.25, 9)

    def putInPlace(self):
        node_item = self.parentItem()
        parent_size = node_item.size()
        
        if self.stack_side in [NodeSocketItem.STACK_TOP, NodeSocketItem.STACK_BOTTOM]:
    
            if self.stack_side == NodeSocketItem.STACK_TOP:
                self.setPos(0, -(parent_size.height() / 2 + self.size().height() / 2))
            else:
                self.setPos(0, (parent_size.height() / 2 + self.size().height() / 2))

            # we need to place sockets once again so they accupy all the available space on the edge
            existing_sockets = node_item.inputSockets(self.stack_side)
            if existing_sockets:
                total_sockets_count = len(existing_sockets) + 1
                sockets_distance = node_item.size().width() / total_sockets_count
                socket_position = (sockets_distance / 2) - node_item.size().width() / 2

                for existing_socket in existing_sockets:
                    existing_socket.setX(socket_position)
                    socket_position += sockets_distance

                self.setX(socket_position)



        elif self.stack_side in [NodeSocketItem.STACK_LEFT, NodeSocketItem.STACK_RIGHT]:
            pass


class NodeItem(QtWidgets.QGraphicsItem):
    def __init__(self, node):      
        QtWidgets.QGraphicsItem.__init__(self)
        self.node = node
        self._inputs = {NodeSocketItem.STACK_TOP: [], NodeSocketItem.STACK_LEFT: [], NodeSocketItem.STACK_RIGHT: [], NodeSocketItem.STACK_BOTTOM: []}
        self._outputs = {NodeSocketItem.STACK_TOP: [], NodeSocketItem.STACK_LEFT: [], NodeSocketItem.STACK_RIGHT: [], NodeSocketItem.STACK_BOTTOM: []}
        self._selected_indirect = False # this flag shows us that this node selected outside the widget
             
        if self.node.iconName():
            self.icon = QtGui.QIcon(self.node.iconName())
        else:
            self.icon = None
        
        self.setAcceptHoverEvents(True)
        self.setFlag(QtWidgets.QGraphicsItem.ItemSendsGeometryChanges)
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsMovable)
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsSelectable)

        # create input sockets
        for socket in self.node.inputs():
            socket_item = NodeSocketItem(self, socket_type=NodeSocketItem.INPUT_SOCKET, stack_side=NodeSocketItem.STACK_TOP)
            self._inputs[NodeSocketItem.STACK_TOP].append(socket_item)

        # create output sockets
        for socket in self.node.outputs():
            socket_item = NodeSocketItem(self,  socket_type=NodeSocketItem.OUTPUT_SOCKET, stack_side=NodeSocketItem.STACK_BOTTOM)
            self._outputs[NodeSocketItem.STACK_BOTTOM].append(socket_item)

    def inputSockets(self, stack_side):
        return tuple(self._inputs[stack_side])

    def outputSockets(self, stack_side):
        return tuple(self._outputs[stack_side])

    def autoPlace(self):
        scene = self.scene()
        items_rect = scene.itemsBoundingRect()

        pos = self.node.position()
        if pos[0] is None or pos[1] is None:
            self.node.setPosition((items_rect.right() + 20, items_rect.bottom() + 20))

        self.setPos(self.node.position()[0], self.node.position()[1])

    def paint(self, painter, option, widget=None):
        device_scale_factor = 1.0 / painter.deviceTransform().m11()
        
        if painter.deviceTransform().m11() > 0.75:
            [socket.show() for socket in self.childItems()]
        else:
            [socket.hide() for socket in self.childItems()]

        pen = QtGui.QPen()
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform, True)

        node_rect = self.boundingRect().adjusted(device_scale_factor, device_scale_factor, -device_scale_factor, -device_scale_factor)
        node_outline_rect = self.boundingRect()
        node_color = QtGui.QColor(160, 160, 160)
        if option.state & QtWidgets.QStyle.State_Selected:
            node_color = QtGui.QColor(196, 196, 196)
            # Draw selection border
            painter.fillPath(self.outlinePath(painter), QtGui.QBrush(QtGui.QColor(250, 190, 64)))

        # Draw node box itself
        painter.fillRect(node_outline_rect, QtGui.QColor(16, 16, 16))
        painter.fillRect(node_rect, node_color)

        # Draw error pattern if need
        if self.node.errors():
            error_brush = QtGui.QBrush(QtCore.Qt.red, QtCore.Qt.BDiagPattern)
            matrix = error_brush.matrix()
            matrix.scale(device_scale_factor * 0.75, device_scale_factor * 0.75)
            error_brush.setMatrix(matrix)
            painter.fillRect(node_rect, error_brush)

        ## Paint icon if there is one
        icon_size = next_greater_power_of_2(int(max(min(8 / device_scale_factor, 64), 8)))
        if self.icon and icon_size > 8:
            pixmap = self.icon.pixmap(icon_size, icon_size)
            painter.drawPixmap(-3, -3, 6, 6, pixmap)

        font = painter.font()
        font.setPointSize(4)
        painter.setFont(font)
        painter.setPen(QtGui.QColor(192, 192, 192))
        painter.drawText(self.size().width() / 2 + 1, 1, self.node.name())

    def boundingRect(self):
        socket_width = self.size().width()
        socket_height = self.size().height()
        return QtCore.QRectF(-socket_width/2, -socket_height/2, socket_width, socket_height)

    def outlinePath(self, painter):
        device_transfrom = 1.0 / painter.deviceTransform().m11()
        border_width = 2.0 *device_transfrom
        path = QtGui.QPainterPath()
        path.addRect(self.boundingRect().adjusted(-border_width, -border_width, border_width, border_width))
        border_width = 3.0 *device_transfrom
        for child_item in self.childItems():
            if child_item.isVisible():
                child_path = QtGui.QPainterPath()
                child_rect = child_item.mapRectToParent(child_item.boundingRect()).adjusted(-border_width, -border_width, border_width, border_width)
                child_path.addRect(child_rect)
                path += child_path

        return path

    def size(self):
        return QtCore.QSizeF(38, 10)

    def select(self):
        ''' This method is used to select node when Network View panel recieves signal copperNodeSelected.
            We need this to avoid signals loop. Because copperNodeSelected signal was fired by other widget, 
            this copper node is already selected, so we need only update graphics item without sending signal
            again.
        '''
        self._selected_indirect = True
        for item in self.scene().selectedItems(): item.setSelected(False)
        self.setSelected(True)
        self._selected_indirect = False

    def itemChange(self, change, value, direct=True):
        ''' direct argument shows us that shit node wa selected inside the items scene. Otherwise don't propagate copperNodeSelected signal.
            Just change item state.
        '''
        if change == QtWidgets.QGraphicsItem.ItemSelectedChange:
            if value == True:
                # do stuff if selected
                if not self._selected_indirect:
                    signals.copperNodeSelected[str].emit(self.node.path()) 
            else:
                # do stuff if unselected
                pass

        elif change == QtWidgets.QGraphicsItem.ItemPositionChange:
            # snap to grid code here
            scene = self.scene()
            new_pos = value #QtCore.QPointF(value.toPointF()

            snapped_x = round((new_pos.x() / scene.gridSizeWidth)) * scene.gridSizeWidth
            snapped_y = round((new_pos.y() / scene.gridSizeHeight)) * scene.gridSizeHeight
            
            if abs(new_pos.x() - snapped_x) < 5: new_pos.setX(snapped_x)
            if abs(new_pos.y() - snapped_y) < 5: new_pos.setY(snapped_y)
            

            #print "ItemPositionChange %s" % new_pos
            value = QtCore.QVariant(new_pos)

        return super(NodeItem, self).itemChange(change, value)

    def contextMenuEvent(self, event):
        logger.debug("Context menu")


class NodeFlowScene(QtWidgets.QGraphicsScene):
    def __init__(self, parent=None):      
        QtWidgets.QGraphicsScene.__init__(self, parent) 
        self.nodes_map = {}

        self.gridSizeWidth = 60
        self.gridSizeHeight = 30 
        self.zoomLevel = 1.0
        self.setSceneRect(-100000, -100000, 200000, 200000)

    @QtCore.pyqtSlot()
    def addNode(self, node_path=None):
        if node_path:
            node = engine.node(node_path)
            if node:
                node_item= NodeItem(node)
                self.addItem(node_item)
                self.nodes_map[node_path] = node_item
                node_item.autoPlace()

    def buildNetworkLevel(self, node_path=None):
        node = engine.node(node_path)
        if node:
            self.network_level = node_path
            self.nodes_map = {}
            self.clear()
            # build node boxes
            for child in node.children():
                self.addNode(child.path())

    def zoom(self, zoomFactor):
        self.zoomLevel *= zoomFactor

    def drawBackground(self, painter, rect):
        painter.fillRect(rect, QtGui.QColor(42, 42, 42))

        if self.zoomLevel > 0.1:
            # Draw grid
            left = rect.left() - (rect.left() % self.gridSizeWidth)
            top = rect.top() - (rect.top() % self.gridSizeHeight)
     
            lines = []
     
            x = left
            while x < rect.right():
                lines.append( QtCore.QLineF(x, rect.top(), x, rect.bottom()) )
                x += self.gridSizeWidth

            y = top
            while y < rect.bottom():
                lines.append( QtCore.QLineF(rect.left(), y, rect.right(), y) )
                y += self.gridSizeHeight

            pen = QtGui.QPen(QtGui.QColor(64, 64, 64), 1)
            pen.setCosmetic(True)
            painter.setPen(pen)
            painter.drawLines(lines)

    def drawForeground(self, painter, rect):
        #painter.drawText(rect, "Network type name")
        pass

    def mousePressEvent(self, event):
        picked_item = self.itemAt(event.scenePos(), self.transform())

        # Bring picked items to front
        if picked_item:
            for item in self.items():
                item.setZValue(0)

            picked_item.setZValue(1)

        super(NodeFlowScene, self).mousePressEvent(event) # propogate event to items


    def selectNode(self, node_path):
        if node_path not in self.nodes_map:
            # If node is not in map we need to rebuild visual network
            self.buildNetworkLevel(engine.node(node_path).parent().path())

        # highlight selected node
        self.nodes_map[node_path].select()

    def contextMenuEvent(self, event):
        network_node = engine.node(self.network_level)

        menu = QtGui.QMenu(event.widget())
        group = QtGui.QActionGroup(menu)
        menu.addAction('Tool Menu...')

        add_operators_menu = menu.addMenu("Add")

        node_types = network_node.childTypeCategory().nodeTypes()
        for node_type_name, node_class in node_types.iteritems():
            icon = QtGui.QIcon(node_class.iconName())
            action = add_operators_menu.addAction(icon, node_type_name)
            action.setActionGroup(group)
            action.setData(node_type_name)
        
        group.triggered.connect(self.addOperator)

        menu.exec_(event.screenPos())

    def addOperator(self, action):
        network_node = engine.node(self.network_level)
        network_node.createNode(action.data().toPyObject())


class NetworkViewWidget(QtWidgets.QGraphicsView):
    def __init__(self, parent):  
        QtWidgets.QGraphicsView.__init__(self, parent)
        self.setObjectName("network_widget")

        self.scene = NodeFlowScene(self)
        self.setScene(self.scene)
        self.setMouseTracking(True)
        self.setInteractive(True) 

        ## No need to see scroll bars in flow editor
        self.setHorizontalScrollBarPolicy ( QtCore.Qt.ScrollBarAlwaysOff )
        self.setVerticalScrollBarPolicy ( QtCore.Qt.ScrollBarAlwaysOff )

        format = QtOpenGL.QGLFormat.defaultFormat()
        format.setSampleBuffers(True)
        format.setSamples(16)
        self.setViewport( QtOpenGL.QGLWidget(format) ) # Force OpenGL rendering mode.
        self.setViewportUpdateMode( QtWidgets.QGraphicsView.FullViewportUpdate )
        self.setDragMode( QtWidgets.QGraphicsView.RubberBandDrag )

        ## As a debug we always set new panel widget to "/"
        self.setNetworkLevel("/img")

        ## Connect panel signals
        self.parent().signals.copperNodeCreated[str].connect(self.copperNodeCreated)
        self.parent().signals.copperNodeSelected[str].connect(self.copperNodeSelected)

    @QtCore.pyqtSlot(str)
    def copperNodeCreated(self, node_path):
        node = engine.node(str(node_path))
        if node:
            if self.scene.network_level == node.parent().path():
                self.scene.addNode(str(node_path))

    @QtCore.pyqtSlot(str)
    def copperNodeSelected(self, node_path):
        self.scene.selectNode(str(node_path))

    def setNetworkLevel(self, node_path):
        self.scene.buildNetworkLevel(node_path)

    def wheelEvent(self, event):
         # Zoom Factor
        zoomInFactor = 1.05
        zoomOutFactor = 1 / zoomInFactor

        # Set Anchors
        self.setTransformationAnchor(QtWidgets.QGraphicsView.NoAnchor)
        self.setResizeAnchor(QtWidgets.QGraphicsView.NoAnchor)

        # Save the scene pos
        oldPos = self.mapToScene(event.pos())

        # Zoom
        if event.angleDelta().y() > 0:
            zoomFactor = zoomInFactor
        else:
            zoomFactor = zoomOutFactor
        
        self.scale(zoomFactor, zoomFactor)
        self.scene.zoom(zoomFactor) # This is used by scene view to determine current viewport zoom

        # Get the new position
        newPos = self.mapToScene(event.pos())

        # Move scene to old position
        delta = newPos - oldPos
        self.translate(delta.x(), delta.y())

    def mouseDoubleClickEvent(self, event):
        picked_item = self.itemAt(event.scenePos())
        self.buildNetworkLevel(picked_item.node.path())

    def keyPressEvent(self, event):
        if event.modifiers() == QtCore.Qt.AltModifier:
            self.setInteractive(False)
            self.setDragMode( QtGui.QGraphicsView.ScrollHandDrag )

    def keyReleaseEvent(self, event):
        self.setInteractive(True)
        self.setDragMode( QtGui.QGraphicsView.RubberBandDrag )



