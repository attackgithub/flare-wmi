# TODO:
#   what is "DYNPROPS: True"?
#   where do descriptions come from?
#   how to determine start of TOC in class instance?
# BUGs:
#   class instance: "root\\CIMV2" Microsoft_BDD_Info NS_68577372C66A7B20658487FBD959AA154EF54B5F935DCC5663E9228B44322805/CI_6FCB95E1CB11D0950DA7AE40A94D774F02DCD34701D9645E00AB9444DBCF640B/IL_EEC4121F2A07B61ABA16414812AA9AFC39AB0A136360A5ACE2240DC19B0464EB.1606.116085.3740

import logging
import traceback
import functools
from datetime import datetime
from collections import namedtuple

from funcy.objects import cached_property
import vstruct
from vstruct.primitives import *

from .common import h
from .common import one
from .common import LoggingObject
from .cim import Key
from .cim import Index
from .cim import CIM_TYPE_XP
from .cim import CIM_TYPE_WIN7

# TODO: remove this from the top level
logging.basicConfig(level=logging.DEBUG)
g_logger = logging.getLogger("cim.objects")


ROOT_NAMESPACE_NAME = "root"
SYSTEM_NAMESPACE_NAME = "__SystemClass"
NAMESPACE_CLASS_NAME = "__namespace"


class FILETIME(vstruct.primitives.v_prim):
    _vs_builder = True
    def __init__(self):
        vstruct.primitives.v_prim.__init__(self)
        self._vs_length = 8
        self._vs_value = "\x00" * 8
        self._vs_fmt = "<Q"
        self._ts = datetime.min

    def vsParse(self, fbytes, offset=0):
        offend = offset + self._vs_length
        q = struct.unpack("<Q", fbytes[offset:offend])[0]
        try:
            self._ts = datetime.utcfromtimestamp(float(q) * 1e-7 - 11644473600 )
        except ValueError:
            self._ts = datetime.min
        return offend

    def vsEmit(self):
        raise NotImplementedError()

    def vsSetValue(self, guidstr):
        raise NotImplementedError()

    def vsGetValue(self):
        return self._ts

    def __repr__(self):
        return self._ts.isoformat("T") + "Z"


class WMIString(vstruct.VStruct):
    def __init__(self):
        vstruct.VStruct.__init__(self)
        self.zero = v_uint8()
        self.s = v_zstr()

    def __repr__(self):
        return repr(self.s)

    def vsGetValue(self):
        return self.s.vsGetValue()



comment = """

enum VARENUM {  VT_EMPTY             = 0,
  VT_NULL              = 1,
  VT_I2                = 2,
  VT_I4                = 3,
  VT_R4                = 4,
  VT_R8                = 5,
  VT_CY                = 6,
  VT_DATE              = 7,
  VT_BSTR              = 8,
  VT_DISPATCH          = 9,
  VT_ERROR             = 10,
  VT_BOOL              = 11,
  VT_VARIANT           = 12,
  VT_UNKNOWN           = 13,
  VT_DECIMAL           = 14,
  VT_I1                = 16,
  VT_UI1               = 17,
  VT_UI2               = 18,
  VT_UI4               = 19,
  VT_I8                = 20,
  VT_UI8               = 21,
  VT_INT               = 22,
  VT_UINT              = 23,
  VT_VOID              = 24,
  VT_HRESULT           = 25,
  VT_PTR               = 26,
  VT_SAFEARRAY         = 27,
  VT_CARRAY            = 28,
  VT_USERDEFINED       = 29,
  VT_LPSTR             = 30,
  VT_LPWSTR            = 31,
  VT_RECORD            = 36,
  VT_INT_PTR           = 37,
  VT_UINT_PTR          = 38,
  VT_FILETIME          = 64,
  VT_BLOB              = 65,
  VT_STREAM            = 66,
  VT_STORAGE           = 67,
  VT_STREAMED_OBJECT   = 68,
  VT_STORED_OBJECT     = 69,
  VT_BLOB_OBJECT       = 70,
  VT_CF                = 71,
  VT_CLSID             = 72,
  VT_VERSIONED_STREAM  = 73,
  VT_BSTR_BLOB         = 0xfff,
  VT_VECTOR            = 0x1000,
  VT_ARRAY             = 0x2000,
  VT_BYREF             = 0x4000
};
"""

CIM_TYPES = v_enum()
CIM_TYPES.CIM_TYPE_LANGID = 0x3
CIM_TYPES.CIM_TYPE_REAL32 = 0x4
CIM_TYPES.CIM_TYPE_STRING = 0x8
CIM_TYPES.CIM_TYPE_BOOLEAN = 0xB
CIM_TYPES.CIM_TYPE_UINT8 = 0x11
CIM_TYPES.CIM_TYPE_UINT16 = 0x12
CIM_TYPES.CIM_TYPE_UINT32= 0x13
CIM_TYPES.CIM_TYPE_UINT64 = 0x15
CIM_TYPES.CIM_TYPE_REFERENCE = 0x66
CIM_TYPES.CIM_TYPE_DATETIME = 0x65

CIM_TYPE_SIZES = {
    CIM_TYPES.CIM_TYPE_LANGID: 4,
    CIM_TYPES.CIM_TYPE_REAL32: 4,
    CIM_TYPES.CIM_TYPE_STRING: 4,
    CIM_TYPES.CIM_TYPE_BOOLEAN: 2,
    CIM_TYPES.CIM_TYPE_UINT8: 1,
    CIM_TYPES.CIM_TYPE_UINT16: 2,
    CIM_TYPES.CIM_TYPE_UINT32: 4,
    CIM_TYPES.CIM_TYPE_UINT64: 8,
    # looks like: stringref to "\x00 00000000000030.000000:000"
    CIM_TYPES.CIM_TYPE_DATETIME: 4,
    CIM_TYPES.CIM_TYPE_REFERENCE: 4,
}


class BaseType(object):
    """
    this acts like a CimType, but its not backed by some bytes,
      and is used to represent a type.
    probably not often used. good example is an array CimType
      that needs to pass along info on the type of each item.
      each item is not an array, but has the type of the array.
    needs to adhere to CimType interface.
    """
    def __init__(self, type_, value_parser):
        self._type = type_
        self._value_parser = value_parser

    @property
    def type(self):
        return self._type

    @property
    def is_array(self):
        return False

    @property
    def value_parser(self):
        return self._value_parser

    def __repr__(self):
        return CIM_TYPES.vsReverseMapping(self._type)

    @property
    def base_type_clone(self):
        return self


ARRAY_STATES = v_enum()
ARRAY_STATES.NOT_ARRAY = 0x0
ARRAY_STATES.ARRAY = 0x20


BOOLEAN_STATES = v_enum()
BOOLEAN_STATES.FALSE = 0x0
BOOLEAN_STATES.TRUE = 0xFFFF


class CimType(vstruct.VStruct):
    def __init__(self):
        vstruct.VStruct.__init__(self)
        self.type = v_uint8(enum=CIM_TYPES)
        self.array_state = v_uint8(enum=ARRAY_STATES)
        self.unk0 = v_uint8()
        self.unk2 = v_uint8()

    @property
    def is_array(self):
        # TODO: this is probably a bit-flag
        return self.array_state == ARRAY_STATES.ARRAY

    @property
    def value_parser(self):
        if self.is_array:
            return v_uint32
        elif self.type == CIM_TYPES.CIM_TYPE_LANGID:
            return v_uint32
        elif self.type == CIM_TYPES.CIM_TYPE_REAL32:
            return v_float
        elif self.type == CIM_TYPES.CIM_TYPE_STRING:
            return v_uint32
        elif self.type == CIM_TYPES.CIM_TYPE_BOOLEAN:
            return functools.partial(v_uint16, enum=BOOLEAN_STATES)
        elif self.type == CIM_TYPES.CIM_TYPE_UINT8:
            return v_uint8
        elif self.type == CIM_TYPES.CIM_TYPE_UINT16:
            return v_uint16
        elif self.type == CIM_TYPES.CIM_TYPE_UINT32:
            return v_uint32
        elif self.type == CIM_TYPES.CIM_TYPE_UINT64:
            return v_uint64
        elif self.type == CIM_TYPES.CIM_TYPE_DATETIME:
            return v_uint32
        elif self.type == CIM_TYPES.CIM_TYPE_REFERENCE:
            return v_uint32
        else:
            raise RuntimeError("unknown qualifier type: %s", h(self.type))

    def __repr__(self):
        r = ""
        if self.is_array:
            r += "arrayref to "
        r += CIM_TYPES.vsReverseMapping(self.type)
        return r

    @property
    def base_type_clone(self):
        return BaseType(self.type, self.value_parser)


class CimTypeArray(vstruct.VStruct, LoggingObject):
    def __init__(self, cim_type):
        vstruct.VStruct.__init__(self)
        LoggingObject.__init__(self)
        self._type = cim_type
        self.count = v_uint32()
        self.elements = vstruct.VArray()

    def pcb_count(self):
        self.elements.vsAddElements(self.count, self._type)


BUILTIN_QUALIFIERS = v_enum()
BUILTIN_QUALIFIERS.PROP_QUALIFIER_KEY = 0x1
BUILTIN_QUALIFIERS.PROP_QUALIFIER_READ_ACCESS = 0x3
BUILTIN_QUALIFIERS.CLASS_QUALIFIER_PROVIDER = 0x6
BUILTIN_QUALIFIERS.CLASS_QUALIFIER_DYNAMIC = 0x7
BUILTIN_QUALIFIERS.PROP_QUALIFIER_TYPE = 0xA

BUILTIN_PROPERTIES = v_enum()
BUILTIN_PROPERTIES.PRIMARY_KEY = 0x1
BUILTIN_PROPERTIES.READ = 0x3
BUILTIN_PROPERTIES.WRITE = 0x4
BUILTIN_PROPERTIES.VOLATILE = 0x5
BUILTIN_PROPERTIES.PROVIDER = 0x6
BUILTIN_PROPERTIES.DYNAMIC = 0x7
BUILTIN_PROPERTIES.TYPE = 0xA


class QualifierReference(vstruct.VStruct):
    # ref:4 + unk0:1 + valueType:4 = 9
    MIN_SIZE = 9

    def __init__(self):
        vstruct.VStruct.__init__(self)
        self.key_reference = v_uint32()
        self.unk0 = v_uint8()
        self.value_type = CimType()
        self.value = v_bytes(size=0)

    def pcb_value_type(self):
        P = self.value_type.value_parser
        self.vsSetField("value", P())

    @property
    def is_builtin_key(self):
        return self.key_reference & 0x80000000 > 0

    @property
    def key(self):
        return self.key_reference & 0x7FFFFFFF

    def __repr__(self):
        return "QualifierReference(type: {:s}, isBuiltinKey: {:b}, keyref: {:s})".format(
                str(self.value_type),
                self.is_builtin_key,
                h(self.key)
            )


class QualifiersList(vstruct.VStruct):
    def __init__(self):
        vstruct.VStruct.__init__(self)
        self.count = 0
        self.size = v_uint32()
        self.qualifiers = vstruct.VArray()

    def vsParse(self, bytez, offset=0, fast=False):
        soffset = offset
        offset = self["size"].vsParse(bytez, offset=offset)
        eoffset = soffset + self.size

        self.count = 0
        while offset + QualifierReference.MIN_SIZE <= eoffset:
            q = QualifierReference()
            offset = q.vsParse(bytez, offset=offset)
            self.qualifiers.vsAddElement(q)
            self.count += 1
        return offset

    def vsParseFd(self, fd):
        raise NotImplementedError()


class _ClassDefinitionProperty(vstruct.VStruct):
    """
    this is the on-disk property definition structure
    """
    def __init__(self):
        vstruct.VStruct.__init__(self)
        self.type = CimType()  # the on-disk type for this property's value
        self.index = v_uint16()  # the on-disk order for this property
        self.offset = v_uint32()
        self.level = v_uint32()
        self.qualifiers = QualifiersList()


class ClassDefinitionProperty(LoggingObject):
    """
    this is the logical property object parsed from a standalone class definition.
    it is not aware of default values and inheritance behavior.
    """
    def __init__(self, class_def, propref):
        super(ClassDefinitionProperty, self).__init__()
        self._class_definition = class_def
        self._propref = propref

        # this is the raw struct, without references/strings resolved
        self._prop = _ClassDefinitionProperty()
        property_offset = self._propref.offset_property_struct
        self._prop.vsParse(self._class_definition.property_data.data, offset=property_offset)

    def __repr__(self):
        return "Property(name: {:s}, type: {:s}, qualifiers: {:s})".format(
            self.name,
            CIM_TYPES.vsReverseMapping(self.type.type),
            ",".join("%s=%s" % (k, str(v)) for k, v in self.qualifiers.items()))

    @property
    def name(self):
        # TODO: don't reach
        if self._propref.is_builtin_property:
            return self._propref.builtin_property_name
        else:
            return self._class_definition.property_data.get_string(self._propref.offset_property_name)

    @property
    def type(self):
        return self._prop.type

    @property
    def index(self):
        return self._prop.index

    @property
    def offset(self):
        return self._prop.offset

    @property
    def level(self):
        return self._prop.level

    @property
    def qualifiers(self):
        """ get dict of str to str """
        # TODO: remove duplication
        ret = {}
        for i in range(self._prop.qualifiers.count):
            q = self._prop.qualifiers.qualifiers[i]
            # TODO: don't reach
            qk = self._class_definition.property_data.get_qualifier_key(q)
            qv = self._class_definition.property_data.get_qualifier_value(q)
            ret[str(qk)] = qv
        return ret


class PropertyReference(vstruct.VStruct):
    def __init__(self):
        vstruct.VStruct.__init__(self)
        self.offset_property_name = v_uint32()
        self.offset_property_struct = v_uint32()

    @property
    def is_builtin_property(self):
        return self.offset_property_name & 0x80000000 > 0

    @property
    def builtin_property_name(self):
        if not self.is_builtin_property:
            raise RuntimeError("property is not builtin")
        key = self.offset_property_name & 0x7FFFFFFF
        return BUILTIN_PROPERTIES.vsReverseMapping(key)

    def __repr__(self):
       if self.is_builtin_property:
            return "PropertyReference(isBuiltinKey: true, name: {:s}, structref: {:s})".format(
                self.builtin_property_name,
                h(self.offset_property_struct))
       else:
            return "PropertyReference(isBuiltinKey: false, nameref: {:s}, structref: {:s})".format(
                h(self.offset_property_name),
                h(self.offset_property_struct))
 

class PropertyReferenceList(vstruct.VStruct):
    def __init__(self):
        vstruct.VStruct.__init__(self)
        self.count = v_uint32()
        self.refs = vstruct.VArray()

    def pcb_count(self):
        self.refs.vsAddElements(self.count, PropertyReference)


# TODO: remove and prefer DataRegion
class ClassFieldGetter(LoggingObject):
    """ fetches values from ClassDefinition, ClassInstance """
    def __init__(self, buf):
        """ :type buf: v_bytes """
        super(ClassFieldGetter, self).__init__()
        self._buf = buf

    def get_string(self, ref):
        s = WMIString()
        s.vsParse(self._buf, offset=int(ref))
        return str(s.s)

    def get_array(self, ref, item_type):
        Parser = item_type.value_parser
        data = self._buf

        arraySize = v_uint32()
        arraySize.vsParse(data, offset=int(ref))

        items = []
        offset = ref + 4  # sizeof(array_size:uint32_t)
        for i in range(arraySize):
            p = Parser()
            p.vsParse(data, offset=offset)
            items.append(self.get_value(p, item_type))
            offset += len(p)
        return items

    def get_value(self, value, value_type):
        """
        value: is a parsed value, might need dereferencing
        value_type: is a CimType
        """
        if value_type.is_array:
            return self.get_array(value, value_type.base_type_clone)

        t = value_type.type
        if t == CIM_TYPES.CIM_TYPE_STRING:
            return self.get_string(value)
        elif t == CIM_TYPES.CIM_TYPE_BOOLEAN:
            return value != 0
        elif t == CIM_TYPES.CIM_TYPE_DATETIME:
            return self.get_string(value)
        elif CIM_TYPES.vsReverseMapping(t):
            return value
        else:
            raise RuntimeError("unknown type: %s", str(value_type))

    def get_qualifier_value(self, qualifier):
        return self.get_value(qualifier.value, qualifier.value_type)

    def get_qualifier_key(self, qualifier):
        if qualifier.is_builtin_key:
            return BUILTIN_QUALIFIERS.vsReverseMapping(qualifier.key)
        return self.get_string(qualifier.key)


class ClassDefinitionHeader(vstruct.VStruct):
    def __init__(self):
        vstruct.VStruct.__init__(self)
        self.super_class_unicode_length = v_uint32()
        self.super_class_unicode = v_wstr(size=0)  # not present if no superclass
        self.timestamp = FILETIME()
        self.data_length = v_uint32()  # size of data from this point forwards
        self.unk1 = v_uint8()
        self.offset_class_name = v_uint32()
        self.property_default_values_length = v_uint32()
        self.super_class_ascii_length = v_uint32()  # len(super class ascii string) + 8
        self.super_class_ascii = WMIString()  # not present if no superclass
        self.super_class_ascii_length2 = v_uint32()  # not present if no superclass, length of super class ascii string

    def pcb_super_class_unicode_length(self):
        self["super_class_unicode"].vsSetLength(self.super_class_unicode_length * 2)

    def pcb_super_class_ascii_length(self):
        if self.super_class_ascii_length == 0x4:
            self.vsSetField("super_class_ascii", v_str(size=0))
            self.vsSetField("super_class_ascii_length2", v_str(size=0))


PropertyDefaultsState = namedtuple("PropertyDefaultsState", ["is_inherited", "has_default_value"])


def compute_property_state_length(num_properties):
    """
    get number of bytes required to describe state of a bunch of properties.
    two bits per property, rounded up to the nearest byte.
    :rtype: int
    """
    required_bits = 2 * num_properties
    if required_bits % 8 == 0:
        delta_to_nearest_byte = 0
    else:
        delta_to_nearest_byte = 8 - (required_bits % 8)
    total_bits = required_bits + delta_to_nearest_byte
    total_bytes = total_bits // 8
    return total_bytes


class PropertyDefaultValues(vstruct.VArray):
    # two bits per property, rounded up to the nearest byte
    def __init__(self, properties):
        vstruct.VArray.__init__(self)
        self._properties = properties

        self.state = vstruct.VArray()
        total_bytes = compute_property_state_length(len(self._properties))
        self.state.vsAddElements(total_bytes, v_uint8)

        self.default_values_toc = vstruct.VArray()
        for prop in self._properties:
            P = prop.type.value_parser
            self.default_values_toc.vsAddElement(P())

    def get_state_by_index(self, prop_index):
        if prop_index > len(self._properties):
            raise RuntimeError("invalid prop_index")

        state_index = prop_index // 4
        byte_of_state = self.state[state_index]
        rotations = prop_index % 4
        state_flags = (byte_of_state >> (2 * rotations)) & 0x3
        return PropertyDefaultsState(state_flags & 0b10 == 1, state_flags & 0b01 == 0)


class DataRegion(vstruct.VStruct, LoggingObject):
    """
    size field, then variable length of binary data.
    provides accessors for common types.
    """
    def __init__(self):
        vstruct.VStruct.__init__(self)
        LoggingObject.__init__(self)

        self._size = v_uint32()
        self.data = v_bytes(size=0)

    def pcb__size(self):
        self["data"].vsSetLength(self.size)

    @property
    def size(self):
        return self._size & 0x7FFFFFFF

    def pcb_size(self):
        self["data"].vsSetLength(self.size)

    def get_string(self, ref):
        s = WMIString()
        s.vsParse(self.data, offset=int(ref))
        return str(s.s)

    def get_array(self, ref, item_type):
        Parser = item_type.value_parser
        data = self.data

        arraySize = v_uint32()
        arraySize.vsParse(data, offset=int(ref))

        items = []
        offset = ref + 4  # sizeof(array_size:uint32_t)
        for i in range(arraySize):
            p = Parser()
            p.vsParse(data, offset=offset)
            items.append(self.get_value(p, item_type))
            offset += len(p)
        return items

    def get_value(self, value, value_type):
        """
        value: is a parsed value, might need dereferencing
        value_type: is a CimType
        """
        if value_type.is_array:
            return self.get_array(value, value_type.base_type_clone)

        t = value_type.type
        if t == CIM_TYPES.CIM_TYPE_STRING:
            return self.get_string(value)
        elif t == CIM_TYPES.CIM_TYPE_BOOLEAN:
            return value != 0
        elif t == CIM_TYPES.CIM_TYPE_DATETIME:
            return self.get_string(value)
        elif CIM_TYPES.vsReverseMapping(t):
            return value
        else:
            raise RuntimeError("unknown type: %s", str(value_type))

    def get_qualifier_value(self, qualifier):
        return self.get_value(qualifier.value, qualifier.value_type)

    def get_qualifier_key(self, qualifier):
        if qualifier.is_builtin_key:
            return BUILTIN_QUALIFIERS.vsReverseMapping(qualifier.key)
        return self.get_string(qualifier.key)


class ClassDefinition(vstruct.VStruct, LoggingObject):
    def __init__(self):
        vstruct.VStruct.__init__(self)
        LoggingObject.__init__(self)

        self.header = ClassDefinitionHeader()
        self.qualifiers_list = QualifiersList()
        self.property_references = PropertyReferenceList()
        # useful with the PropertyDefaultValues structure, but that requires
        #  a complete list of properties from the ClassLayout
        self.property_default_values_data = v_bytes(size=0)
        self.property_data = DataRegion()
        self.method_data = DataRegion()

    def pcb_property_references(self):
        self["property_default_values_data"].vsSetLength(self.header.property_default_values_length)
        # TODO: add fields

    def __repr__(self):
        # TODO: fixme
        return "ClassDefinition(name: {:s})".format(self.class_name)

    @property
    def keys(self):
        """
        get names of Key properties for instances

        :rtype: str
        """
        ret = []
        for propname, prop in self.properties.items():
            for k, v in prop.qualifiers.items():
                # TODO: don't hardcode BUILTIN_QUALIFIERS.PROP_KEY symbol name
                if k == "PROP_KEY" and v == True:
                    ret.append(propname)
        return ret

    @property
    def class_name(self):
        """ :rtype: str """
        return self.property_data.get_string(self.header.offset_class_name)

    @property
    def super_class_name(self):
        """ :rtype: str """
        return str(self.header.super_class_unicode)

    @property
    def timestamp(self):
        """ :rtype: datetime.datetime """
        return self.header.timestamp

    @cached_property
    def qualifiers(self):
        """ :rtype: Mapping[str, Variant]"""
        ret = {}
        qualrefs = self.qualifiers_list
        for i in range(qualrefs.count):
            q = qualrefs.qualifiers[i]
            qk = self.property_data.get_qualifier_key(q)
            qv = self.property_data.get_qualifier_value(q)
            ret[str(qk)] = qv
        return ret

    # TODO: cached_property
    @property
    def properties(self):
        """
        Get the Properties specific to this Class Definition.
        That is, don't return Properties inherited from ancestors.
        Note, you can't compute default values using only this field, since
          the complete class layout is required.

        :rtype: Mapping[str, ClassDefinitionProperty]
        """
        ret = {}
        proprefs = self.property_references
        for i in range(proprefs.count):
            propref = proprefs.refs[i]
            prop = ClassDefinitionProperty(self, propref)
            ret[prop.name] = prop
        return ret


class InstanceKey(object):
    """ the key that uniquely identifies an instance """
    def __init__(self):
        object.__setattr__(self, '_d', {})

    def __setattr__(self, key, value):
        self._d[key] = value

    def __getattr__(self, item):
        return self._d[item]

    def __setitem__(self, key, item):
        self._d[key] = item

    def __getitem__(self, item):
        return self._d[item]

    def __repr__(self):
        return "InstanceKey({:s})".format(str(self._d))

    def __str__(self):
        return ",".join(["{:s}={:s}".format(str(k), str(self[k])) for k in sorted(self._d.keys())])


class ClassInstance(vstruct.VStruct, LoggingObject):
    def __init__(self, cim_type, class_layout):
        vstruct.VStruct.__init__(self)
        LoggingObject.__init__(self)

        self._cim_type = cim_type
        self.class_layout = class_layout

        if self._cim_type == CIM_TYPE_XP:
            self.name_hash = v_wstr(size=0x20)
        elif self._cim_type == CIM_TYPE_WIN7:
            self.name_hash = v_wstr(size=0x40)
        else:
            raise RuntimeError("Unexpected CIM type: " + str(self._cim_type))

        self.ts1 = FILETIME()
        self.ts2 = FILETIME()
        self.data_length2 = v_uint32()  # length of entire instance data
        self.offset_instance_class_name = v_uint32()
        self.unk0 = v_uint8()
        property_state_length = compute_property_state_length(len(self.class_layout.properties))
        self.property_state_data = v_bytes(size=property_state_length)

        self.toc = vstruct.VArray()
        for prop in self.class_layout.properties:
            P = prop.type.value_parser
            self.toc.vsAddElement(P())

        self.qualifiers_list = QualifiersList()
        self.unk1 = v_uint8()
        self.data_length = v_uint32()  # high bit always set, length of variable data
        self.data = v_bytes(size=0)

        self._property_index_map = {prop.name: i for i, prop in enumerate(self.class_layout.properties)}
        self._property_type_map = {prop.name: prop.type for prop in self.class_layout.properties}

        self._fields = ClassFieldGetter(self.data)

    def pcb_data_length(self):
        self["data"].vsSetLength(self.data_length & 0x7FFFFFFF)

    def pcb_unk1(self):
        if self.unk1 != 0x1:
            # seems that when this field is 0x0, then there is additional property data
            # maybe this is DYNPROPS: True???
            raise NotImplementedError("ClassInstance.unk1 != 0x1: %s" % h(self.unk1))

    def __repr__(self):
        # TODO: make this nice
        return "ClassInstance(classhash: {:s}, key: {:s})".format(self.name_hash, self.key)

    @property
    def class_name(self):
        return self._fields.get_string(0x0)

    @cached_property
    def qualifiers(self):
        """ get dict of str to str """
        # TODO: remove duplication
        ret = {}
        for i in range(self.qualifiers_list.count):
            q = self.qualifiers_list.qualifiers[i]
            qk = self._fields.get_qualifier_key(q)
            qv = self._fields.get_qualifier_value(q)
            ret[str(qk)] = qv
        return ret

    @cached_property
    def properties(self):
        """ get dict of str to Property instances """
        ret = []
        for prop in self.class_layout.properties:
            n = prop.name
            i = self._property_index_map[n]
            t = self._property_type_map[n]
            v = self.toc[i]
            ret.append(self._fields.get_value(v, t))
        return ret

    def get_property_value(self, name):
        i = self._property_index_map[name]
        t = self._property_type_map[name]
        v = self.toc[i]
        return self._fields.get_value(v, t)

    @property
    def key(self):
        ret = InstanceKey()
        for prop_name in self.class_layout.class_definition.keys:
            ret[prop_name] = self.get_property_value(prop_name)
        return ret


class CoreClassInstance(vstruct.VStruct, LoggingObject):
    """
    begins with DWORD:0x0 and has no hash field
    seen at least for __NAMESPACE on an XP repo
    """
    def __init__(self, class_layout):
        vstruct.VStruct.__init__(self)
        LoggingObject.__init__(self)

        self.class_layout = class_layout
        self._buf = None

        self._unk0 = v_uint32()
        self.ts = FILETIME()
        self.data_length2 = v_uint32()  # length of all instance data
        self.extra_padding = v_bytes(size=8)

        self.toc = vstruct.VArray()
        for prop in self.class_layout.properties:
            self.toc.vsAddElement(prop.type.value_parser())

        self.qualifiers_list = QualifiersList()
        self.unk1 = v_uint32()
        self.data_length = v_uint32()  # high bit always set, length of variable data
        self.data = v_bytes(size=0)

        self._property_index_map = {prop.name: i for i, prop in enumerate(self.class_layout.properties)}
        self._property_type_map = {prop.name: prop.type for prop in self.class_layout.properties}

        self._fields = ClassFieldGetter(self.data)

    def pcb_data_length(self):
        self["data"].vsSetLength(self.data_length & 0x7FFFFFFF)

    def __repr__(self):
        # TODO: make this nice
        return "CoreClassInstance()".format()

    @property
    def class_name(self):
        return self._fields.get_string(0x0)

    @cached_property
    def qualifiers(self):
        """ get dict of str to str """
        # TODO: remove duplication
        ret = {}
        for i in range(self.qualifiers_list.count):
            q = self.qualifiers_list.qualifiers[i]
            qk = self._fields.get_qualifier_key(q)
            qv = self._fields.get_qualifier_value(q)
            ret[str(qk)] = qv
        return ret

    @cached_property
    def properties(self):
        """ get dict of str to Property instances """
        ret = []
        for prop in self.class_layout.properties:
            n = prop.name
            i = self._property_index_map[n]
            t = self._property_type_map[n]
            v = self.toc[i]
            ret.append(self._fields.get_value(v, t))
        return ret

    def get_property_value(self, name):
        i = self._property_index_map[name]
        t = self._property_type_map[name]
        v = self.toc[i]
        return self._fields.get_value(v, t)

    def get_property(self, name):
        raise NotImplementedError()


class ClassLayoutProperty(LoggingObject):
    def __init__(self, prop, class_layout):
        """
        TODO: its unclear which cl should be passed here.
            - the one one which the prop is defined?
            - the leaf cl from which we're trying to get default values?  <--

        :type prop:  ClassDefinitionProperty
        :type class_layout: ClassLayout
        """
        super(ClassLayoutProperty, self).__init__()
        self._prop = prop
        self.class_layout = class_layout

    @property
    def type(self):
        return self._prop.type

    @property
    def qualifiers(self):
        return self._prop.qualifiers

    @property
    def name(self):
        return self._prop.name

    @property
    def index(self):
        return self._prop.index

    @property
    def offset(self):
        return self._prop.offset

    @property
    def level(self):
        return self._prop.level

    def __repr__(self):
        return "Property(name: {:s}, type: {:s}, qualifiers: {:s})".format(
            self.name,
            CIM_TYPES.vsReverseMapping(self.type.type),
            ",".join("%s=%s" % (k, str(v)) for k, v in self.qualifiers.items()))

    @property
    def is_inherited(self):
        return self.class_layout.property_default_values.get_state_by_index(self.index).is_inherited

    @property
    def has_default_value(self):
        return self.class_layout.property_default_values.get_state_by_index(self.index).has_default_value

    @property
    def default_value(self):
        if not self.has_default_value:
            raise RuntimeError("property has no default value!")

        if not self.is_inherited:
            # then the data is stored nicely in the CD prop data section
            v = self.class_layout.property_default_values.default_values_toc[self.index]
            return self.class_layout.class_definition.property_data.get_value(v, self.type)
        else:
            # we have to walk up the derivation path looking for the default value
            rderivation = self.class_layout.derivation[:]
            rderivation.reverse()

            for ancestor_cl in rderivation:
                defaults = ancestor_cl.property_default_values
                state = defaults.get_state_by_index(self.index)
                if not state.has_default_value:
                    raise RuntimeError("prop with inherited default value has bad ancestor (no default value)")

                if state.is_inherited:
                    # keep trucking! look further up the ancestry tree.
                    continue

                # else, this must be where the default value is defined
                v = defaults.default_values_toc[self.index]
                return ancestor_cl.class_definition.property_data.get_value(v, self.type)
            raise RuntimeError("unable to find ancestor class with default value")


class ClassLayout(LoggingObject):
    def __init__(self, object_resolver, namespace, class_definition):
        """
        :type object_resolver: ObjectResolver
        :type namespace: str
        :type class_definition: ClassDefinition
        """
        super(ClassLayout, self).__init__()
        self.object_resolver = object_resolver
        self.namespace = namespace
        self.class_definition = class_definition

    def __repr__(self):
        # TODO: fixme
        return "ClassLayout(name: {:s})".format(self.class_definition.class_name)

    @cached_property
    def derivation(self):
        """
        list from root to leaf of class layouts
        """
        derivation = []

        cl = self
        super_class_name = self.class_definition.super_class_name

        while super_class_name != "":
            derivation.append(cl)
            cl = self.object_resolver.get_cl(self.namespace, super_class_name)
            super_class_name = cl.class_definition.super_class_name
        derivation.append(cl)
        derivation.reverse()
        return derivation

    @cached_property
    def property_default_values(self):
        """ :rtype: PropertyDefaultValues """
        props = self.properties.values()
        props = sorted(props, key=lambda p: p.index)
        default_values = PropertyDefaultValues(props)
        d = self.class_definition.property_default_values_data
        default_values.vsParse(d)
        return default_values

    @cached_property
    def properties(self):
        props = {}  # type: Mapping[int, ClassLayoutProperty]
        for cl in self.derivation:
            for prop in cl.class_definition.properties.values():
                props[prop.index] = ClassLayoutProperty(prop, self)
        return {prop.name: prop for prop in props.values()}

    @cached_property
    def properties_length(self):
        off = 0
        for prop in self.properties:
            if prop.type.is_array:
                off += 0x4
            else:
                off += CIM_TYPE_SIZES[prop.type.type]
        return off



class ObjectResolver(LoggingObject):
    def __init__(self, cim, index):
        super(ObjectResolver, self).__init__()
        self._cim = cim
        self._index = index

        self._cdcache = {}  # type: Mapping[str, ClassDefinition]
        self._clcache = {}  # type: Mapping[str, ClassLayout]

        # until we can correctly compute instance key hashes, maintain a cache mapping
        #   from encountered keys (serialized) to the instance hashes
        self._ihashcache = {}  # type: Mapping[str,str]

    def _build(self, prefix, name=None):
        if name is None:
            return prefix
        else:
            return prefix + self._index.hash(name.upper().encode("UTF-16LE"))

    def NS(self, name=None):
        return self._build("NS_", name)

    def CD(self, name=None):
        return self._build("CD_", name)

    def CR(self, name=None):
        return self._build("CR_", name)

    def R(self, name=None):
        return self._build("R_", name)

    def CI(self, name=None):
        return self._build("CI_", name)

    def KI(self, name=None):
        return self._build("KI_", name)

    def IL(self, name=None, known_hash=None):
        if known_hash is not None:
            return "IL_" + known_hash
        return self._build("IL_", name)

    def I(self, name=None):
        return self._build("I_", name)

    def get_object(self, query):
        """ fetch the first object buffer matching the query """
        self.d("query: %s", str(query))
        ref = one(self._index.lookup_keys(query))
        if not ref:
            raise IndexError("Failed to find: {:s}".format(str(query)))
        # TODO: should ensure this query has a unique result
        return self._cim.logical_data_store.get_object_buffer(ref)

    def get_keys(self, query):
        """ return a generator of keys matching the query """
        return self._index.lookup_keys(query)

    def get_objects(self, query):
        """ return a generator of object buffers matching the query """
        for ref in self.get_keys(query):
            yield ref, self._cim.logical_data_store.get_object_buffer(ref)

    @property
    def root_namespace(self):
        return SYSTEM_NAMESPACE_NAME

    def get_cd_buf(self, namespace_name, class_name):
        q = Key("{}/{}".format(
                self.NS(namespace_name),
                self.CD(class_name)))
        # TODO: should ensure this query has a unique result
        ref = one(self._index.lookup_keys(q))

        # some standard class definitions (like __NAMESPACE) are not in the
        #   current NS, but in the __SystemClass NS. So we try that one, too.

        if ref is None:
            self.d("didn't find %s in %s, retrying in %s", class_name, namespace_name, SYSTEM_NAMESPACE_NAME)
            q = Key("{}/{}".format(
                    self.NS(SYSTEM_NAMESPACE_NAME),
                    self.CD(class_name)))
        return self.get_object(q)

    def get_cd(self, namespace_name, class_name):
        c_id = get_class_id(namespace_name, class_name)
        c_cd = self._cdcache.get(c_id, None)
        if c_cd is None:
            self.d("cdcache miss")

            q = Key("{}/{}".format(
                    self.NS(namespace_name),
                    self.CD(class_name)))
            # TODO: should ensure this query has a unique result
            ref = one(self._index.lookup_keys(q))

            # some standard class definitions (like __NAMESPACE) are not in the
            #   current NS, but in the __SystemClass NS. So we try that one, too.

            if ref is None:
                self.d("didn't find %s in %s, retrying in %s", class_name, namespace_name, SYSTEM_NAMESPACE_NAME)
                q = Key("{}/{}".format(
                        self.NS(SYSTEM_NAMESPACE_NAME),
                        self.CD(class_name)))
            c_cdbuf = self.get_object(q)
            c_cd = ClassDefinition()
            c_cd.vsParse(c_cdbuf)
            self._cdcache[c_id] = c_cd
        return c_cd

    def get_cl(self, namespace_name, class_name):
        c_id = get_class_id(namespace_name, class_name)
        c_cl = self._clcache.get(c_id, None)
        if not c_cl:
            self.d("clcache miss")
            c_cd = self.get_cd(namespace_name, class_name)
            c_cl = ClassLayout(self, namespace_name, c_cd)
            self._clcache[c_id] = c_cl
        return c_cl

    def get_ci(self, namespace_name, class_name, instance_key):
        # TODO: this is a major hack! we should build the hash, but the data to hash
        #    has not been described correctly..

        # CI or KI?
        q = Key("{}/{}/{}".format(
                    self.NS(namespace_name),
                    self.CI(class_name),
                    self.IL(known_hash=self._ihashcache.get(str(instance_key), ""))))

        cl = self.get_cl(namespace_name, class_name)
        for _, buf in self.get_objects(q):
            instance = self.parse_instance(self.get_cl(namespace_name, class_name), buf)
            this_is_it = True
            for k in cl.class_definition.keys:
                if not instance.get_property_value(k) == instance_key[k]:
                    this_is_it = False
                    break
            if this_is_it:
                return instance

        raise IndexError("Key not found: " + str(instance_key))

    def get_ci_buf(self, namespace_name, class_name, instance_key):
        # TODO: this is a major hack!

        # CI or KI?
        q = Key("{}/{}/{}".format(
                    self.NS(namespace_name),
                    self.CI(class_name),
                    self.IL(known_hash=self._ihashcache.get(str(instance_key), ""))))

        cl = self.get_cl(namespace_name, class_name)
        for _, buf in self.get_objects(q):
            instance = self.parse_instance(self.get_cl(namespace_name, class_name), buf)
            this_is_it = True
            for k in cl.class_definition.keys:
                if not instance.get_property_value(k) == instance_key[k]:
                    this_is_it = False
                    break
            if this_is_it:
                return buf

        raise IndexError("Key not found: " + instance_key)

    @property
    def ns_cd(self):
        return self.get_cd(SYSTEM_NAMESPACE_NAME, NAMESPACE_CLASS_NAME)

    @property
    def ns_cl(self):
        return self.get_cl(SYSTEM_NAMESPACE_NAME, NAMESPACE_CLASS_NAME)

    def parse_instance(self, cl, buf):
        if buf[0x0:0x4] == "\x00\x00\x00\x00":
            i = CoreClassInstance(cl)
        else:
            i = ClassInstance(self._cim.cim_type, cl)
        i.vsParse(buf)
        return i

    NamespaceSpecifier = namedtuple("NamespaceSpecifier", ["namespace_name"])
    def get_ns_children_ns(self, namespace_name):
        q = Key("{}/{}/{}".format(
                    self.NS(namespace_name),
                    self.CI(NAMESPACE_CLASS_NAME),
                    self.IL()))

        for ref, ns_i in self.get_objects(q):
            i = self.parse_instance(self.ns_cl, ns_i)
            yield self.NamespaceSpecifier(namespace_name + "\\" + i.get_property_value("Name"))
        if namespace_name == ROOT_NAMESPACE_NAME:
            yield self.NamespaceSpecifier(SYSTEM_NAMESPACE_NAME)

    ClassDefinitionSpecifier = namedtuple("ClassDefintionSpecifier", ["namespace_name", "class_name"])
    def get_ns_children_cd(self, namespace_name):
        q = Key("{}/{}".format(
                    self.NS(namespace_name),
                    self.CD()))

        for _, cdbuf in self.get_objects(q):
            cd = ClassDefinition()
            cd.vsParse(cdbuf)
            yield self.ClassDefinitionSpecifier(namespace_name, cd.class_name)

    ClassInstanceSpecifier = namedtuple("ClassInstanceSpecifier", ["namespace_name", "class_name", "instance_key"])
    def get_cd_children_ci(self, namespace_name, class_name):
        # TODO: CI or KI?
        q = Key("{}/{}/{}".format(
                    self.NS(namespace_name),
                    self.CI(class_name),
                    self.IL()))

        for ref, ibuf in self.get_objects(q):
            try:
                instance = self.parse_instance(self.get_cl(namespace_name, class_name), ibuf)
            except:
                g_logger.error("failed to parse instance: %s %s at %s", namespace_name, class_name, ref)
                g_logger.error(traceback.format_exc())
                continue

            # str(instance.key) is sorted k-v pairs, should be unique
            self._ihashcache[str(instance.key)] = ref.get_part_hash("IL_")
            yield self.ClassInstanceSpecifier(namespace_name, class_name, instance.key)


def get_class_id(namespace, classname):
    return namespace + ":" + classname


class TreeNamespace(LoggingObject):
    def __init__(self, object_resolver, name):
        super(TreeNamespace, self).__init__()
        self._object_resolver = object_resolver
        self.name = name

    def __repr__(self):
        return "\\{namespace:s}".format(namespace=self.name)

    @property
    def namespace(self):
        """ get parent namespace """
        if self.name == ROOT_NAMESPACE_NAME:
            return None
        else:
            # TODO
            raise NotImplementedError()

    @property
    def namespaces(self):
        """ return a generator of direct child namespaces """
        yielded = set([])
        for ns in self._object_resolver.get_ns_children_ns(self.name):
            name = ns.namespace_name
            if name not in yielded:
                yielded.add(name)
                yield TreeNamespace(self._object_resolver, ns.namespace_name)

    @property
    def classes(self):
        yielded = set([])
        for cd in self._object_resolver.get_ns_children_cd(self.name):
            name = cd.class_name
            if name not in yielded:
                yielded.add(name)
                yield TreeClassDefinition(self._object_resolver, self.name, cd.class_name)


class TreeClassDefinition(LoggingObject):
    def __init__(self, object_resolver, namespace, name):
        super(TreeClassDefinition, self).__init__()
        self._object_resolver = object_resolver
        self.ns = namespace
        self.name = name

    def __repr__(self):
        return "\\{namespace:s}:{klass:s}".format(namespace=self.ns, klass=self.name)

    @property
    def namespace(self):
        """ get parent namespace """
        return TreeNamespace(self._object_resolver, self.ns)

    @property
    def cd(self):
        return self._object_resolver.get_cd(self.ns, self.name)

    @property
    def cl(self):
        return self._object_resolver.get_cl(self.ns, self.name)

    @property
    def instances(self):
        """ get instances of this class definition """
        yielded = set([])
        for ci in self._object_resolver.get_cd_children_ci(self.ns, self.name):
            key = str(ci.instance_key)
            if key not in yielded:
                yielded.add(key)
                yield TreeClassInstance(self._object_resolver, self.ns, ci.class_name, ci.instance_key)


class TreeClassInstance(LoggingObject):
    def __init__(self, object_resolver, namespace_name, class_name, instance_key):
        super(TreeClassInstance, self).__init__()
        self._object_resolver = object_resolver
        self.ns = namespace_name
        self.class_name = class_name
        self.instance_key = instance_key

    def __repr__(self):
        return "\\{namespace:s}:{klass:s}.{key:s}".format(
            namespace=self.ns, klass=self.class_name, key=repr(self.instance_key))

    @property
    def klass(self):
        """ get class definition """
        return TreeClassDefinition(self._object_resolver, self.ns, self.class_name)

    @property
    def namespace(self):
        """ get parent namespace """
        return TreeNamespace(self._object_resolver, self.ns)

    @property
    def cl(self):
        return self._object_resolver.get_cl(self.ns, self.class_name)

    @property
    def cd(self):
        return self._object_resolver.get_cd(self.ns, self.class_name)

    @property
    def ci(self):
        return self._object_resolver.get_ci(self.ns, self.class_name, self.instance_key)


class Tree(LoggingObject):
    def __init__(self, cim):
        super(Tree, self).__init__()
        self._object_resolver = ObjectResolver(cim, Index(cim.cim_type, cim.logical_index_store))

    def __repr__(self):
        return "Tree"

    @property
    def root(self):
        """ get root namespace """
        return TreeNamespace(self._object_resolver, ROOT_NAMESPACE_NAME)


# TODO: this probably doesn't go here
class Moniker(LoggingObject):
    def __init__(self, string):
        super(Moniker, self).__init__()
        self._string = string
        self.hostname = None  # type: str
        self.namespace = None  # type: str
        self.klass = None  # type: str
        self.instance = None  # type: dict of str to str
        self._parse()

    def __str__(self):
        return self._string

    def __repr__(self):
        return "Moniker({:s})".format(self._string)

    def _parse(self):
        """
        supported schemas:
            //./root/cimv2 --> namespace
            //HOSTNAME/root/cimv2 --> namespace
            winmgmts://./root/cimv2 --> namespace
            //./root/cimv2:Win32_Service --> class
            //./root/cimv2:Win32_Service.Name="Beep" --> instance
            //./root/cimv2:Win32_Service.Name='Beep' --> instance

        we'd like to support this, but can't differentiate this
          from a class:
            //./root/cimv2/Win32_Service --> class
        """
        s = self._string
        s = s.replace("\\", "/")

        if s.startswith("winmgmts:"):
            s = s[len("winmgmts:"):]

        if not s.startswith("//"):
            raise RuntimeError("Moniker doesn't contain '//': %s" % (s))
        s = s[len("//"):]

        self.hostname, _, s = s.partition("/")
        if self.hostname == ".":
            self.hostname = "localhost"

        s, _, keys = s.partition(".")
        if keys == "":
            keys = None
        # s must now not contain any special characters
        # we'll process the keys later

        self.namespace, _, self.klass = s.partition(":")
        if self.klass == "":
            self.klass = None
        self.namespace = self.namespace.replace("/", "\\")

        if keys is not None:
            self.instance = {}
            for key in keys.split(","):
                k, _, v = key.partition("=")
                self.instance[k] = v.strip("\"'")
