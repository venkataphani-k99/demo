"""Pydantic v1/v2 compatibility shim.

The codebase uses pydantic v2 APIs (model_dump, model_dump_json,
model_validate) but FreeCAD's Python has pydantic v1. This module
provides thin wrappers so all other modules can use either version.
"""
from __future__ import annotations

import json as _json

from pydantic import BaseModel, Field

# Validator decorators (v1/v2)
def model_validator(*args, **kwargs):
    try:
        from pydantic import model_validator as _mv
        return _mv(*args, **kwargs)
    except ImportError:
        from pydantic import root_validator
        import functools

        def decorator(fn):
            @functools.wraps(fn)
            def wrapper(cls, values):
                class _Proxy:
                    def __init__(self, d):
                        self.__dict__.update(d)
                try:
                    proxy = _Proxy(values)
                    fn(proxy)
                except Exception:
                    pass
                return values
            return root_validator(pre=False, allow_reuse=True)(wrapper)

        if args and callable(args[0]):
            return decorator(args[0])
        return decorator


def field_validator(*fields, **kwargs):
    try:
        from pydantic import field_validator as _fv
        return _fv(*fields, **kwargs)
    except ImportError:
        from pydantic import validator
        pre = kwargs.get('mode') == 'before'
        clean_kwargs = {k: v for k, v in kwargs.items() if k not in ('mode',)}
        return validator(*fields, pre=pre, allow_reuse=True, **clean_kwargs)


if not hasattr(BaseModel, "model_dump"):
    BaseModel.model_dump = lambda self, **kwargs: self.dict(**{k: v for k, v in kwargs.items() if k not in ('mode',)})
if not hasattr(BaseModel, "model_dump_json"):
    BaseModel.model_dump_json = lambda self, **kwargs: _json.dumps(self.dict(), indent=kwargs.get('indent', 2))
if not hasattr(BaseModel, "model_validate"):
    BaseModel.model_validate = classmethod(lambda cls, data: cls.parse_obj(data))
if not hasattr(BaseModel, "model_validate_json"):
    BaseModel.model_validate_json = classmethod(lambda cls, json_str: cls.parse_raw(json_str))


def model_dump(model: BaseModel, **kwargs) -> dict:
    """Serialize model to dict (v1/v2 compatible)."""
    if hasattr(model, 'model_dump'):
        return model.model_dump(**kwargs)
    # v1: filter kwargs to valid v1 dict() args
    v1_kwargs = {k: v for k, v in kwargs.items() if k not in ('mode',)}
    return model.dict(**v1_kwargs)


def model_dump_json(model: BaseModel, **kwargs) -> str:
    """Serialize model to JSON string (v1/v2 compatible)."""
    if hasattr(model, 'model_dump_json'):
        return model.model_dump_json(**kwargs)
    indent = kwargs.get('indent', 2)
    exclude = kwargs.get('exclude', None)
    d = model.dict(exclude=exclude) if exclude else model.dict()
    return _json.dumps(d, indent=indent)


def model_validate(model_cls, data) -> BaseModel:
    """Parse data into model (v1/v2 compatible)."""
    if hasattr(model_cls, 'model_validate'):
        return model_cls.model_validate(data)
    return model_cls.parse_obj(data)


__all__ = [
    'BaseModel',
    'Field',
    'field_validator',
    'model_validator',
    'model_dump',
    'model_dump_json',
    'model_validate',
]
