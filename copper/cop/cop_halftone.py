import pyopencl as cl
import numpy

from copper.core.op.node_type import NodeTypeBase
from copper.core.op.node_type_category import Cop2NodeTypeCategory
from copper.core.op.op_data_socket import OP_DataSocket
from copper.core.data.image_data import ImageData
from copper.cop.cop_node import CopNode

from copper.core.parameter.parm_template import *

class COP2_HalfTone(CopNode):

	class NodeType(NodeTypeBase):
		icon_name = 'COP2_press'
		type_name = 'halftone'
		category = Cop2NodeTypeCategory

	def __init__(self, engine, parent):
		super(COP2_HalfTone, self).__init__(engine, parent)
		self.program = engine.load_program("effects_halftone.cl")
		self._input_sockets = (
			OP_DataSocket(self, "input1", ImageData),
		)
		self._output_sockets = (
			OP_DataSocket(self, "output1", ImageData),
		)
		

	def parmTemplates(self):
		templates = super(COP2_HalfTone, self).parmTemplates()
		templates += [
			FloatParmTemplate(name="density", label="Density", length=1, default_value=(200,), min=10.0, max=1000.0),
			IntParmTemplate(name="quality", label="Super sampling", length=1, default_value=(2,), min=1, max=10),
			MenuParmTemplate(name='mode', label='Missing Frames', menu_items=(0,1), menu_labels=('CMYK',
 				'BW'), default_value=0),
		]
		
		return templates

	@classmethod
	def label(cls):
		return "Half Tone"

	def xRes(self):
		return self.input(0).xRes()

	def yRes(self):
		return self.input(0).yRes()
			
	def compute(self, lock, cl_context, cl_queue):
		super(COP2_HalfTone, self).compute()	
		if self.hasInputs():
			self.devOutBuffer = cl.Image(cl_context, cl.mem_flags.READ_WRITE, self.image_format, shape=self.input(0).shape())	
			self.width = self.xRes()
			self.height = self.yRes()
			exec_evt = self.program.filter(cl_queue, (self.width, self.height), None, 
				self.input(0).getCookedData(),     
				self.devOutBuffer,
				numpy.int32(self.input(0).xRes()),
				numpy.int32(self.input(0).yRes()),
				numpy.float32(self.parm("density").eval()),
				numpy.int32(self.parm("quality").eval()),
				numpy.int32(self.parm("mode").evalAsInt()),
			)
			exec_evt.wait()
		else:
			raise BaseException("No input specified !!!")
