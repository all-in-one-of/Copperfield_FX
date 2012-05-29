import pyopencl as cl

class CLC_Engine():
	cpu_devices = []
	gpu_devices = []
	programs = {}
		
	def __init__(self):
		print "Initializing compositing engine..."
		for found_platform in cl.get_platforms():
			if found_platform.name in ['NVIDIA CUDA', 'ATI Stream', 'Apple']:
				my_platform = found_platform
			else:
				raise BaseException("Unable to found capable OpenCL GPU")
		
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
	
		self._ctx = cl.Context(devices = self.gpu_devices, dev_type = None)
		self._queue = cl.CommandQueue(self.ctx, properties=cl.command_queue_properties.PROFILING_ENABLE)
		self._mf = cl.mem_flags
		print "Done."	
	
	def load_program(self, filename):
		of = open("cl/%s" % filename, 'r')
		return cl.Program(self.ctx, of.read()).build()	
	
	@property
	def ctx(self):
		return self._ctx
		
	@property
	def queue(self):
		return self._queue	
		
	@property
	def mf(self):
		return self._mf
