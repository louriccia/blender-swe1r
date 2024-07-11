import struct
from ..utils import clamp

def readUInt8(buffer, cursor):
    return int.from_bytes(buffer[cursor: cursor+1], byteorder='big')

def readInt8(buffer, cursor):
    return int.from_bytes(buffer[cursor: cursor+1], byteorder='big', signed = True)

def readUInt16BE(buffer, cursor):
    return int.from_bytes(buffer[cursor:cursor + 2], byteorder='big')

def readInt16BE(buffer, cursor):
    return int.from_bytes(buffer[cursor:cursor + 2], byteorder='big', signed = True)

def readUInt32BE(buffer, cursor):
    return int.from_bytes(buffer[cursor:cursor + 4], byteorder='big')

def readInt32BE(buffer, cursor):
    return int.from_bytes(buffer[cursor:cursor + 4], byteorder='big', signed = True)

def readString(buffer, cursor):
    return struct.unpack_from('4s', buffer, cursor)[0].decode('utf-8', errors='replace')

def readFloatBE(buffer, cursor):
    return struct.unpack_from('>f', buffer, cursor)[0]

def readVec3(buffer, cursor):
    return struct.unpack_from('>fff', buffer, cursor)

def writeBulk(buffer, cursor, format_string, arr):
    struct.pack_into(format_string, buffer, cursor, *arr)
    return cursor + struct.calcsize(format_string)

def writeString(buffer,  string, cursor):
    struct.pack_into('>4s', buffer, cursor, string.encode('utf-8'))
    return cursor + struct.calcsize('4s')

def writeInt8(buffer, num, cursor):
    struct.pack_into('>b', buffer, cursor, num)
    return cursor + struct.calcsize('b')

def writeUInt8(buffer, num, cursor):
    struct.pack_into('>B', buffer, cursor, num)
    return cursor + struct.calcsize('B')

def writeInt16BE(buffer, num, cursor):
    struct.pack_into('>h', buffer, cursor, num)
    return cursor + struct.calcsize('h')

def writeUInt16BE(buffer, num, cursor):
    struct.pack_into('>H', buffer, cursor, num)
    return cursor + struct.calcsize('H')

def writeInt32BE(buffer, num, cursor):
    struct.pack_into('>i', buffer, cursor, num)
    return cursor + struct.calcsize('i')

def writeUInt32BE(buffer, num, cursor):
    struct.pack_into('>I', buffer, cursor, num)
    return cursor + struct.calcsize('I')

def writeFloatBE(buffer, num, cursor):
    struct.pack_into('>f', buffer, cursor, num)
    return cursor + struct.calcsize('f')

class Data:
    def get(self):
        pass
    def set(self):
        pass

class DataStruct:
    
    def __init__(self, format_string):
        self.parent = None
        self.format_string = format_string
        self.size = struct.calcsize(self.format_string)
        
    def read(self, buffer, cursor):
        self.data = struct.unpack_from(self.format_string, buffer, cursor)
        return self
    
    def make(self):
        return self.to_array()
    
    def unmake(self):
        raise NotImplementedError("Subclasses must implement this method")
    
    def write(self, buffer, cursor):
        struct.pack_into(self.format_string, buffer, cursor, *self.to_array())
        return cursor + self.size
    
    def from_array(self, data):
        self.data = data
        return self
    
    def to_array(self):
        return self.data
    
class FloatPosition(DataStruct):
    def __init__(self, data = None):
        super().__init__('>3f')
        self.data = [0,0,0]
        if data is not None:
            self.from_array(data)

    def __str__(self):
        return f"({self.data[0]}, {self.data[1]}, {self.data[2]})"
    
    def from_array(self, data=None):
        if(len(data) != 3):
            raise ValueError(f"Vec3 must contain 3 values, received {len(data)}")
        super().from_array(data)
        return self
    
    def to_array(self):
        return self.data
    
class FloatVector(FloatPosition):
    def from_array(self, data = None):
        for d in data:
            if d > 1.0 or d < -1.0:
                print(f"Vec3 {d} in {data} is not normalized")
        super().from_array(data)
        return self
    
    def to_array(self):
        return self.data

class ShortPosition(DataStruct):
    def __init__(self, data = None):
        super().__init__('>3h')
        self.data = [0,0,0]
        if data is not None:
            self.from_array(data)  
    
    def __eq__(self, other):
        return self.data == other.data
    
    def from_array(self, data=None):
        super().from_array(data)  
        self.data = [round(min(32767, max(-32768, d))) for d in self.data]
        return self
    
    def to_array(self):
        return [round(min(32767, max(-32768, c))) for c in self.data]
    
class FloatMatrix(DataStruct):
    def __init__(self, data = None):
        super().__init__('>12f')
        if data is None:
            self.data = [FloatVector(), FloatVector(), FloatVector(), FloatPosition()]
        else:
            self.from_array([FloatVector().from_array(data[:3]), FloatVector().from_array(data[3:6]), FloatVector().from_array(data[6:9]), FloatPosition().from_array(data[9:])])

    def read(self, buffer, cursor):
        super().read(buffer, cursor)
        self.from_array(self.data)
        return self

    def from_array(self, data=None):
        if(len(data) != 12):
            raise ValueError("FloatMatrix must have 12 values")
        self.data = [FloatVector().from_array(data[:3]), FloatVector().from_array(data[3:6]), FloatVector().from_array(data[6:9]), FloatPosition().from_array(data[9:])]

    def to_array(self):
        data = []
        for vec in self.data:
            data.extend(vec.to_array())
        return data
    
    def make(self, scale):
        matrix = []
        for i in range(3):
            matrix.append(tuple([*self.data[i].to_array(), 0.0]))
        matrix.append(tuple([*[a * scale for a in self.data[3].to_array()], 1.0]))
        return matrix
    
    def unmake(self, matrix, scale):
        mat = []
        for i in range(3):
            mat.extend(matrix[i][:3])
        mat.extend([a / scale for a in matrix[3][:3]])
        self.from_array(mat)  
    
    def write(self, buffer, cursor):
        struct.pack_into(self.format_string, buffer, cursor, *self.to_array())
        return cursor + self.size

class Color(Data):
    def __init__(self, data = None):
        if data is None:
            self.data = [0, 0, 0, 255]
        else:
            self.set(data)
        
    def __str__(self):
        return f"r: {self.data[0]} g: {self.data[1]} b: {self.data[2]}"
    
    def set(self, data=None):
        if(len(data) > 4 or len(data) < 3):
            raise ValueError("Color must have 3 or 4 values")
        for c in self.data:
            if c > 255:
                raise ValueError(f"Color values must be < 255, received {c}")
        if len(data) == 3:
            data.append(255)
        self.data = data
        return self
    
    def make(self):
        return [d/255 for d in self.data]
    
    def unmake(self, data):
        self.set([round(d * 255) for d in data])
    
    def get(self):
        return self.data
    
class RGB3Bytes(DataStruct):
    def __init__(self, r = 255, g = 255, b = 255):
        super().__init__('>3B')
        self.r = r
        self.g = g
        self.b = b
    
    def from_array(self, arr):
        self.r, self.g, self.b = arr
        return self

    def make(self):
        return [self.r/255, self.g/255, self.b/255]
    
    def unmake(self, data):
        self.r, self.g, self.b = [round(clamp(d*255, 0, 255)) for d in data]
        return self
    
    def to_array(self):
        return [self.r, self.g, self.b]
    
class RGBA4Bytes(DataStruct):
    def __init__(self, r = 255, g = 255, b = 255, a = 255):
        super().__init__('>4B')
        self.r = r
        self.g = g
        self.b = b
        self.a = a
    def to_array(self):
        return [self.r, self.g, self.b, self.a]
    def __eq__(self, other):
        return self.to_array() == other.to_array()
    def unmake(self, data):
        self.r = round(data[0]*255)
        self.g = round(data[1]*255)
        self.b = round(data[2]*255)
        self.a = round(data[3]*255)
        return self
