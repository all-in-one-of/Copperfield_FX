import sys
import pyopencl as cl
import pickle
import numpy
import compy.network_manager as network_manager
from compy.compy_string import CompyString
from compy.translators import compyNullTranslator, boomShotTranslator
from pyopencl.tools import get_gl_sharing_context_properties
from PIL import Image

class CLC_Engine(network_manager.CLC_NetworkManager):
	cpu_devices = []
	gpu_devices = []
	programs 	= {}
	app 		= None
	filters		= {}
	network_cb  = None

	def __init__(self, device_type="GPU", filters={}, cl_path=""): # "cpu" or "gpu" here or "ALL"
		super(CLC_Engine, self).__init__(self, None, ["comp"]) # only CLC_Composition class nodes allowed to be created at the root/engine level
		self.__time__= 0
		self.__frame__= 0
		self.__fps__ = 25.0

		print "Initializing compositing engine..."
		for found_platform in cl.get_platforms():
			if found_platform.name in ['NVIDIA CUDA', 'ATI Stream', 'Apple']:
				my_platform = found_platform
			else:
				raise BaseException("Unable to found capable OpenCL device!")
		
		for found_device in my_platform.get_devices():
			if cl.device_type.to_string(found_device.type) == "GPU":
				self.gpu_devices += [found_device]
			elif cl.device_type.to_string(found_device.type) == "CPU":    
				self.cpu_devices += [found_device]
	
		if self.cpu_devices != []:
			print "Found CPU devices: %s" % self.cpu_devices        
		else:
			print "No CPU devices found"
	
		if self.gpu_devices != []:
			print "Found GPU devices: %s" % self.gpu_devices
		else:
			print "No GPU devices found"
		
		if device_type in ["gpu","GPU","Gpu"]:
			print "Creating engine using GPU devices"
			self._ctx = cl.Context(devices = self.gpu_devices)
			#self._ctx = cl.Context(properties=[
            #    (cl.context_properties.PLATFORM, cl.get_platforms()[0])]
            #    + get_gl_sharing_context_properties())
		elif device_type in ["cpu","CPU","Cpu"]:
			print "Creating engine using CPU devices"
			self._ctx = cl.Context(devices = self.cpu_devices)
		else:
			print "Creating engine using any type of device"
			self._ctx = cl.Context(devices = self.cpu_devices + self.gpu_devices)
		
		self._queue 	= cl.CommandQueue(self.ctx, properties=cl.command_queue_properties.PROFILING_ENABLE)
		self._mf 		= cl.mem_flags
		self.filters 	= filters
		self.cl_path 	= cl_path
		print "Bundled with filters: %s \n Done." % self.filters

		# register translators
		self.translators = {}
		translators = [compyNullTranslator(), boomShotTranslator() ]
		for translator in translators:
			self.translators[translator.registerExtension()] = translator

		# create base network managers
		img = network_manager.CLC_NetworkManager(self, self, ["comp"])
		img.setName("img")
		self.__node_dict__["img"] = img

		out = network_manager.CLC_NetworkManager(self, self, ["composite"])
		out.setName("out")
		self.__node_dict__["out"] = out		
	
	def set_network_change_callback(self, callback):
		self.network_cb = callback

	def call_network_changed_callback(self):
		if self.network_cb:
			print "Calling network change callback..."
			self.network_cb()	 	

	def load_program(self, filename):
		of = open("%s/%s" % (self.cl_path, filename), 'r')
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
		print "Frame %s" % frame
		self.__frame__ = frame
		self.__time__ = float(frame) / float(self.__fps__)				

	def engine(self):
		return self

	def flush(self):
		for net_name in self.__node_dict__:
			self.__node_dict__[net_name].flush()	

	def renderToFile(self, node_path, filename, frame = None):
		node = self.node(node_path)
		if frame:
			render_frame = frame
		else:
			render_frame = self.frame()

		self.setFrame(frame)	
		render_file_name = CompyString(self.engine, filename).expandedString()	
		print "Rendering frame %s for node %s to file: %s" % (render_frame, node.path(), render_file_name)
		
		buff = node.getOutHostBuffer()
		image = Image.frombuffer('RGBA', node.size, buff.astype(numpy.uint8), 'raw', 'RGBA', 0, 1)
		image.save(render_file_name, 'JPEG', quality=100)

		#file = open(render_file_name, 'w+')
		#file.close()			

	def save_project(self, filename):
		project_file = open(filename, "wb")

		# write out nodes
		node_list = []
		for node in self.nodes:
			node_list += node.dump(recursive=True, dump_parms=True)

		project_file.write("nodes = %s\n" % node_list)
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

