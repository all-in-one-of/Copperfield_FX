from PyQt5 import QtWidgets, Qt, QtGui, QtCore

from gui.signals import signals
from copper import hou as engine

class PathBarWidget(QtWidgets.QFrame):
    def __init__(self, parent, panel): 
        QtWidgets.QFrame.__init__(self, parent)
        self.panel = panel  
        self.pinned = False
        self.history = []
        self.history_index = -1
        self.setObjectName("pathBar")
        
        self.layout = QtWidgets.QHBoxLayout()
        self.layout.setSpacing(2)
        self.layout.setContentsMargins(2, 2, 2, 2)

        self.btn_back = QtWidgets.QToolButton(self)
        self.btn_back.setIcon(QtGui.QIcon( "gui/icons/main/go-previous.svg"))
        self.btn_back.setEnabled(False)
        self.btn_back.pressed.connect(self.historyGoBack)

        self.btn_frwd = QtWidgets.QToolButton(self)
        self.btn_frwd.setIcon(QtGui.QIcon("gui/icons/main/go-next.svg"))
        self.btn_frwd.setEnabled(False)
        self.btn_frwd.pressed.connect(self.historyGoForward)

        self.btn_pin = QtWidgets.QToolButton(self)
        self.btn_pin.setObjectName("pin")
        self.btn_pin.setCheckable(True)
        self.btn_pin.pressed.connect(self.pinPressed)

        self.path_layout = QtWidgets.QHBoxLayout()
        self.path_layout.setSpacing(0)
        self.path_layout.setContentsMargins(0, 0, 0, 0)

        self.path_bar = QtWidgets.QFrame()
        self.path_bar.setObjectName("bar")
        self.path_bar.setLayout(self.path_layout)

        self.layout.addWidget(self.btn_back)
        self.layout.addWidget(self.btn_frwd)
        self.layout.addWidget(self.path_bar)
        self.layout.addWidget(self.btn_pin)

        self.setLayout(self.layout)
        self.setAcceptDrops(True)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)

        self.buildPathBar(node_path="/obj")

        # connect panel signals
        self.panel.signals.copperNodeSelected[str].connect(self.nodeSelected)

    def historyGoBack(self):
        if self.history_index > 0:
            self.history_index -= 1
            #print "History back to: %s with index %s" % (self.history[self.history_index], self.history_index)
            self.btn_frwd.setEnabled(True)
            if self.history_index == 0:
                self.btn_back.setEnabled(False)

            signals.copperNodeSelected.emit(self.history[self.history_index])

    def historyGoForward(self):
        if self.history_index < (len(self.history) - 1):
            self.history_index += 1
            #print "History fwd to: %s with index %s" % (self.history[self.history_index], self.history_index)
            self.btn_back.setEnabled(True)
            if self.history_index == (len(self.history) - 1):
                self.btn_frwd.setEnabled(False)

            signals.copperNodeSelected.emit(self.history[self.history_index])

    def pinPressed(self):
        if self.pinned == False:
            self.pinned = True
        else:
            self.pinned = False

    def isPinned(self):
        return self.pinned

    @QtCore.pyqtSlot(str)
    def nodeSelected(self, node_path=None):
        if node_path == "/":
            return

        if self.buildPathBar(node_path):
            if self.history:
                if self.history[-1] == node_path:
                    return

            self.history += [node_path]
            self.history_index += 1
            #print "History added: %s at index %s" % (node_path, self.history_index)
            self.btn_back.setEnabled(True)

    def buildPathBar(self, node_path=None):
        node = engine.node(node_path)
        if not node:
            return False
        elif node.isRoot():
            btn = QtWidgets.QPushButton()
        else:
            parent = node.parent()
            if parent.isRoot():
                parent = node

            for i in reversed(range(self.path_layout.count())): 
                self.path_layout.itemAt(i).widget().deleteLater()

            btn = None

            path_nodes = parent.pathAsNodeList()

            for node in path_nodes:
                btn = QtWidgets.QPushButton()
                btn.setIcon(QtGui.QIcon(node.iconName()))
                btn.setText(node.name())
                btn.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed)

                menu = QtWidgets.QMenu()
                for child in node.parent().children():
                    menu.addAction(child.name())

                btn.setMenu(menu)

                self.path_layout.addWidget(btn)

        if btn:
            btn.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)

        return True


