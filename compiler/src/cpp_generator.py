import time
import os
import os.path
from string import Template
from parser import *
from generator import *

HEADER_COMMENT = """/**
 * Autogenerated by Thrift
 * ${date}
 *
 * DO NOT EDIT UNLESS YOU ARE SURE THAT YOU KNOW WHAT YOU ARE DOING
 */
 """

CPP_TYPES_HEADER = Template(HEADER_COMMENT+"""
#if !defined(${source}_types_h_)
#define ${source}_types_h_ 1

#include <Thrift.h>
""")

CPP_TYPES_FOOTER = Template("""
#endif // !defined(${source}_types_h_)
""")

CPP_SERVICES_HEADER = Template(HEADER_COMMENT+"""
#if !defined(${source}_h_)
#define ${source}_h_ 1

#include <Thrift.h>
#include <TProcessor.h>
#include <protocol/TProtocol.h>
#include <transport/TTransport.h>
#include \"${source}_types.h\"
""")

CPP_SERVICES_FOOTER = Template("""
#endif // !defined(${source}_h_)""")

CPP_IMPL_HEADER = Template(HEADER_COMMENT+"""
#include \"${source}.h\"
""")

CPP_IMPL_FOOTER = Template("")

def cpp_debug(arg):
    print(arg)

class Indenter(object):
    def __init__(self, level=0, step=4):
	self.level = level
	self.step = step
	self.chunk = ""
	for i in range(step):
	    self.chunk+= " "
	self.prefix=""

    def inc(self):
	self.level+= self.step
	self.prefix += self.chunk

    def dec(self):
	self.level-= self.step
	if(self.level < 0):
	    raise Exception, "Illegal indent level"
	self.prefix = self.prefix[:self.level]

    def __call__(self):
	return  self.prefix

class CFile(file):

    def __init__(self, name, flags):
        file.__init__(self, name, flags)
        self.indent = Indenter()
        self.newline = True

    def rwrite(self, value):
        file.write(self, value)

    def write(self, value=""):
        if self.newline:
            self.rwrite(self.indent())
            self.newline = False
        self.rwrite(value)

    def writeln(self, value=""):
        self.write(value+"\n")
        self.newline = True

    def beginBlock(self):
        self.writeln("{")
        self.indent.inc();

    def endBlock(self, suffix=""):
        self.indent.dec();
        self.writeln("}"+suffix)

CPP_PRIMITIVE_MAP = {
    "void" : "void",
    "bool" : "bool",
    "string": "std::string",
    "utf7": "std::string",
    "utf8": "std::wstring",
    "utf16": "std::utf16",
    "byte" : "uint8_t",
    "i08": "int8_t",
    "i16": "int16_t",
    "i32": "int32_t",
    "i64": "int64_t",
    "u08": "uint8_t",
    "u16": "uint16_t",
    "u32": "uint32_t",
    "u64": "uint64_t",
    "float": "double"
}

CPP_CONTAINER_MAP = {
    MapType : "std::map",
    ListType: "std::list",
    SetType : "std::set",
}

def typeToCTypeDeclaration(ttype):

    if isinstance(ttype, PrimitiveType):
        return CPP_PRIMITIVE_MAP[ttype.name]

    elif isinstance(ttype, CollectionType):

        result = CPP_CONTAINER_MAP[type(ttype)]+"<"
        
        if isinstance(ttype, MapType):
            result+= typeToCTypeDeclaration(ttype.keyType)+", "+ typeToCTypeDeclaration(ttype.valueType)

        elif isinstance(ttype, SetType) or isinstance(ttype, ListType):
            result+= typeToCTypeDeclaration(ttype.valueType)

        else:
            raise Exception, "Unknown Collection Type "+str(ttype)

        result+= "> "

        return result

    elif isinstance(ttype, StructType):
        return "struct "+ttype.name

    elif isinstance(ttype, TypedefType):
        return ttype.name;

    elif isinstance(ttype, EnumType):
        return ttype.name;

    elif isinstance(ttype, Function):
        return typeToCTypeDeclaration(ttype.returnType())+ " "+ttype.name+"("+string.join([typeToCTypeDeclaration(arg) for arg in ttype.args()], ", ")+")"

    elif isinstance(ttype, Field):
        return typeToCTypeDeclaration(ttype.type)+ " "+ttype.name

    else:
        raise Exception, "Unknown type "+str(ttype)

def toTypeDefDefinition(typedef):

    return "typedef "+typeToCTypeDeclaration(typedef.definitionType)+" "+typedef.name+";"

def toEnumDefinition(enum):

    result = "enum "+enum.name+" {\n"

    first = True

    for ed in enum.enumDefs:
        if first:
            first = False
        else:
            result+= ",\n"
        result+= "    "+ed.name+" = "+str(ed.id)

    result+= "\n};\n"

    return result


def toStructDefinition(struct):

    result = "struct "+struct.name+" {\n"

    for field in struct.fieldList:
	if toCanonicalType(field.type) != VOID_TYPE:
	    result += "    "+typeToCTypeDeclaration(field)+";\n"

    result+= "    struct {\n"

    for field in struct.fieldList:
	result+= "        bool "+field.name+";\n"
    result+= "   } __isset;\n"

    result+= "};\n"

    return result

CPP_DEFINITION_MAP = {
    TypedefType : toTypeDefDefinition,
    EnumType : toEnumDefinition,
    StructType : toStructDefinition,
    Service : None
    }
    
def toDefinitions(definitions):

    result = ""

    for definition in definitions:

        writer = CPP_DEFINITION_MAP[type(definition)]

        if writer:
            result+= writer(definition)+"\n"

    return result

CPP_THRIFT_NS = "facebook::thrift"

CPP_INTERFACE_FUNCTION_DECLARATION = Template("""    virtual ${functionDeclaration} = 0;
""")

CPP_INTERFACE_DECLARATION = Template("""
class ${service}If {
    public:
    virtual ~${service}If() {}
${functionDeclarations}};
""")

def toServiceInterfaceDeclaration(service, debugp=None):

    functionDeclarations = string.join([CPP_INTERFACE_FUNCTION_DECLARATION.substitute(service=service.name, functionDeclaration=typeToCTypeDeclaration(function)) for function in service.functionList], "")

    return CPP_INTERFACE_DECLARATION.substitute(service=service.name, functionDeclarations=functionDeclarations)

CPP_EXCEPTION = CPP_THRIFT_NS+"::Exception"

CPP_SP = Template("boost::shared_ptr<${klass}> ")

CPP_PROCESSOR = CPP_THRIFT_NS+"::TProcessor"
CPP_PROCESSORP = CPP_SP.substitute(klass=CPP_PROCESSOR)

CPP_PROTOCOL_NS = CPP_THRIFT_NS+"::protocol"
CPP_PROTOCOL = CPP_PROTOCOL_NS+"::TProtocol"
CPP_PROTOCOLP = CPP_SP.substitute(klass="const "+CPP_PROTOCOL)


CPP_TRANSPORT_NS = CPP_THRIFT_NS+"::transport"
CPP_TRANSPORT = CPP_TRANSPORT_NS+"::TTransport"
CPP_TRANSPORTP = CPP_SP.substitute(klass=CPP_TRANSPORT)

CPP_PROTOCOL_TSTOP = CPP_PROTOCOL_NS+"::T_STOP"
CPP_PROTOCOL_TTYPE = CPP_PROTOCOL_NS+"::TType"
CPP_PROTOCOL_MESSAGE_TYPE = CPP_PROTOCOL_NS+"::TMessageType"
CPP_PROTOCOL_CALL = CPP_PROTOCOL_NS+"::T_CALL"
CPP_PROTOCOL_REPLY = CPP_PROTOCOL_NS+"::T_REPLY"

CPP_TTYPE_MAP = {
    STOP_TYPE : CPP_PROTOCOL_NS+"::T_STOP",
    VOID_TYPE : CPP_PROTOCOL_NS+"::T_VOID",
    BOOL_TYPE : CPP_PROTOCOL_NS+"::T_BOOL",
    UTF7_TYPE : CPP_PROTOCOL_NS+"::T_UTF7",
    UTF7_TYPE : CPP_PROTOCOL_NS+"::T_UTF7",
    UTF8_TYPE : CPP_PROTOCOL_NS+"::T_UTF8",
    UTF16_TYPE : CPP_PROTOCOL_NS+"::T_UTF16",
    U08_TYPE : CPP_PROTOCOL_NS+"::T_U08",
    I08_TYPE : CPP_PROTOCOL_NS+"::T_I08",
    I16_TYPE : CPP_PROTOCOL_NS+"::T_I16",
    I32_TYPE : CPP_PROTOCOL_NS+"::T_I32",
    I64_TYPE : CPP_PROTOCOL_NS+"::T_I64",
    U08_TYPE : CPP_PROTOCOL_NS+"::T_U08",
    U16_TYPE : CPP_PROTOCOL_NS+"::T_U16",
    U32_TYPE : CPP_PROTOCOL_NS+"::T_U32",
    U64_TYPE : CPP_PROTOCOL_NS+"::T_U64",
    FLOAT_TYPE : CPP_PROTOCOL_NS+"::T_FLOAT",
    StructType : CPP_PROTOCOL_NS+"::T_STRUCT",
    ListType : CPP_PROTOCOL_NS+"::T_LIST",
    MapType : CPP_PROTOCOL_NS+"::T_MAP",
    SetType : CPP_PROTOCOL_NS+"::T_SET"
}


CPP_SERVER_FUNCTION_DECLARATION = Template("""    void process_${function}(uint32_t seqid, """+CPP_TRANSPORTP+""" itrans, """+CPP_TRANSPORTP+""" otrans);
""")

CPP_SERVER_FUNCTION_DEFINITION = Template("""
void ${service}ServerIf::process_${function}(uint32_t seqid, """+CPP_TRANSPORTP+""" itrans, """+CPP_TRANSPORTP+""" otrans) {

    uint32_t xfer = 0;

    ${argsStructDeclaration};

    ${argsStructReader};

    _iprot->readMessageEnd(itrans);

    ${returnValueDeclaration};

    ${functionCall};

    ${resultStructDeclaration};

    ${returnToResult};

    _oprot->writeMessageBegin(otrans, \"${function}\", """+CPP_PROTOCOL_REPLY+""", seqid);

    ${resultStructWriter};

    _oprot->writeMessageEnd(otrans);

    otrans->flush();
}
""")

CPP_SERVER_PROCESS_DEFINITION = Template("""
bool ${service}ServerIf::process("""+CPP_TRANSPORTP+""" itrans, """+CPP_TRANSPORTP+""" otrans) {

    std::string name;

    """+CPP_PROTOCOL_MESSAGE_TYPE+""" messageType;

    uint32_t seqid;

    _iprot->readMessageBegin(itrans, name, messageType, seqid);

    if(messageType == """+CPP_PROTOCOL_CALL+""") {
${callProcessSwitch}
    } else {
        throw """+CPP_EXCEPTION+"""(\"Unexpected message type\");     
    }

    return true;
}
""")

def toWireType(ttype):

    if isinstance(ttype, PrimitiveType):
	return CPP_TTYPE_MAP[ttype]

    elif isinstance(ttype, EnumType):
	return CPP_TTYPE_MAP[I32_TYPE]

    elif isinstance(ttype, TypedefType):
	return toWireType(toCanonicalType(ttype))

    elif isinstance(ttype, StructType) or isinstance(ttype, CollectionType):
	return CPP_TTYPE_MAP[type(ttype)]

    else:
	raise Exception, "No wire type for thrift type: "+str(ttype)

CPP_SERVER_DECLARATION = Template("""
class ${service}ServerIf : public ${service}If, public """+CPP_PROCESSOR+""" {
    public:
    ${service}ServerIf("""+CPP_PROTOCOLP+""" protocol): _iprot(protocol), _oprot(protocol) {}
    ${service}ServerIf("""+CPP_PROTOCOLP+""" iprot, """+CPP_PROTOCOLP+""" oprot) : _iprot(iprot), _oprot(oprot) {}
    virtual ~${service}ServerIf() {}
    bool process("""+CPP_TRANSPORTP+""" _itrans,"""+CPP_TRANSPORTP+""" _otrans);
    protected:
    """+CPP_PROTOCOLP+""" _iprot;
    """+CPP_PROTOCOLP+""" _oprot;
    private:
${functionDeclarations}};
""")

def toServerDeclaration(service, debugp=None):

    functionDeclarations = string.join([CPP_SERVER_FUNCTION_DECLARATION.substitute(function=function.name) for function in service.functionList], "")

    return CPP_SERVER_DECLARATION.substitute(service=service.name, functionDeclarations=functionDeclarations)
    
CPP_CLIENT_FUNCTION_DECLARATION = Template("""    ${functionDeclaration};
""")


CPP_CLIENT_FUNCTION_DEFINITION = Template("""
${returnDeclaration} ${service}Client::${function}(${argsDeclaration}) {

    uint32_t xfer = 0;
    std::string name;
    """+CPP_PROTOCOL_MESSAGE_TYPE+""" messageType;
    uint32_t cseqid = 0;
    uint32_t rseqid = 0;

    _oprot->writeMessageBegin(_otrans, \"${function}\", """+CPP_PROTOCOL_CALL+""", cseqid);

    ${argsStructDeclaration};

${argsToStruct};

    ${argsStructWriter};

    _otrans->flush();

    _iprot->readMessageBegin(_itrans, name, messageType, rseqid);

    if(messageType != """+CPP_PROTOCOL_REPLY+""" || 
       rseqid != cseqid) {
        throw """+CPP_EXCEPTION+"""(\"unexpected message type or id\");
    }

    ${resultStructDeclaration};

    ${resultStructReader};

    _iprot->readMessageEnd(_itrans);

    if(__result.__isset.success) {
        ${success};
    } else {
        throw """+CPP_EXCEPTION+"""(\"${function} failed\");
    }
}
""")

CPP_CLIENT_DECLARATION = Template("""
class ${service}Client : public ${service}If {

    public:

    ${service}Client("""+CPP_TRANSPORTP+""" transport, """+CPP_PROTOCOLP+""" protocol): _itrans(transport), _otrans(transport), _iprot(protocol), _oprot(protocol) {}

    ${service}Client("""+CPP_TRANSPORTP+""" itrans, """+CPP_TRANSPORTP+""" otrans, """+CPP_PROTOCOLP+""" iprot, """+CPP_PROTOCOLP+""" oprot) : _itrans(itrans), _otrans(otrans), _iprot(iprot), _oprot(oprot) {}

${functionDeclarations}
    private:
    """+CPP_TRANSPORTP+""" _itrans;
    """+CPP_TRANSPORTP+""" _otrans;
    """+CPP_PROTOCOLP+""" _iprot;
    """+CPP_PROTOCOLP+""" _oprot;
};""")

def toServerFunctionDefinition(servicePrefix, function, debugp=None):
    result = ""

    argsStructDeclaration = typeToCTypeDeclaration(function.argsStruct)+" __args"

    argsStructReader = toReaderCall("__args", function.argsStruct, "_iprot")

    resultStructDeclaration = typeToCTypeDeclaration(function.resultStruct)+" __result"

    resultStructWriter = toWriterCall("__result", function.resultStruct, "_oprot")

    if function.returnType() != VOID_TYPE:
	returnValueDeclaration = typeToCTypeDeclaration(toCanonicalType(function.returnType()))+"  __returnValue"
	functionCall = "__returnValue = "
	returnToResult = "__result.success = __returnValue"
    else:
	returnValueDeclaration = ""
	functionCall = ""
	returnToResult = ""

    functionCall+= function.name+"("+string.join(["__args."+arg.name for arg in function.args()], ", ")+")"

    result+= CPP_SERVER_FUNCTION_DEFINITION.substitute(service=servicePrefix, function=function.name,
						       argsStructDeclaration=argsStructDeclaration, 
						       argsStructReader=argsStructReader, 
						       functionCall=functionCall,
						       returnToResult=returnToResult,
						       resultStructDeclaration=resultStructDeclaration,
						       resultStructWriter=resultStructWriter,
						       returnValueDeclaration=returnValueDeclaration)

    

    return result

def toServerServiceDefinition(service, debugp=None):

    result = ""

    for function in service.functionList:
	
	result+= toServerFunctionDefinition(service.name, function, debugp)
    
    callProcessSwitch = "        if"+string.join(["(name.compare(\""+function.name+"\") == 0) { process_"+function.name+"(seqid, itrans, otrans);}" for function in service.functionList], "\n        else if")+"\n        else {throw "+CPP_EXCEPTION+"(\"Unknown function name \\\"\"+name+\"\\\"\");}"

    result+= CPP_SERVER_PROCESS_DEFINITION.substitute(service=service.name, callProcessSwitch=callProcessSwitch)

    return result

def toServerDefinition(program, debugp=None):

    return string.join([toServerServiceDefinition(service) for service in program.serviceMap.values()], "\n")

def toClientDeclaration(service, debugp=None):

    functionDeclarations = string.join([CPP_CLIENT_FUNCTION_DECLARATION.substitute(functionDeclaration=typeToCTypeDeclaration(function)) for function in service.functionList], "")

    return CPP_CLIENT_DECLARATION.substitute(service=service.name, functionDeclarations=functionDeclarations)+"\n"

def toClientFunctionDefinition(servicePrefix, function, debugp=None):

    returnDeclaration = typeToCTypeDeclaration(function.returnType())

    argsDeclaration = string.join([typeToCTypeDeclaration(function.args()[ix].type)+" __arg"+str(ix) for ix in range(len(function.args()))], ", ")

    argsStructDeclaration = typeToCTypeDeclaration(function.argsStruct)+" __args"

    argsStructWriter = toWriterCall("__args", function.argsStruct, "_oprot", "_otrans")

    argsToStruct= string.join(["    __args."+function.args()[ix].name+" = __arg"+str(ix) for ix in range(len(function.args()))], ";\n")
    
    resultStructDeclaration = typeToCTypeDeclaration(function.resultStruct)+" __result"

    resultStructReader = toReaderCall("__result", function.resultStruct, "_iprot", "_itrans")

    if(toCanonicalType(function.returnType()) != VOID_TYPE):
	
	success = "return __result.success;"
    else:
	success = ""
	    
    return CPP_CLIENT_FUNCTION_DEFINITION.substitute(service=servicePrefix,
						     function=function.name,
						     returnDeclaration=returnDeclaration,
						     argsDeclaration=argsDeclaration,
						     argsStructDeclaration=argsStructDeclaration,
						     argsStructWriter=argsStructWriter,
						     argsToStruct=argsToStruct,
						     resultStructDeclaration=resultStructDeclaration, 
						     resultStructReader=resultStructReader,
						     success=success)

def toClientServiceDefinition(service, debugp=None):

    result = ""

    for function in service.functionList:

	result+= toClientFunctionDefinition(service.name, function)

    return result

def toClientDefinition(program, debugp=None):

    return string.join([toClientServiceDefinition(service) for service in program.serviceMap.values()], "\n")

def toServiceDeclaration(service, debugp=None):
    return toServiceInterfaceDeclaration(service, debugp) + toServerDeclaration(service, debugp) + toClientDeclaration(service, debugp)

def toGenDir(filename, suffix="cpp-gen", debugp=None):

    result = os.path.join(os.path.split(filename)[0], suffix)

    if not os.path.exists(result):
        os.mkdir(result)

    return result

def toBasename(filename, debugp=None):
    """ Take the filename minus the path and\".thrift\" extension  if present """

    basename = os.path.split(filename)[1]

    tokens = os.path.splitext(basename)

    if tokens[1].lower() == ".thrift":
        basename = tokens[0]

    if debugp:
        debugp("toBasename("+str(filename)+") => "+str(basename))

    return basename

def toDefinitionHeaderName(filename, genDir=None, debugp=None):

    if not genDir:
        genDir = toGenDir(filename)

    basename = toBasename(filename)

    result = os.path.join(genDir, basename+"_types.h")

    if debugp:
        debugp("toDefinitionHeaderName("+str(filename)+", "+str(genDir)+") => "+str(basename))

    return result

def writeDefinitionHeader(program, filename, genDir=None, debugp=None):

    definitionHeader = toDefinitionHeaderName(filename, genDir)

    if debugp:
        debugp("definitionHeader: "+str(definitionHeader))

    cfile = CFile(definitionHeader, "w")

    basename = toBasename(filename)

    cfile.writeln(CPP_TYPES_HEADER.substitute(source=basename, date=time.ctime()))

    cfile.write(toDefinitions(program.definitions))

    cfile.writeln(CPP_TYPES_FOOTER.substitute(source=basename))

    cfile.close()

def toServicesHeaderName(filename, genDir=None, debugp=None):

    if not genDir:
        genDir = toGenDir(filename)

    basename = toBasename(filename)

    result = os.path.join(genDir, basename+".h")

    if debugp:
        debugp("toDefinitionHeaderName("+str(filename)+", "+str(genDir)+") => "+str(basename))

    return result


def writeServicesHeader(program, filename, genDir=None, debugp=None):

    servicesHeader = toServicesHeaderName(filename, genDir)

    if debugp:
        debugp("servicesHeader: "+str(servicesHeader))

    cfile = CFile(servicesHeader, "w")

    basename = toBasename(filename)

    cfile.writeln(CPP_SERVICES_HEADER.substitute(source=basename, date=time.ctime()))

    services = []

    # Build orderered list of service definitions by scanning definitions list for services

    for definition in  program.definitions:
        if isinstance(definition, Service) and definition.name in program.serviceMap:
            services.append(definition)

    for service in services:

        cfile.write(toServiceDeclaration(service))

    cfile.writeln(CPP_SERVICES_FOOTER.substitute(source=basename))

    cfile.close()


CPP_STRUCT_READ = Template("""
uint32_t read${name}Struct("""+CPP_PROTOCOLP+""" _iprot, """+CPP_TRANSPORTP+""" itrans, ${declaration}& value) {

    std::string name;
    uint32_t id;
    uint32_t type;
    uint32_t xfer = 0;

    while(true) {
        xfer+= _iprot->readFieldBegin(_itrans, name, type, id);
        if(type == """+CPP_PROTOCOL_TSTOP+""") {
            break;
        }
        switch(id) {
${readFieldListSwitch}
        }
    }

    xfer+= _iprot->readStructEnd(_itrans);

    return xfer;
}
""")

CPP_PRIMITIVE_TYPE_IO_METHOD_SUFFIX_MAP = {
    "void" :"Void",
    "bool" : "Bool",
    "string": "String",
    "utf7": "String",
    "utf8": "String", 
    "utf16": "String",
    "i08": "Byte",
    "i16": "I16",
    "i32": "I32", 
    "i64": "I64", 
    "u08": "Byte",
    "u16": "U16",
    "u32": "U32",
    "u64": "U64",
    "float": "Double"
}

CPP_COLLECTION_TYPE_IO_METHOD_SUFFIX_MAP = {
    MapType : "map",
    ListType : "list",
    SetType : "set"
}

def typeToIOMethodSuffix(ttype):

    if isinstance(ttype, PrimitiveType):
        return CPP_PRIMITIVE_TYPE_IO_METHOD_SUFFIX_MAP[ttype.name]

    elif isinstance(ttype, CollectionType):

        result = CPP_COLLECTION_TYPE_IO_METHOD_SUFFIX_MAP[type(ttype)]+"_"

        if isinstance(ttype, MapType):
            result+= "k_"+typeToIOMethodSuffix(ttype.keyType)+"_"

        result += "v_"+typeToIOMethodSuffix(ttype.valueType)

        return result

    elif isinstance(ttype, StructType):
        return "struct_"+ttype.name

    elif isinstance(ttype, TypedefType):
        return ttype.name

    elif isinstance(ttype, EnumType):
        return ttype.name

    else:
        raise Exception, "Unknown type "+str(ttype)

def toReaderCall(value, ttype, reader="iprot", transport="itrans"):

    suffix = typeToIOMethodSuffix(ttype)

    if isinstance(ttype, PrimitiveType):
	if ttype != VOID_TYPE:
	    return "xfer += "+reader+"->read"+suffix+"("+transport+", "+value+")"
	else:
	    return ""

    elif isinstance(ttype, CollectionType):
        return "xfer+= read_"+suffix+"("+reader+", "+transport+", "+value+")"

    elif isinstance(ttype, StructType):
        return "xfer+= read_"+suffix+"("+reader+", "+transport+", "+value+")"

    elif isinstance(ttype, TypedefType):
        return toReaderCall("reinterpret_cast<"+typeToCTypeDeclaration(ttype.definitionType)+"&>("+value+")", ttype.definitionType, reader)

    elif isinstance(ttype, EnumType):
        return toReaderCall("reinterpret_cast<"+typeToCTypeDeclaration(I32_TYPE)+"&>("+value+")", I32_TYPE, reader)

    else:
        raise Exception, "Unknown type "+str(ttype)

def toWriterCall(value, ttype, writer="oprot", transport="otrans"):

    suffix = typeToIOMethodSuffix(ttype)

    if isinstance(ttype, PrimitiveType):
	if ttype != VOID_TYPE:
	    return "xfer+= "+writer+"->write"+suffix+"("+transport+", "+value+")"
	else:
	    return ""

    elif isinstance(ttype, CollectionType):
        return "xfer+= write_"+suffix+"("+writer+", "+transport+", "+value+")"

    elif isinstance(ttype, StructType):
        return "xfer+= write_"+suffix+"("+writer+", "+transport+", "+value+")"

    elif isinstance(ttype, TypedefType):
        return toWriterCall("reinterpret_cast<const "+typeToCTypeDeclaration(ttype.definitionType)+"&>("+value+")", ttype.definitionType, writer)

    elif isinstance(ttype, EnumType):
        return toWriterCall("reinterpret_cast<const "+typeToCTypeDeclaration(I32_TYPE)+"&>("+value+")", I32_TYPE, writer)

    else:
        raise Exception, "Unknown type "+str(ttype)

CPP_READ_MAP_DEFINITION = Template("""
uint32_t read_${suffix}("""+CPP_PROTOCOLP+""" iprot, """+CPP_TRANSPORTP+""" itrans, ${declaration}& value) {

   uint32_t count;
   ${keyType} key;
   ${valueType} elem;
   uint32_t xfer = 0;

   xfer += iprot->readU32(itrans, count);

   for(uint32_t ix = 0; ix < count; ix++) {
       ${keyReaderCall};
       ${valueReaderCall};
       value.insert(std::make_pair(key, elem));
   }

   return xfer;
}
""")
    
CPP_WRITE_MAP_DEFINITION = Template("""
uint32_t write_${suffix}("""+CPP_PROTOCOLP+""" oprot, """+CPP_TRANSPORTP+""" otrans, const ${declaration}& value) {

   uint32_t xfer = 0;

   xfer += oprot->writeU32(otrans, value.size());

   for(${declaration}::const_iterator ix = value.begin(); ix != value.end(); ++ix) {
       ${keyWriterCall};
       ${valueWriterCall};
   }
   return xfer;
}
""")
    
CPP_READ_LIST_DEFINITION = Template("""
uint32_t read_${suffix}("""+CPP_PROTOCOLP+""" iprot, """+CPP_TRANSPORTP+""" itrans, ${declaration}& value) {

   uint32_t count;
   ${valueType} elem;
   uint32_t xfer = 0;

   xfer+= iprot->readU32(itrans,  count);

   for(uint32_t ix = 0; ix < count; ix++) {
       ${valueReaderCall};
       value.${insert}(elem);
   }
   return xfer;
}
""")
    
CPP_WRITE_LIST_DEFINITION = Template("""
uint32_t write_${suffix}("""+CPP_PROTOCOLP+""" oprot, """+CPP_TRANSPORTP+""" otrans, const ${declaration}& value) {

   uint32_t xfer = 0;

   xfer+= oprot->writeU32(otrans, value.size());

   for(${declaration}::const_iterator ix = value.begin(); ix != value.end(); ++ix) {
       ${valueWriterCall};
   }
   return xfer;
}
""")
    
def toCollectionReaderDefinition(ttype):

    suffix = typeToIOMethodSuffix(ttype)

    if isinstance(ttype, MapType):
        keyReaderCall = toReaderCall("key", ttype.keyType)

    valueReaderCall= toReaderCall("elem", ttype.valueType)

    if isinstance(ttype, MapType):
        return CPP_READ_MAP_DEFINITION.substitute(suffix=suffix, declaration=typeToCTypeDeclaration(ttype),
                                                  keyType=typeToCTypeDeclaration(ttype.keyType),
                                                  keyReaderCall=keyReaderCall,
                                                  valueType=typeToCTypeDeclaration(ttype.valueType),
                                                  valueReaderCall=valueReaderCall)

    else:
	if isinstance(ttype, ListType):
	    insert="push_back"
	else:
	    insert="insert"

        return CPP_READ_LIST_DEFINITION.substitute(suffix=suffix, declaration=typeToCTypeDeclaration(ttype),
                                                   valueReaderCall=valueReaderCall,
                                                   valueType=typeToCTypeDeclaration(ttype.valueType),
						   insert=insert)


def toCollectionWriterDefinition(ttype):

    suffix = typeToIOMethodSuffix(ttype)

    if isinstance(ttype, MapType):
        keyWriterCall = toWriterCall("ix->first", ttype.keyType)
        valueWriterCall = toWriterCall("ix->second", ttype.valueType)

    else:
	valueWriterCall= toWriterCall("*ix", ttype.valueType)

    if isinstance(ttype, MapType):
        return CPP_WRITE_MAP_DEFINITION.substitute(suffix=suffix, declaration=typeToCTypeDeclaration(ttype),
                                                  keyType=typeToCTypeDeclaration(ttype.keyType),
                                                  keyWriterCall=keyWriterCall,
                                                  valueType=typeToCTypeDeclaration(ttype.valueType),
                                                  valueWriterCall=valueWriterCall)

    else:
        return CPP_WRITE_LIST_DEFINITION.substitute(suffix=suffix, declaration=typeToCTypeDeclaration(ttype),
                                                   valueWriterCall=valueWriterCall,
                                                   valueType=typeToCTypeDeclaration(ttype.valueType))


CPP_READ_STRUCT_DEFINITION = Template("""
uint32_t read_${suffix}("""+CPP_PROTOCOLP+""" iprot, """+CPP_TRANSPORTP+""" itrans, ${declaration}& value) {

    std::string name;
    """+CPP_PROTOCOL_TTYPE+""" type;
    int16_t id;
    uint32_t xfer = 0;

    xfer+= iprot->readStructBegin(itrans, name);

    while(true) {

        xfer+= iprot->readFieldBegin(itrans, name, type, id);

        if(type == """+CPP_PROTOCOL_TSTOP+""") {break;}

        switch(id) {
${fieldSwitch}
            default: xfer += iprot->skip(itrans, type); break;
	}

        xfer+= iprot->readFieldEnd(itrans);
    }

    xfer+= iprot->readStructEnd(itrans);

    return xfer;
}
""")
    
CPP_WRITE_FIELD_DEFINITION  = Template("""
    oprot->writeFieldBegin(otrans, \"${name}\", ${type}, ${id});
    ${fieldWriterCall};
    oprot->writeFieldEnd(otrans);
""")
    
CPP_WRITE_STRUCT_DEFINITION = Template("""
uint32_t write_${suffix}("""+CPP_PROTOCOLP+""" oprot, """+CPP_TRANSPORTP+""" otrans, const ${declaration}& value) {

    uint32_t xfer = 0;

    xfer+= oprot->writeStructBegin(otrans, \"${name}\");
${fieldWriterCalls}
    xfer+= oprot->writeFieldStop(otrans);
    xfer += oprot->writeStructEnd(otrans);
    return xfer;
}
""")
    
def toStructReaderDefinition(ttype):

    suffix = typeToIOMethodSuffix(ttype)

    # Sort field list in order of increasing ids

    fieldList = []
    fieldList+= ttype.fieldList

    fieldList.sort(lambda a,b: a.id - b.id)

    fieldSwitch=""

    for field in fieldList:
        fieldSwitch+= "            case "+str(field.id)+": "
        fieldSwitch+= toReaderCall("value."+field.name, field.type)+"; value.__isset."+field.name+" = true; break;\n"

    return CPP_READ_STRUCT_DEFINITION.substitute(suffix=suffix, declaration=typeToCTypeDeclaration(ttype), fieldSwitch=fieldSwitch)

def toStructWriterDefinition(ttype):

    suffix = typeToIOMethodSuffix(ttype)

    writeCalls = ""

    for field in ttype.fieldList:

	writeCalls+= CPP_WRITE_FIELD_DEFINITION.substitute(name=field.name, type=toWireType(field.type), id=field.id,
							   fieldWriterCall=toWriterCall("value."+field.name, field.type))
				   
    return CPP_WRITE_STRUCT_DEFINITION.substitute(name=ttype.name, suffix=suffix, declaration=typeToCTypeDeclaration(ttype), fieldWriterCalls=writeCalls)
    
def toReaderDefinition(ttype):
    if isinstance(ttype, CollectionType):
        return toCollectionReaderDefinition(ttype)

    elif isinstance(ttype, StructType):
        return toStructReaderDefinition(ttype)

    elif isinstance(ttype, TypedefType):
	return ""

    elif isinstance(ttype, EnumType):
	return ""

    else:
	raise Exception, "Unsupported type: "+str(ttype)

def toWriterDefinition(ttype):
    if isinstance(ttype, CollectionType):
        return toCollectionWriterDefinition(ttype)

    elif isinstance(ttype, StructType):
        return toStructWriterDefinition(ttype)

    elif isinstance(ttype, TypedefType):
	return ""

    elif isinstance(ttype, EnumType):
	return ""

    else:
	raise Exception, "Unsupported type: "+str(ttype)

def toOrderedIOList(ttype, result=None):
    if not result:
	result = []

    if ttype in result:
	return result

    elif isinstance(ttype, PrimitiveType):
	return result

    elif isinstance(ttype, CollectionType):

	if isinstance(ttype, MapType):
	    result = toOrderedIOList(ttype.keyType, result)

	result = toOrderedIOList(ttype.valueType, result)

	result.append(ttype)

    elif isinstance(ttype, StructType):
	for field in ttype.fieldList:
	    result = toOrderedIOList(field.type, result)
	result.append(ttype)

    elif isinstance(ttype, TypedefType):
	result.append(ttype)
	return result

    elif isinstance(ttype, EnumType):
	result.append(ttype)
	return result

    elif isinstance(ttype, Program):

	for struct in ttype.structMap.values():
	    result = toOrderedIOList(struct, result)

	for service in ttype.serviceMap.values():
	    result = toOrderedIOList(service, result)

    elif isinstance(ttype, Service):
	for function in ttype.functionList:
	    result = toOrderedIOList(function, result)

    elif isinstance(ttype, Function):
	result = toOrderedIOList(ttype.returnType(), result)

	# skip the args struct itself and just order the arguments themselves
	# we don't want the arg struct to be referred to until later, since we need to
	# inline those struct definitions with the implementation, not in the types header
	
	for field in ttype.args():
	    result = toOrderedIOList(field.type, result)

    else:
	raise Exception, "Unsupported thrift type: "+str(ttype)

    return result

def toIOMethodImplementations(program):
    
    # get ordered list of all types that need marshallers:

    iolist = toOrderedIOList(program)

    result = ""

    for ttype in iolist:
	result+= toReaderDefinition(ttype)
	result+= toWriterDefinition(ttype)

    # For all function argument lists, we need to create both struct definitions
    # and io methods.  We keep the struct definitions local, since they aren't part of the service API
    #
    # Note that we don't need to do a depth-first traverse of arg structs since they can only include fields
    # we've already seen

    for service in program.serviceMap.values():
	for function in service.functionList:
	    result+= toStructDefinition(function.argsStruct)
	    result+= toReaderDefinition(function.argsStruct)
	    result+= toWriterDefinition(function.argsStruct)
	    result+= toStructDefinition(function.resultStruct)
	    result+= toReaderDefinition(function.resultStruct)
	    result+= toWriterDefinition(function.resultStruct)

    return result;

def toImplementationSourceName(filename, genDir=None, debugp=None):

    if not genDir:
        genDir = toGenDir(filename)

    basename = toBasename(filename)

    result = os.path.join(genDir, basename+".cc")

    if debugp:
        debugp("toDefinitionHeaderName("+str(filename)+", "+str(genDir)+") => "+str(basename))

    return result

def writeImplementationSource(program, filename, genDir=None, debugp=None):

    implementationSource = toImplementationSourceName(filename, genDir)

    if debugp:
        debugp("implementationSource: "+str(implementationSource))

    cfile = CFile(implementationSource, "w")

    basename = toBasename(filename)

    cfile.writeln(CPP_IMPL_HEADER.substitute(source=basename, date=time.ctime()))

    cfile.write(toIOMethodImplementations(program))

    cfile.write(toServerDefinition(program))

    cfile.write(toClientDefinition(program))

    cfile.writeln(CPP_IMPL_FOOTER.substitute(source=basename))

    cfile.close()

class CPPGenerator(Generator):

    def __call__(self, program, filename, genDir=None, debugp=None):

        writeDefinitionHeader(program, filename, genDir, debugp)
        
        writeServicesHeader(program, filename, genDir, debugp)
        
        writeImplementationSource(program, filename, genDir, debugp)