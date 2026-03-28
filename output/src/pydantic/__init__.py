"""Lightweight local subset of the pydantic API used by this project.

This compatibility module exists so the project can run in environments where
the external ``pydantic`` package is unavailable.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, ClassVar, get_args, get_origin, get_type_hints


class ValidationError(ValueError):
    """Validation error raised when model parsing fails."""


class _UndefinedType:
    """Sentinel type used to mark missing defaults."""


PydanticUndefined = _UndefinedType()


@dataclass(frozen=True)
class FieldInfo:
    """Field metadata used by ``Field`` during model validation."""

    default: Any = PydanticUndefined
    ge: float | None = None
    le: float | None = None
    min_length: int | None = None


def Field(
    default: Any = PydanticUndefined,
    *,
    ge: float | None = None,
    le: float | None = None,
    min_length: int | None = None,
) -> FieldInfo:
    """Create field metadata for declarative validation constraints."""
    return FieldInfo(default=default, ge=ge, le=le, min_length=min_length)


class ConfigDict(dict[str, Any]):
    """Dictionary type used for model configuration values."""


def model_validator(*, mode: str) -> Any:
    """Decorator to register model-level validators."""

    if mode != "after":
        msg = "Only model_validator(mode='after') is supported"
        raise NotImplementedError(msg)

    def decorator(func: Any) -> Any:
        setattr(func, "__model_validator_mode__", mode)
        return func

    return decorator


def _is_optional_type(expected_type: Any) -> bool:
    """Return ``True`` when the annotation is ``X | None`` or ``Optional[X]``."""
    return type(None) in get_args(expected_type)


def _strip_optional(expected_type: Any) -> Any:
    """Return the non-None branch from an optional union annotation."""
    return next(arg for arg in get_args(expected_type) if arg is not type(None))


def _dump_value(value: Any, *, mode: str) -> Any:
    """Serialize nested values recursively for ``model_dump``."""
    if isinstance(value, BaseModel):
        return value.model_dump(mode=mode)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, tuple):
        return [_dump_value(item, mode=mode) for item in value]
    if isinstance(value, list):
        return [_dump_value(item, mode=mode) for item in value]
    if isinstance(value, dict):
        return {key: _dump_value(item, mode=mode) for key, item in value.items()}
    return value


class BaseModel:
    """Minimal pydantic-like base model with strict field validation."""

    model_config: ClassVar[ConfigDict] = ConfigDict()
    __field_hints__: ClassVar[dict[str, Any]]
    __field_infos__: ClassVar[dict[str, FieldInfo]]
    __model_validators__: ClassVar[tuple[str, ...]]

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Resolve type hints and validator metadata for subclasses."""
        super().__init_subclass__(**kwargs)
        resolved_hints = get_type_hints(cls)
        cls.__field_hints__ = {
            name: annotation
            for name, annotation in resolved_hints.items()
            if not name.startswith("__") and get_origin(annotation) is not ClassVar
        }

        field_infos: dict[str, FieldInfo] = {}
        for field_name in cls.__field_hints__:
            default = cls.__dict__.get(field_name, PydanticUndefined)
            if isinstance(default, FieldInfo):
                field_infos[field_name] = default
            elif default is not PydanticUndefined:
                field_infos[field_name] = FieldInfo(default=default)
        cls.__field_infos__ = field_infos

        validator_names: list[str] = []
        for name, value in cls.__dict__.items():
            if callable(value) and getattr(value, "__model_validator_mode__", None) == "after":
                validator_names.append(name)
        cls.__model_validators__ = tuple(validator_names)

    def __init__(self, **data: Any) -> None:
        """Validate constructor inputs and assign normalized model attributes."""
        validated = self._validate_dict(data)
        for key, value in validated.items():
            object.__setattr__(self, key, value)
        self._run_model_validators()

    @classmethod
    def model_validate(cls, obj: Any) -> BaseModel:
        """Validate and parse input data into a model instance."""
        if isinstance(obj, cls):
            return obj
        if not isinstance(obj, dict):
            msg = f"{cls.__name__} requires a dict input"
            raise ValidationError(msg)
        return cls(**obj)

    def model_dump(self, *, mode: str = "python") -> dict[str, Any]:
        """Return a recursive plain-data dump of model fields."""
        dumped: dict[str, Any] = {}
        for field_name in self.__class__.__field_hints__:
            dumped[field_name] = _dump_value(getattr(self, field_name), mode=mode)
        return dumped

    @classmethod
    def _validate_dict(cls, data: dict[str, Any]) -> dict[str, Any]:
        """Validate a raw input dict against the class field definitions."""
        config = cls.model_config
        if config.get("extra") == "forbid":
            extras = set(data) - set(cls.__field_hints__)
            if extras:
                msg = f"Extra fields not permitted: {', '.join(sorted(extras))}"
                raise ValidationError(msg)

        validated: dict[str, Any] = {}
        for field_name, expected_type in cls.__field_hints__.items():
            has_value = field_name in data
            field_info = cls.__field_infos__.get(field_name, FieldInfo())
            if not has_value:
                if field_info.default is PydanticUndefined:
                    msg = f"Field required: {field_name}"
                    raise ValidationError(msg)
                validated[field_name] = field_info.default
                continue
            raw_value = data[field_name]
            try:
                parsed_value = cls._parse_value(
                    raw_value,
                    expected_type,
                    field_info=field_info,
                    strip_strings=bool(config.get("str_strip_whitespace", False)),
                )
            except ValidationError:
                raise
            except Exception as exc:  # pragma: no cover - defensive fallback.
                raise ValidationError(str(exc)) from exc
            validated[field_name] = parsed_value
        return validated

    @classmethod
    def _parse_value(
        cls,
        raw_value: Any,
        expected_type: Any,
        *,
        field_info: FieldInfo,
        strip_strings: bool,
    ) -> Any:
        """Parse a raw field value using supported annotation kinds."""
        if _is_optional_type(expected_type):
            if raw_value is None:
                return None
            expected_type = _strip_optional(expected_type)

        origin = get_origin(expected_type)
        if origin is tuple:
            args = get_args(expected_type)
            if len(args) != 2 or args[1] is not Ellipsis:
                msg = "Only tuple[T, ...] is supported"
                raise ValidationError(msg)
            item_type = args[0]
            if not isinstance(raw_value, (list, tuple)):
                msg = "Expected list/tuple value"
                raise ValidationError(msg)
            parsed_items = tuple(
                cls._parse_value(
                    item,
                    item_type,
                    field_info=FieldInfo(),
                    strip_strings=strip_strings,
                )
                for item in raw_value
            )
            return parsed_items

        if isinstance(expected_type, type) and issubclass(expected_type, Enum):
            try:
                return expected_type(raw_value)
            except Exception as exc:
                raise ValidationError(str(exc)) from exc

        if isinstance(expected_type, type) and issubclass(expected_type, BaseModel):
            if isinstance(raw_value, expected_type):
                return raw_value
            if not isinstance(raw_value, dict):
                msg = f"Expected dict for nested {expected_type.__name__}"
                raise ValidationError(msg)
            return expected_type.model_validate(raw_value)

        if expected_type is str:
            if not isinstance(raw_value, str):
                msg = "Expected string value"
                raise ValidationError(msg)
            parsed_str = raw_value.strip() if strip_strings else raw_value
            if field_info.min_length is not None and len(parsed_str) < field_info.min_length:
                msg = f"String shorter than min_length={field_info.min_length}"
                raise ValidationError(msg)
            return parsed_str

        if expected_type is int:
            if isinstance(raw_value, bool) or not isinstance(raw_value, int):
                msg = "Expected int value"
                raise ValidationError(msg)
            cls._validate_numeric_bounds(raw_value, field_info)
            return raw_value

        if expected_type is float:
            if isinstance(raw_value, bool) or not isinstance(raw_value, (int, float)):
                msg = "Expected float value"
                raise ValidationError(msg)
            parsed_float = float(raw_value)
            cls._validate_numeric_bounds(parsed_float, field_info)
            return parsed_float

        if expected_type is bool:
            if not isinstance(raw_value, bool):
                msg = "Expected bool value"
                raise ValidationError(msg)
            return raw_value

        if raw_value is None and expected_type is type(None):
            return None

        if not isinstance(raw_value, expected_type):
            msg = f"Expected {expected_type!r} value"
            raise ValidationError(msg)
        return raw_value

    @staticmethod
    def _validate_numeric_bounds(value: float, field_info: FieldInfo) -> None:
        """Validate ``ge`` and ``le`` constraints for numeric values."""
        if field_info.ge is not None and value < field_info.ge:
            msg = f"Value must be >= {field_info.ge}"
            raise ValidationError(msg)
        if field_info.le is not None and value > field_info.le:
            msg = f"Value must be <= {field_info.le}"
            raise ValidationError(msg)

    def _run_model_validators(self) -> None:
        """Run registered ``model_validator(mode='after')`` hooks."""
        for validator_name in self.__class__.__model_validators__:
            validator = getattr(self, validator_name)
            try:
                validator()
            except ValidationError:
                raise
            except ValueError as exc:
                raise ValidationError(str(exc)) from exc
