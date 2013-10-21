import inspect
#import pyopencl as cl
#import numpy
from compy.engines import CLC_Engine as engine
import settings
import composition
import base

print "Loading effects..."

effects = {}

for module_name in settings.fx_modules:
	module = __import__(module_name, fromlist="*")
	for name in dir(module):
		obj = getattr(module, name)
		if inspect.isclass(obj):
			if getattr(obj,"__cfx__"):
				effects[obj.name] = obj
				print "FX filter %s loaded..." % obj		


def CreateEngine(device_type):
	return engine(device_type, effects, settings.cl_path)