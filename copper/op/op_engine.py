import sys, os
import pyopencl as cl
import pickle
import numpy
from copper.op.node_type_category import ManagerNodeTypeCategory
from copper.op.op_node import OpRegistry
from copper.op.op_network import OP_Network
from copper.managers import OBJ_Network, COP_Network, ROP_Network
from copper.copper_string import CopperString
from copper.translators import CopperNullTranslator, boomShotTranslator
from pyopencl.tools import get_gl_sharing_context_properties
from PIL import Image

class Copper_Engine(OP_Network):
	__base__ = True
	programs 	= {}
	app 		= None
	filters		= {}
	network_cb  = None

	def __init__(self, device_type="GPU", device_index=None, cl_path=""): # "cpu" or "gpu" here or "ALL"
		super(Copper_Engine, self).__init__(self, None) # base node is the engine itself, therefore it has no parent
		self.__time__= 0
		self.__frame__= 0
		self.__fps__ = 25.0

		print "Initializing engine of type %s" % device_type
		devices = []
		platforms = cl.get_platforms()
		for platform in platforms:
			if device_type is "CPU":
				devices += platform.get_devices(cl.device_type.CPU)
			
			elif device_type is "GPU":
				devices += platform.get_devices(cl.device_type.GPU)
			
			elif device_type is "ALL":	 
				devices += platform.get_devices(cl.device_type.ALL)	
			
			else:
				devices = None	
			
		if devices:		
			if device_index:
				print "Creating engine selected device: %s" % devices[device_index] 
				self._ctx = cl.Context(devices = [devices[device_index]])
			else:	
				print "Creating engine using devices: %s" % devices 
				self._ctx = cl.Context(devices = devices)

			self._queue 	= cl.CommandQueue(self.ctx, properties=cl.command_queue_properties.PROFILING_ENABLE)
			self._mf 		= cl.mem_flags
			self.cl_path 	= cl_path
			self.cl_mode = True
			print "Using Open_CL."
		else:
			print "NO OPEN_CL CAPABLE DEVICE FOUND !!!"
			exit(1)		

		print "Bundled with ops: %s \n Done." % OpRegistry._registry

		# register translators
		self.translators = {}
		translators = [CopperNullTranslator(), boomShotTranslator() ]
		for translator in translators:
			self.translators[translator.registerExtension()] = translator

		# create base network managers
		self.createNode("out")
		self.createNode("img")
		self.createNode("obj")	
	
	def set_network_change_callback(self, callback):
		self.network_cb = callback

	def call_network_changed_callback(self):
		if self.network_cb:
			print "Calling network change callback..."
			self.network_cb()	 	

	def load_program(self, filename):
		of = open("%s/%s" % (os.path.expandvars(self.cl_path), filename), 'r')
		return cl.Program(self.ctx, of.read()).build()

	@property 
	def have_gl(self):
		return cl.have_gl()	

	@property
	def ctx(self):
		return self._ctx
		
	@property
	def queue(self):
		return self._queue	
		
	@property
	def mf(self):
		return self._mf

	def fps(self):
		return self.__fps__

	def time(self):
		return self.__time__

	def frame(self):
		return self.__frame__		

	def setFps(self, fps):
		self.__fps__ = fps	

	def setTime(self, time):
		self.__time__ = time
		self.__frame__ = float(time) * float(self.__fps__)

	def setFrame(self, frame):
		self.__frame__ = frame
		self.__time__ = float(frame) / float(self.__fps__)			

	@property	
	def engine(self):
		return self

	@classmethod
	def allowedChildTypeCategory(cls):
		return ManagerNodeTypeCategory.name()

	def flush(self):
		for net_name in self.__node_dict__:
			self.__node_dict__[net_name].flush()	

	def renderToFile(self, node_path, filename, frame = None):
		node = self.node(node_path)
		if frame:
			render_frame = frame
		else:
			render_frame = self.frame()

		self.setFrame(render_frame)	

		self.setFrame(frame)	
		render_file_name = CopperString(self.engine, filename).expandedString()	
		
		self.log("OpenCL. Rendering frame %s for node %s to file: %s" % (render_frame, node.path(), render_file_name))
		buff = node.getOutHostBuffer()
		image = Image.frombuffer('RGBA', node.size, buff.astype(numpy.uint8), 'raw', 'RGBA', 0, 1)			

		if "lin" in sys.platform :
			# Flip image vertically
			image = image.transpose(Image.FLIP_TOP_BOTTOM)

		image.save(render_file_name, 'JPEG', quality=100)

	def save_project(self, filename):
		project_file = open(filename, "wb")

		# write out nodes
		node_list = []
		node_links = []
		for node in self.node("/img").children() + self.node("/out").children():
			node_list += node.dump(recursive=True, dump_parms=True)
			node_links += node.dumpLinks(recursive=True)

		project_file.write("nodes = %s\n" % node_list)
		project_file.write("links = %s\n" % node_links)
		project_file.close()

	def readFile(self, file_path):
		return open(file_path, "rb").read()

	def open_project(self, filename):
		file_extension = filename.rsplit(".",1)[-1]
		translator = self.translators.get(file_extension, None)
		if not translator: raise BaseException("No translator found for file type \"%s\"" % file_extension)
		project_string = translator.translateToString(filename)
		project_code = compile(project_string, '<string>', 'exec')

		self.flush() # erase all node networks this engine holds
		ns = {}
		exec project_code in ns
		links = ns['links']
		
		# create nodes and fill parameters
		for node_desc in ns['nodes']:
			node = self.node(node_desc["path"]).createNode(node_desc["type"], node_desc["name"]) 
			if node_desc.get("parms"):
				node.setParms(node_desc["parms"])

		# set up links between nodes
		for link in ns['links']:
			from_node = self.node(link[0])
			to_node = self.node(link[1])
			input_index = link[3]
			to_node.setInput(input_index, from_node)		

		self.call_network_changed_callback()

	def test_project(self):
		#### ---- create simple scene for debug purposes
		
		## Create out composite node
		out = self.node("out")

		## Create composite output driver
		out.createNode("comp", "comp1")

		## First get image network
		img = self.node("img")
		
		## Create composition
		comp = img.createNode("img", "comp1")

		obj = self.node("obj")

		geo = obj.createNode("geo", "geo1")

		## Create file reading node 
		file1 = comp.createNode("file")
		file1.setPos(10, 10)
		file1.setParms({"width": 1280, "height": 720, "filename": "/Users/max/Desktop/773dee750c33093fd74279637db1a38b.jpg"})

		## Create blur node
		blur1 = comp.createNode("blur")
		blur1.setInput(0, file1)
		blur1.setParms({"blursize":0.01, "blursizey": 0.5, "useindepy" : True}) 

		print "Final childern %s" % [child.type() for child in comp.children()]
