#!/usr/local/bin/python

import sys, os
from PyQt4 import QtGui, QtCore, QtOpenGL

import copper
from gui.dialogs import RenderNodeDialog

from gui import TabbedPanelManager

from gui.widgets import TimeLineWidget

from gui.panels import ParametersPanel
from gui.panels import NetworkViewPanel
from gui.panels import TreeViewPanel
from gui.panels import CompositeViewPanel
from gui.panels import PythonShellPanel

os.environ['PYOPENCL_COMPILER_OUTPUT'] = "1"

class Workarea(QtGui.QWidget):
    def __init__(self, parent=None, engine=None):
        QtGui.QWidget.__init__(self, parent)
        self.engine = engine
        self.engine.set_network_change_callback(self.rebuild_widgets)
        self.setObjectName("Workarea")

        # Basic UI panels
        self.parmetersEditor    = ParametersPanel(self, engine = self.engine)
        self.nodeFlow           = NetworkViewPanel(self, engine = self.engine)
        self.imageViewer        = CompositeViewPanel(self, engine = self.engine)
        self.nodeTree           = TreeViewPanel(self, engine = self.engine, viewer = self.imageViewer, params = self.parmetersEditor)
        #self.pythonShell        = PythonShellPanel(self, engine = self.engine)

        # TimeLine widget
        self.timeLine           = TimeLineWidget(self)

        # Now init our UI 
        self.initUI()
        
    def initUI(self): 

        # Create layout and place widgets
        VBox = QtGui.QVBoxLayout()    
        VBox.setContentsMargins(0, 0, 0, 0)
        HBox = QtGui.QHBoxLayout()
        HBox.setContentsMargins(0, 0, 0, 0)
        VBox.addLayout(HBox)
        VBox.addWidget(self.timeLine)

        panelMgr1 = TabbedPanelManager(engine=self.engine)
        panelMgr1.setAllowedPanelTypes([ParametersPanel, CompositeViewPanel, TreeViewPanel, NetworkViewPanel, PythonShellPanel])
        panelMgr1.addPaneTab(self.imageViewer)

        panelMgr2 = TabbedPanelManager(engine=self.engine)
        panelMgr2.setAllowedPanelTypes([ParametersPanel, CompositeViewPanel, TreeViewPanel, NetworkViewPanel, PythonShellPanel])
        panelMgr2.addPaneTab(self.parmetersEditor)

        panelMgr3 = TabbedPanelManager(engine=self.engine)
        panelMgr3.setAllowedPanelTypes([ParametersPanel, CompositeViewPanel, TreeViewPanel, NetworkViewPanel, PythonShellPanel])
        panelMgr3.addPaneTab(self.nodeFlow)
        panelMgr3.addPaneTab(self.nodeTree)
        #panelMgr3.addPaneTab(self.pythonShell)

        VSplitter = QtGui.QSplitter(QtCore.Qt.Vertical)
        VSplitter.setMinimumWidth(370)
        VSplitter.addWidget(panelMgr2)
        VSplitter.addWidget(panelMgr3)

        HSplitter = QtGui.QSplitter(QtCore.Qt.Horizontal)
        HSplitter.addWidget(panelMgr1)
        HSplitter.addWidget(VSplitter)
        HSplitter.setStretchFactor (0, 1)
        HSplitter.setStretchFactor (1, 0)   

        HBox.addWidget(HSplitter)
        self.setLayout(VBox)
        self.show()
       
    def rebuild_widgets(self):
        print "Network change callback called by engine..."
        self.tree_view.emit(QtCore.SIGNAL('network_changed'))

    @QtCore.pyqtSlot()   
    def renderNode(self, node_path):
        RenderNodeDialog.render(self.engine, node_path)        

class Window(QtGui.QMainWindow):
    def __init__(self, engine):
        super(Window, self).__init__()
        self.engine = engine
        if not self.engine.have_gl:
            print "OpecCL - OpenGL interoperability not supported !!! Abort."
            exit()

        self.initUI()

    def close(self):
        exit()

    def open_project(self):
        try:
            fname = QtGui.QFileDialog.getOpenFileName(self, 'Open file', "/Users")
        except:
            raise
        if fname:    
            self.engine.open_project(str(fname))   

    def save_project(self):
        fname = QtGui.QFileDialog.getSaveFileName(self, 'Save file', "/Users")    
        if fname:
            self.engine.save_project(fname)

    def load_style(self):
        sqq_filename="media/copper.stylesheet.qss"
        with open(sqq_filename,"r") as fh:
            self.setStyleSheet(fh.read())

    def initUI(self):
        self.setMinimumWidth(740)
        self.setMinimumHeight(540)
        self.resize(1400, 900)
        self.workarea = Workarea(self, engine=self.engine)
        self.setCentralWidget(self.workarea)


        exitAction = QtGui.QAction(QtGui.QIcon('icons/main/exit.svg'), 'Exit', self)
        exitAction.setObjectName("ActionExitApp")
        exitAction.setShortcut('Ctrl+Q')
        exitAction.setStatusTip('Exit application')
        exitAction.triggered.connect(self.close)

        openAction = QtGui.QAction(QtGui.QIcon('icons/main/document_open.svg'), 'Open project', self)
        openAction.setShortcut('Ctrl+O')
        openAction.setStatusTip('Open project')
        openAction.triggered.connect(self.open_project)

        saveAction = QtGui.QAction(QtGui.QIcon('icons/main/document_save.svg'), 'Save project', self)
        saveAction.setShortcut('Ctrl+S')
        saveAction.setStatusTip('Save project')
        saveAction.triggered.connect(self.save_project)


        reloadStylAction = QtGui.QAction(QtGui.QIcon('icons/main/reload.svg'), 'Reload QSS', self)
        reloadStylAction.setShortcut('Ctrl+R')
        reloadStylAction.setStatusTip('Reload style')
        reloadStylAction.triggered.connect(self.load_style)

        menubar = self.menuBar()

        fileMenu = menubar.addMenu('&File')
        fileMenu.addAction(reloadStylAction)
        fileMenu.addAction(openAction)
        fileMenu.addAction(saveAction)
        fileMenu.addAction(exitAction)

        viewMenu = menubar.addMenu('&View')

        helpManu = menubar.addMenu('&Help')
        
        toolbar = self.addToolBar('Toolbar')
        toolbar.addAction(reloadStylAction)
        toolbar.addAction(openAction)
        toolbar.addAction(saveAction)
        toolbar.addAction(exitAction)
        
        self.setWindowTitle("Copperfield")
        self.statusBar().showMessage('Ready...')


if __name__ == '__main__':
    app = QtGui.QApplication(sys.argv)
    app.setStyle(QtGui.QStyleFactory.create('Plastique'))

    app.setWindowIcon(QtGui.QIcon('icons/copper_icon.png'))

    engine = copper.CreateEngine("GPU")
    engine.test_project()

    window = Window(engine)
    window.load_style()
    window.show()    
    window.raise_() 
    window.activateWindow()
    sys.exit(app.exec_())