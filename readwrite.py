import struct

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
    print(arr)
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


