from PyQt4 import QtGui, QtCore

class TimeLine(QtGui.QWidget):
    cursor = 0.0

    def __init__(self, parent=None):      
        super(TimeLine, self).__init__(parent)
        self.isPressed = False
        self.initUI()
        
    def initUI(self):
        #self.setFixedHeight(30)
        self.value = 175
        self.num = [75, 150, 225, 300, 375, 450, 525, 600, 675]

    def setValue(self, value):
        self.value = value


    def paintEvent(self, e):
        qp = QtGui.QPainter()
        qp.begin(self)
        self.drawWidget(qp)
        qp.end()
      
      
    def drawWidget(self, qp):
        font = QtGui.QFont('Arial', 8, QtGui.QFont.Light)
        qp.setFont(font)

        size = self.size()
        w = size.width()
        h = size.height()

        step = int(round(w / 10.0))

        till = int(((w / 750.0) * self.value))
        full = int(((w / 750.0) * 700))

        if self.value >= 700:
        
            qp.setPen(QtGui.QColor(255, 255, 255))
            qp.setBrush(QtGui.QColor(255, 255, 184))
            qp.drawRect(0, 0, full, h)
            qp.setPen(QtGui.QColor(255, 175, 175))
            qp.setBrush(QtGui.QColor(255, 175, 175))
            qp.drawRect(full, 0, till-full, h)
            
        else:
            qp.setPen(QtGui.QColor(255, 255, 255))
            qp.setBrush(QtGui.QColor(255, 255, 184))
            qp.drawRect(0, 0, till, h)


        pen = QtGui.QPen(QtGui.QColor(20, 20, 20), 1, 
            QtCore.Qt.SolidLine)
            
        qp.setPen(pen)
        qp.setBrush(QtCore.Qt.NoBrush)
        qp.drawRect(0, 0, w-1, h-1)

        j = 0

        #draw frames
        for i in range(step, 10*step, step):
            qp.drawLine(i, 0, i, 5)
            metrics = qp.fontMetrics()
            fw = metrics.width(str(self.num[j]))
            qp.drawText(i-fw/2, h/2, str(self.num[j]))
            j += 1

    def mousePressEvent(self, e):
        self.isPressed = True

    def mouseReleaseEvent(self, e):
        self.isPressed = False    


class TimelineWidget(QtGui.QWidget):
    in_frame = 0
    out_frame = 250
    cursor = 0.0

    def __init__(self, parent=None):      
        super(TimelineWidget, self).__init__(parent)
        self.isPressed = False
        self.setStyleSheet("background-color: rgb(164, 164, 164); border:1px solid rgb(128, 128, 128); border-radius: 1px;")
        self.initUI()
        
    def initUI(self):
        self.setFixedHeight(30)
        
        # Left buttons
        buttons_box = QtGui.QHBoxLayout()
        buttons_box.setContentsMargins(0, 0, 0, 0)
        buttons_box.setSpacing(2)
        
        prev_key_btn = QtGui.QToolButton()
        prev_key_btn.setIcon(QtGui.QIcon('icons/glyphicons_170_step_backward.png'))
        prev_key_btn.setIconSize(QtCore.QSize(24,24))
        prev_key_btn.setStatusTip('Step back one frame')

        play_btn = QtGui.QToolButton()
        play_btn.setIcon(QtGui.QIcon('icons/glyphicons_173_play.png'))
        play_btn.setIconSize(QtCore.QSize(24,24))
        play_btn.setStatusTip('Play')

        next_key_btn = QtGui.QToolButton()
        next_key_btn.setIcon(QtGui.QIcon('icons/glyphicons_178_step_forward.png'))
        next_key_btn.setIconSize(QtCore.QSize(24,24))
        next_key_btn.setStatusTip('Step forward one frame')

        buttons_box.addWidget(prev_key_btn)
        buttons_box.addWidget(play_btn)
        buttons_box.addWidget(next_key_btn)

        # Time line
        timelinebox = QtGui.QHBoxLayout()
        timeline = TimeLine(self)
        timelinebox.addWidget(timeline)

        # Set main layout
        hbox = QtGui.QHBoxLayout()
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.addLayout(buttons_box)
        hbox.addLayout(timelinebox)

        self.setLayout(hbox)       