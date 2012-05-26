from PIL import Image, ImageMath
import numpy
import numpy.linalg as la
import pyopencl as cl
from scipy import misc

'''
pic = Image.open("foo.jpg")
pix = numpy.array(pic.getdata()).reshape(pic.size[0], pic.size[1], 3)
'''

class CL_RGBA_Layer():
	
	buff	= None
	width	= None	
	height	= None
		
	def __init__(self, width = None, height= None, imagefile = None, color = None):
		self.width = width
		self.height = height
				
		if imagefile:
			pic = Image.open(imagefile)
			self.width = pic.size[0]
			self.height = pic.size[1]
			temp_buff = numpy.array(pic.convert("RGB").getdata(), dtype=numpy.uint8).reshape(self.width, self.height, 3)
			self.buff = temp_buff.astype(numpy.float32) / 256
			print self.buff.dtype
		elif color:
			self.buff = numpy.empty((self.width, self.height, 3), dtype=numpy.float32)
			self.buff[:, :, 0].fill(color[0])
			self.buff[:, :, 1].fill(color[1])
			self.buff[:, :, 2].fill(color[2])
		else:
			self.buff = numpy.empty((self.height, self.width, 3), dtype=numpy.float32)	

	def normalize(self, rgb):
		for i in range(3):
			rgb[...,i]*=255
		return rgb

	def showBuffer(self):
		Image.frombuffer('RGB', (self.width, self.height), self.normalize(self.buff).astype(numpy.uint8), 'raw', 'RGB', 0, 1).show()	

class CL_Composer():
	
	source_a = None	
	source_b = None
	result	 = None 
	
	prg = None
	queue = None
	def __init__(self, source_a, source_b):
		self.source_a = source_a
		self.source_b = source_b
		self.result = numpy.empty_like(self.source_a)
		
		ctx = cl.create_some_context()
		self.queue = cl.CommandQueue(ctx)

		mf = cl.mem_flags
		self.a_buf = cl.Buffer(ctx, mf.READ_ONLY | mf.COPY_HOST_PTR, hostbuf=self.source_a)
		self.b_buf = cl.Buffer(ctx, mf.READ_ONLY | mf.COPY_HOST_PTR, hostbuf=self.source_b)
		self.dest_buf = cl.Buffer(ctx, mf.WRITE_ONLY, self.result.nbytes * 100)

		self.prg = cl.Program(ctx,
		"""
			__kernel void sum(__global const float *a,
			__global const float *b, __global float *c)
			{
			int gid = get_global_id(0);
			c[gid] = a[gid] + b[gid];
			c[gid] = 1;
			}
		"""
		).build()

	def normalize(self, rgb):
		for i in range(3):
			rgb[...,i]*=255
		return rgb

	def showResult(self):
		Image.frombuffer('RGB', (512, 512), self.normalize(self.result).astype(numpy.uint8), 'raw', 'RGB', 0, 1).show()

	def perform(self):
		self.prg.sum(self.queue, self.source_a.shape, None, self.a_buf, self.b_buf, self.dest_buf)
		cl.enqueue_copy(self.queue, self.result, self.dest_buf)


layer1 = CL_RGBA_Layer(imagefile="/Users/max/Desktop/dog.jpg")
layer2 = CL_RGBA_Layer(width=512, height=512, color=(1, 0.5, 0.1, 1))

layer1.showBuffer()
layer2.showBuffer()

comp = CL_Composer(layer1.buff, layer2.buff)
comp.perform()
comp.showResult()
