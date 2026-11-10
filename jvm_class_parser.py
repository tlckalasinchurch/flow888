import struct
import io
import zipfile

class JavaClassParser:
    def __init__(self, data):
        self.stream = io.BytesIO(data)
        self.parse()

    def read_u1(self):
        return struct.unpack('>B', self.stream.read(1))[0]

    def read_u2(self):
        return struct.unpack('>H', self.stream.read(2))[0]

    def read_u4(self):
        return struct.unpack('>I', self.stream.read(4))[0]

    def parse(self):
        magic = self.read_u4()
        if magic != 0xCAFEBABE:
            raise ValueError(f"Invalid magic: {magic:#x}")
        self.minor_version = self.read_u2()
        self.major_version = self.read_u2()
        self.cp_count = self.read_u2()
        self.constant_pool = [None] * self.cp_count

        i = 1
        while i < self.cp_count:
            tag = self.read_u1()
            if tag == 1: # Utf8
                length = self.read_u2()
                val = self.stream.read(length).decode('utf-8', errors='replace')
                self.constant_pool[i] = ('Utf8', val)
            elif tag == 3: # Integer
                val = struct.unpack('>i', self.stream.read(4))[0]
                self.constant_pool[i] = ('Integer', val)
            elif tag == 4: # Float
                val = struct.unpack('>f', self.stream.read(4))[0]
                self.constant_pool[i] = ('Float', val)
            elif tag == 5: # Long
                val = struct.unpack('>q', self.stream.read(8))[0]
                self.constant_pool[i] = ('Long', val)
                i += 1 # 8-byte constants take two CP slots
            elif tag == 6: # Double
                val = struct.unpack('>d', self.stream.read(8))[0]
                self.constant_pool[i] = ('Double', val)
                i += 1
            elif tag == 7: # Class
                name_idx = self.read_u2()
                self.constant_pool[i] = ('Class', name_idx)
            elif tag == 8: # String
                str_idx = self.read_u2()
                self.constant_pool[i] = ('String', str_idx)
            elif tag == 9: # Fieldref
                c_idx = self.read_u2()
                nat_idx = self.read_u2()
                self.constant_pool[i] = ('Fieldref', c_idx, nat_idx)
            elif tag == 10: # Methodref
                c_idx = self.read_u2()
                nat_idx = self.read_u2()
                self.constant_pool[i] = ('Methodref', c_idx, nat_idx)
            elif tag == 11: # InterfaceMethodref
                c_idx = self.read_u2()
                nat_idx = self.read_u2()
                self.constant_pool[i] = ('InterfaceMethodref', c_idx, nat_idx)
            elif tag == 12: # NameAndType
                name_idx = self.read_u2()
                desc_idx = self.read_u2()
                self.constant_pool[i] = ('NameAndType', name_idx, desc_idx)
            elif tag == 15: # MethodHandle
                kind = self.read_u1()
                ref_idx = self.read_u2()
                self.constant_pool[i] = ('MethodHandle', kind, ref_idx)
            elif tag == 16: # MethodType
                desc_idx = self.read_u2()
                self.constant_pool[i] = ('MethodType', desc_idx)
            elif tag == 17: # Dynamic
                b_idx = self.read_u2()
                nat_idx = self.read_u2()
                self.constant_pool[i] = ('Dynamic', b_idx, nat_idx)
            elif tag == 18: # InvokeDynamic
                b_idx = self.read_u2()
                nat_idx = self.read_u2()
                self.constant_pool[i] = ('InvokeDynamic', b_idx, nat_idx)
            elif tag == 19: # Module
                name_idx = self.read_u2()
                self.constant_pool[i] = ('Module', name_idx)
            elif tag == 20: # Package
                name_idx = self.read_u2()
                self.constant_pool[i] = ('Package', name_idx)
            else:
                raise ValueError(f"Unknown CP tag: {tag} at index {i}")
            i += 1

        self.access_flags = self.read_u2()
        self.this_class_idx = self.read_u2()
        self.super_class_idx = self.read_u2()

        self.interfaces_count = self.read_u2()
        self.interfaces_idx = [self.read_u2() for _ in range(self.interfaces_count)]

        self.fields_count = self.read_u2()
        self.fields = []
        for _ in range(self.fields_count):
            af = self.read_u2()
            n_idx = self.read_u2()
            d_idx = self.read_u2()
            attr_cnt = self.read_u2()
            for _ in range(attr_cnt):
                self.read_u2()
                length = self.read_u4()
                self.stream.read(length)
            self.fields.append({
                'name': self.get_utf8(n_idx),
                'descriptor': self.get_utf8(d_idx),
                'access_flags': af
            })

        self.methods_count = self.read_u2()
        self.methods = []
        for _ in range(self.methods_count):
            af = self.read_u2()
            n_idx = self.read_u2()
            d_idx = self.read_u2()
            attr_cnt = self.read_u2()
            for _ in range(attr_cnt):
                self.read_u2()
                length = self.read_u4()
                self.stream.read(length)
            self.methods.append({
                'name': self.get_utf8(n_idx),
                'descriptor': self.get_utf8(d_idx),
                'access_flags': af
            })

    def get_utf8(self, idx):
        if idx == 0 or idx >= len(self.constant_pool) or self.constant_pool[idx] is None:
            return ""
        tag = self.constant_pool[idx][0]
        if tag == 'Utf8':
            return self.constant_pool[idx][1]
        elif tag == 'Class':
            return self.get_utf8(self.constant_pool[idx][1])
        elif tag == 'String':
            return self.get_utf8(self.constant_pool[idx][1])
        return ""

    def get_class_name(self, idx):
        if idx == 0 or idx >= len(self.constant_pool) or self.constant_pool[idx] is None:
            return ""
        return self.get_utf8(self.constant_pool[idx][1])

    @property
    def this_class_name(self):
        return self.get_class_name(self.this_class_idx)

    @property
    def super_class_name(self):
        return self.get_class_name(self.super_class_idx)

    @property
    def interface_names(self):
        return [self.get_class_name(i) for i in self.interfaces_idx]

    def get_strings(self):
        res = []
        for item in self.constant_pool:
            if item and item[0] == 'String':
                res.append(self.get_utf8(item[1]))
        return res

    def get_method_refs(self):
        res = []
        for item in self.constant_pool:
            if item and item[0] in ('Methodref', 'InterfaceMethodref'):
                c_idx, nat_idx = item[1], item[2]
                cls = self.get_class_name(c_idx)
                if nat_idx < len(self.constant_pool) and self.constant_pool[nat_idx]:
                    n_idx, d_idx = self.constant_pool[nat_idx][1], self.constant_pool[nat_idx][2]
                    name = self.get_utf8(n_idx)
                    desc = self.get_utf8(d_idx)
                    res.append((cls, name, desc))
        return res

    def get_field_refs(self):
        res = []
        for item in self.constant_pool:
            if item and item[0] == 'Fieldref':
                c_idx, nat_idx = item[1], item[2]
                cls = self.get_class_name(c_idx)
                if nat_idx < len(self.constant_pool) and self.constant_pool[nat_idx]:
                    n_idx, d_idx = self.constant_pool[nat_idx][1], self.constant_pool[nat_idx][2]
                    name = self.get_utf8(n_idx)
                    desc = self.get_utf8(d_idx)
                    res.append((cls, name, desc))
        return res

if __name__ == '__main__':
    jar_path = r"C:\Users\Administrator\Desktop\mixing-station-pc-windows-3-2-2-789\app\installed\mixing-station-pc\app\mixing-station-desktop.jar"
    with zipfile.ZipFile(jar_path, 'r') as z:
        data = z.read("org/devcore/mixingstation/gdx/desktop/MsDesktopLauncher.class")
        parser = JavaClassParser(data)
        print("This class:", parser.this_class_name)
        print("Super class:", parser.super_class_name)
        print("Interfaces:", parser.interface_names)
        print("Fields:")
        for f in parser.fields:
            print(" ", f)
        print("Methods:")
        for m in parser.methods:
            print(" ", m)
        print("Strings referenced:")
        for s in parser.get_strings():
            print("  [str]", repr(s))
        print("Method calls referenced:")
        for ref in parser.get_method_refs()[:30]:
            print("  [call]", ref)
