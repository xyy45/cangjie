"""Lossless display text beside typed evidence; never changes stored facts."""
import json
from nexus.repair import values,object_values


def display_primitive(value):
    if type(value) in (int,bool,str):return True
    if type(value) is dict:
        # Display-only bounded shape check; never authorizes an object type.
        try:object_values.typed_key(value)
        except ValueError:return False
        return True
    if type(value) is not list:return False
    try:values.array(value)
    except ValueError:return False
    return True


def primitive_text(value):
    if isinstance(value,list):return [primitive_text(item) for item in value]
    if not isinstance(value,dict):return value
    result={key:primitive_text(item) for key,item in value.items()}
    text=lambda item:json.dumps(item,ensure_ascii=False,separators=(',',':'))
    for name in ('actual_return','actual_value','expected_value','initial_state','before_state','reference_before','expected_state','left_actual_return','right_actual_return'):
        if display_primitive(value.get(name)):result[name+'_text']=text(value[name])
    for name in ('args','context','left_args','right_args'):
        vector=value.get(name)
        if type(vector) is list and all(display_primitive(item) for item in vector):result[name+'_text']=text(vector)
    return result
