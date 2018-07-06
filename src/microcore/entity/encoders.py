import json
from copy import copy
from json.encoder import JSONEncoder
from typing import Callable, Dict, List, Union

from aiohttp import web

from microcore.base.utils import FQN
from microcore.entity.model import JSON_TYPE_FIELD, public_attributes


class JSONEncoderBase(JSONEncoder):
    entity_type = type

    def default(self, o: object) -> dict:
        pass

    @classmethod
    def decoder_object_hook(cls, dct: dict):
        pass


class EncoderRegistry:
    _class_encoder_map = {}

    @classmethod
    def register_type_encoder(cls, typ: type, encoder: type):
        if not issubclass(encoder, JSONEncoderBase):
            raise TypeError('encoder should be subclass of %s' % JSONEncoderBase.__name__)
        if typ in cls._class_encoder_map:
            raise IndexError('encoder/decoder already registered')
        cls._class_encoder_map[typ] = encoder()

    @classmethod
    def get_encoder_for_type(cls, typ: type) -> JSONEncoderBase:
        if typ in cls._class_encoder_map:
            return cls._class_encoder_map[typ]
        raise TypeError('class [%s] has no encoder registered' % typ)


class _EncoderRegistryRegistrant(type):
    def __new__(mcs, name, bases, namespace, **kwargs):
        result = type.__new__(mcs, name, bases, namespace, **kwargs)
        if not isinstance(result, JSONEncoderBase.__class__):
            raise TypeError('metaclass %s can only be applied on subclasses of %s'
                            % (mcs, JSONEncoderBase))
        # noinspection PyTypeChecker
        EncoderRegistry.register_type_encoder(result.entity_type, result)
        return result


def register_encoder(cls):
    EncoderRegistry.register_type_encoder(cls.entity_type, cls)
    return cls


class EntityJSONEncoderBase(JSONEncoderBase):
    entity_type = type

    def default(self, o: object) -> dict:
        if isinstance(o, self.entity_type):
            dct = self.pack(o)
            dct[JSON_TYPE_FIELD] = FQN.get_fqn(self.entity_type)
            return dct
        return super().default(o)

    @classmethod
    def decoder_object_hook(cls, dct: dict) -> Union[dict, entity_type]:
        if dct.get(JSON_TYPE_FIELD) == FQN.get_fqn(cls.entity_type):
            dct.pop(JSON_TYPE_FIELD)
            return cls.unpack(dct, cls.entity_type)
        return dct

    @staticmethod
    def pack(o: entity_type) -> dict:
        return copy(o.__dict__)

    @staticmethod
    def unpack(dct: dict, cls: type) -> entity_type:
        return cls(**dct)


class StorageEntityJSONEncoderBase(EntityJSONEncoderBase):

    @staticmethod
    def unpack(dct: dict, cls: type) -> object:
        return cls(
            uid=dct.pop('_id'),
            **dct
        )

    @staticmethod
    def pack(o: object) -> dict:
        return {
            '_id': getattr(o, 'uid'),
            **public_attributes(o, exclude={'uid'})
        }


class RegisteredEntityJSONEncoderBase(EntityJSONEncoderBase, metaclass=_EncoderRegistryRegistrant):
    pass


class _OverridableEncoder(EncoderRegistry):
    def __init__(self, *, force_type_mapping=None, **kwargs):
        self.type_mapping = force_type_mapping or {}
        super().__init__(**kwargs)

    def _resolve_encoder(self, typ: type) -> JSONEncoderBase:
        return self.type_mapping.get(typ) or self.get_encoder_for_type(typ)


class ProxyJSONEncoder(_OverridableEncoder, JSONEncoder):
    def default(self, obj: object):
        if hasattr(obj, '__dict__'):  # instance of custom class, not built-in type
            dct = self._resolve_encoder(obj.__class__).default(obj)  # type: dict
            # self._walk_dict(dct, copy=False)
            dct[JSON_TYPE_FIELD] = FQN.get_fqn(obj)
            return dct
        return JSONEncoder.default(self, obj)

    def decoder_object_hook(self, dct: dict):
        type_pointer = dct.get(JSON_TYPE_FIELD)  # type: str
        if type_pointer is not None:
            type_ref = FQN.get_type(type_pointer)
            return self._resolve_encoder(type_ref).decoder_object_hook(dct)
        return dct


proxy_encoder_instance = ProxyJSONEncoder()


class ProxyNativeEncoder(ProxyJSONEncoder):
    def default(self, obj: object):
        if hasattr(obj, '__dict__'):  # instance of custom class, not built-in type
            dct = self._resolve_encoder(obj.__class__).default(obj)  # type: dict
            # foresee included types and encode them
            self._walk_dict(dct, _method=self.default, copy_dict=False, unpack=False)
            dct[JSON_TYPE_FIELD] = FQN.get_fqn(obj)
            return dct
        return obj

    def decoder_object_hook(self, dct: dict):
        type_pointer = dct.get(JSON_TYPE_FIELD)  # type: str
        if type_pointer is not None:
            type_ref = FQN.get_type(type_pointer)
            # foresee included types and decode them
            self._walk_dict(dct, _method=self.decoder_object_hook, copy_dict=False, unpack=False)
            return self._resolve_encoder(type_ref).decoder_object_hook(dct)
        return self._walk_dict(dct, _method=self.decoder_object_hook)

    def _walk_list(self, lst: list, _method: Callable):
        ret = []
        for val in lst:
            if hasattr(val, '__dict__'):
                ret.append(_method(val))
            elif isinstance(val, dict):
                ret.append(_method(val))
            elif isinstance(val, list):
                ret.append(self._walk_list(val, _method=_method))
            else:
                ret.append(val)
        return ret

    def _walk_dict(self, dct: dict, _method: Callable, copy_dict=True, unpack=True) -> dict:
        ret = {} if copy_dict else dct
        for key, val in dct.items():
            if hasattr(val, '__dict__') or (isinstance(val, dict) and val.get(JSON_TYPE_FIELD) is not None):
                ret[key] = _method(val)
            elif isinstance(val, dict):
                ret[key] = self._walk_dict(val, _method=_method)
            elif isinstance(val, list):
                ret[key] = self._walk_list(val, _method=_method)
            elif copy_dict:
                ret[key] = val
        if unpack and ret.get(JSON_TYPE_FIELD) is not None:
            return _method(ret)
        return ret

    def _walk_structure(self, data: Union[Dict, List], _method: Callable):
        if isinstance(data, dict):
            return self._walk_dict(data, _method=_method)
        elif isinstance(data, list):
            return self._walk_list(data, _method=_method)
        else:
            raise ValueError('input should be either dict or list')

    def dump(self, data: Union[Dict, List, object]):
        if not isinstance(data, (dict, list)):
            return self.default(data)
        return self._walk_structure(data, _method=self.default)

    def load(self, data: Union[Dict, List]):
        return self._walk_structure(data, _method=self.decoder_object_hook)


def json_response(fn):
    async def wrapper(*args, **kwargs):
        data = await fn(*args, **kwargs)
        if isinstance(data, web.Response):
            return data
        return web.Response(text=json.dumps(data, cls=ProxyJSONEncoder), content_type='application/json')

    return wrapper
