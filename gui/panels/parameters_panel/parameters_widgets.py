from PyQt4 import QtCore, QtGui

from gui.signals import signals
from copper.parm_template import ParmLookScheme, ParmNamingScheme, ParmTemplateType, StringParmType

class ParameterBaseWidget(QtGui.QWidget):
	valueChanged = QtCore.pyqtSignal()
	def __init__(self, parent, parm):
		QtGui.QWidget.__init__(self, parent)
		self.parm = parm
		self.line_edit = None # Not all type of parm widget has line edit
		self.layout = QtGui.QHBoxLayout(self)
		self.layout.setSpacing(2)
		self.layout.setContentsMargins(0, 0, 0, 0)
		self.setLayout(self.layout)

		self.valueChanged.connect(self.setParmValue)

	@QtCore.pyqtSlot()
	def setParmValue(self):
		parm_type = self.parm.parmTemplate().type()
		if parm_type is ParmTemplateType.Float:
			self.parm.set(float(self.line_edit.text()))
		elif parm_type is ParmTemplateType.Int:
			self.parm.set(int(self.line_edit.text()))
		elif parm_type is ParmTemplateType.String:
			self.parm.set(str(self.line_edit.text()))

	'''
	Handle drop event. Validate dropped data and set parameter.
	'''
	def eventFilter(self, source, event):
		if (event.type() == QtCore.QEvent.Drop and source is self.line_edit):
			if self.line_edit:
				self.line_edit.setText("")
				self.line_edit.dropEvent(event)
				if event.isAccepted():
					self.valueChanged.emit()
				return True
		return QtGui.QWidget.eventFilter(self, source, event) # propagate event


class ParameterFloatWidget(ParameterBaseWidget):
	def __init__(self, parent, parm):
		ParameterBaseWidget.__init__(self, parent, parm)
		self.resolution = 100
		self.slider = None
		self.line_edit = QtGui.QLineEdit(str(self.parm.evalAsFloat())) 
		self.line_edit.setMinimumWidth(60)
		self.layout.addWidget(self.line_edit)

		if parm.parmTemplate().numComponents() == 1:
			self.line_edit.setMaximumWidth(140)
			self.slider = QtGui.QSlider(self)
			self.slider.setValue(int(self.parm.evalAsFloat() * self.resolution))
			self.slider.setOrientation(QtCore.Qt.Horizontal)
			self.slider.setMinimum(0)
			self.slider.setMaximum(self.resolution)
			self.slider.setSingleStep(0)
			self.slider.setTracking(True)
			self.slider.valueChanged.connect(self.processSlider)
			self.layout.addWidget(self.slider)

		# connect signals
		self.line_edit.editingFinished.connect(self.processLineEdit)

	def processSlider(self):
		value = self.slider.value()
		self.line_edit.setText(str(float(value)/self.resolution))
		self.valueChanged.emit()

	def processLineEdit(self):
		value = float(self.line_edit.text())
		if self.slider: self.slider.setValue(value)
		self.valueChanged.emit()

class ParameterIntWidget(ParameterBaseWidget):
	def __init__(self, parent, parm):
		ParameterBaseWidget.__init__(self, parent, parm)
		self.slider = None
		self.line_edit = QtGui.QLineEdit(str(self.parm.evalAsInt())) 
		self.line_edit.setMinimumWidth(60)
		self.layout.addWidget(self.line_edit)

		if parm.parmTemplate().numComponents() == 1:
			self.line_edit.setMaximumWidth(140)
			self.slider = QtGui.QSlider(self)
			self.slider.setValue(self.parm.evalAsFloat())
			self.slider.setOrientation(QtCore.Qt.Horizontal)
			self.slider.setMinimum(parm.parmTemplate().min())
			self.slider.setMaximum(parm.parmTemplate().max())
			self.slider.setTracking(True)
			self.slider.setTickInterval(1)
			self.slider.setTickPosition(QtGui.QSlider.TicksBelow)
			self.slider.valueChanged.connect(self.processSlider)
			self.layout.addWidget(self.slider)

		# connect signals
		self.line_edit.editingFinished.connect(self.processLineEdit)

	def processSlider(self):
		value = self.slider.value()
		self.line_edit.setText(str(value))
		self.valueChanged.emit()

	def processLineEdit(self):
		value = int(self.line_edit.text())
		if self.slider: self.slider.setValue(value)
		self.valueChanged.emit()


class ParameterToggleWidget(ParameterBaseWidget):
	def __init__(self, parent, parm):
		ParameterBaseWidget.__init__(self, parent, parm)

		self.checkbox = QtGui.QCheckBox(self)
		self.checkbox.setCheckState(self.parm.evalAsBool())

		self.label = QtGui.QLabel(parm.parmTemplate().label())
		self.label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
		self.label.setStatusTip(parm.name())

		self.layout.addWidget(self.checkbox)
		self.layout.addWidget(self.label)
		self.layout.addStretch(1)

		# connect signals
		self.checkbox.stateChanged.connect(self.setParmValue)


class ParameterMenuWidget(ParameterBaseWidget):
	def __init__(self, parent, parm):
		ParameterBaseWidget.__init__(self, parent, parm)

		self.combobox = QtGui.QComboBox(self)
		for item_label in self.parm.menuLabels():
			self.combobox.addItem(item_label)

		self.combobox.setCurrentIndex(parm.evalAsInt())

		self.layout.addWidget(self.combobox)

		if parm.parmTemplate().numComponents() == 1:
			self.layout.addStretch(1)


class ParameterButtonWidget(ParameterBaseWidget):
	def __init__(self, parent, parm):
		ParameterBaseWidget.__init__(self, parent, parm)

		self.button = QtGui.QPushButton(parm.parmTemplate().label(), self)
		self.button.setMinimumWidth(60)

		self.layout.addWidget(self.button)
		
		if parm.parmTemplate().numComponents() == 1:
			self.button.setMaximumWidth(140)
			self.layout.addStretch(1)

		# connect signals
		self.button.clicked.connect(parm.pressButton)


class ParameterStringWidget(ParameterBaseWidget):
	def __init__(self, parent, parm):
		ParameterBaseWidget.__init__(self, parent, parm)

		self.line_edit = QtGui.QLineEdit(parm.evalAsString())
		self.line_edit.setDragEnabled(True)
		self.line_edit.setAcceptDrops(True)
		self.line_edit.installEventFilter(self) # process drag'n'drop
		self.layout.addWidget(self.line_edit)

		if parm.parmTemplate().stringType() is StringParmType.FileReference:
			self.file_button = QtGui.QToolButton(self)
			self.file_button.setObjectName("file")
			self.file_button.clicked.connect(self.BrowseFile)
			self.layout.addWidget(self.file_button)
		elif parm.parmTemplate().stringType() is StringParmType.NodeReference:
			self.op_jump_button = QtGui.QToolButton(self)
			self.op_jump_button.setObjectName("op_jump")

			self.op_path_button = QtGui.QToolButton(self)
			self.op_path_button.setObjectName("op_path")
			self.op_path_button.clicked.connect(self.BrowseOp)

			self.layout.addWidget(self.op_jump_button)
			self.layout.addWidget(self.op_path_button)	

		# connect signals
		self.line_edit.editingFinished.connect(self.setParmValue)

	def BrowseFile(self, lineEdit):
		file_name = QtGui.QFileDialog.getOpenFileName()
		self.line_edit.setText(file_name)

	def BrowseOp(self, lineEdit):
		op_path = QtGui.QFileDialog.getOpenFileName()
		self.line_edit.setText(op_path)







