import struct

class Data:
    def get(self):
        pass
    def set(self):
        pass

class DataStruct:
    def __init__(self, format_string):
        self.format_string = format_string
        self.size = struct.calcsize(self.format_string)
    def read(self, buffer, cursor):
        pass
    def make(self):
        pass
    def unmake(self):
        pass
    def write(self, buffer, cursor, hl, model):
        pass
    
    
class FloatVector(Data):
    def __init__(self, data):
        if data is not None:
            self.set([0,0,0])
        else:
            self.data = [0,0,0]

    def __str__(self):
        return f"({self.data[0], self.data[1], self.data[2]})"
    
    def set(self, data=None):
        if(len(data) != 3):
            raise ValueError("Vec3 must contain only 3 values")
        for d in data:
            if d > 1.0 or d < -1.0:
                raise ValueError("Vec3 is not normalized")
        self.data = data
        return self
    
    def get(self):
        return self.data

    
class Matrix(Data):
    def __init__(self, data):
        if data is None:
            self.data = [FloatVector(), FloatVector(), FloatVector()]
        else:
            self.set([FloatVector(data[:3]), FloatVector(data[3:6], FloatVector(data[6:]))])

    def set(self, data=None):
        if(len(data) != 9):
            raise ValueError("Matrix must have 9 values")
        self.data = [FloatVector(data[:3]), FloatVector(data[3:6], FloatVector(data[6:]))]

    def get(self):
        return [vec.get() for vec in self.data]

class Color(Data):
    def __init__(self, data):
        if data is None:
            self.data = [0, 0, 0]
        else:
            self.set(data)
        
    def __str__(self):
        return f"r: {self.data[0]} g: {self.data[1]} b: {self.data[2]}"
    
    def set(self, data=None):
        if(len(data) != 3):
            raise ValueError("Color must have 3 values")
        self.data = data
        return self
    
    def get(self):
        return self.data
    
class Lights(Data):
    def __init__(self):
        self.flag = 0
        self.ambient = Color()
        self.color = Color()
        self.unk1 = 0
        self.unk2 = 0
        self.pos = Pos()
        self.rot = FloatVector()
    
    def get(self):
        return [self.flag, *self.ambient.get(), *self.color.get(),self.unk1, self.unk2, *self.pos.get(), *self.rot.get()]
        
    def set(self, flag, ambient_r, ambient_g, ambient_b, color_r, color_g, color_b,unk1, unk2, x, y, z, a, b, c):
        self.flag = flag
        self.ambient = Color().set([ambient_r, ambient_g, ambient_b])
        self.color = Color().set([color_r, color_g, color_b])
        self.unk1 = unk1
        self.unk2 = unk2
        self.pos = Pos([x, y, z])
        self.rot = FloatVector([a, b, c])

class Fog(Data):
    def __init__(self):
        self.flag = 0
        self.color = Color()
        self.start = 0
        self.end = 0
    
    def get(self):
        return [self.flag, *self.color.get(), self.start, self.end]
        
    def set(self, flag, r, g, b, start, end):
        self.flag = flag
        self.color = Color().set([r, g, b])
        self.start = start
        self.end = end

class CollisionData(DataStruct):
    def __init__(self, hl):
        super().__init__('H4B3H8B6f2I2i')
        self.hl = hl
        self.unk = 0
        self.fog = Fog()
        self.lights = Lights()
        self.flags = 0
        self.unk2 = 0
        self.unload = 0
        self.load = 0

    def read(self, buffer, cursor):
        # Unpack binary data into object attributes
        data = struct.unpack_from(self.format_string, buffer, cursor)
        self.unk = data[0]
        self.fog = Fog().set(data[1:7])
        self.lights = Lights().set(data[7:22])
        self.flags, self.unk2, self.unload, self.load = data[22:]
        
    def make(self, mesh):
        return
    
    def unmake(self, mesh):
        return
    
    def write(self, buffer, cursor):
        # Pack object attributes into binary data
        return struct.pack_into(self.format_string, buffer, cursor, *[self.unk, *self.fog.get(), *self.lights.get(), self.flags, self.unk2, self.unload, self.load])
    

class CollisionVertBuffer(DataStruct):
    def __init__(self, hl, length):
        super().__init__(f'{length*3}h')
        self.hl = hl
        self.data = None

    def read(self, buffer, cursor):
        self.data = struct.unpack_from(self.format_string, buffer, cursor)

    def make(self):
        return self.data
    
    def unmake(self, mesh):
        self.data = [round(co) for vert in mesh.data.vertices for co in vert.co]
    
    def write(self, buffer, cursor):
        return struct.pack_into(self.format_string, buffer, cursor, *self.data)
    
class CollisionVertStrips(DataStruct):
    def __init__(self, hl, count):
        super().__init__(f'{count}I')
        self.hl = hl
        self.data = None

    def read(self, buffer, cursor):
        self.data = struct.unpack_from(self.format_string, buffer, cursor)

    def make(self):
        return self.data
    
    def unmake(self, mesh):
        #this doesn't stripify the mesh but it is able to recognize existing strips in the faces' vertex indices
        face_buffer = [[v for v in face.vertices] for face in mesh.data.polygons]
        last_face = face_buffer[0]
        strips = []
        strip = 3
        for i, face in enumerate(face_buffer):
            if i == 0:
                continue
            last_face = face_buffer[i-1]
            if strip % 2 == 1 and face[0] == last_face[2] and face[1] == last_face[1]:
                strip+=1
            elif strip % 2 == 0 and face[0] == last_face[0] and face[1] == last_face[2]:
                strip+=1
            else:
                strips.append(strip)
                strip = 3
            
            if i == len(face_buffer) - 1:
                strips.append(strip)
                
        self.data = strips
    
    def write(self, buffer, cursor):
        return struct.pack_into(self.format_string, buffer, cursor, *self.data)
    

def Collision(DataStruct):
    def __init__(self, hl):
        super().__init__('4_I24_HHI8_I8_H')
