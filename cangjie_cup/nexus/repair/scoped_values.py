"""V5 wire data: canonical nominal tags with unchanged bounded leaf codecs."""
from nexus.projects.names import symbol_name
from nexus.repair import object_values,object_trace,values

PROTOCOLS={kind:('NEXUS_'+prefix+'_V5|',name+'V5') for kind,prefix,name in (
    ('oracle','ORACLE','NexusOracle'),('single','PROPERTY','NexusProperties'),('relation','RELATION','NexusRelations'))}
SEQUENCE='NEXUS_SEQUENCE_V5|'
END='NEXUS_SEQUENCE_END_V5|'
ERROR='NEXUS_VALUE_ERROR_V5|'
PREFIXES=tuple(p[0] for p in PROTOCOLS.values())+(SEQUENCE,END,ERROR)
MAX_WIRE=2333


def _types(raw):
    result=object_values.registry(raw)
    for identifier in result:symbol_name(identifier)
    return result


def encode(value,kind,types):
    declarations=_types(types);values.primitive(value,kind,declarations)
    result=object_trace.encode(value,kind,declarations)
    if len(result)>MAX_WIRE:raise ValueError('V5观测超过有界编码容量')
    return result


def decode(text,kind,types):
    return object_trace._decode(text,kind,_types(types),MAX_WIRE)
