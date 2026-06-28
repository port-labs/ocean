from datetime import date, datetime
from typing import Any, Dict, Self

from pydantic.v1 import BaseModel
from pydantic.v1.json import pydantic_encoder

from aws.core.modeling.resource_models import ResourceModel

_JSON_NATIVE = (str, int, float, bool, type(None))


def _to_jsonable(value: Any) -> Any:
    """Convert non-JSON-native leaves in a ``.dict()`` result to JSON values.

    Same output as the old ``json.loads(model.json(...))`` round-trip, but for a
    fraction of the CPU: ``.dict()`` hands us a freshly-built structure we
    exclusively own, so dicts/lists are rewritten in place (no parallel copy)
    and only non-native leaves (``datetime``, ``Decimal``, enums, ...) allocate.
    Native leaves are skipped before recursing to avoid the call overhead.
    """
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(item, _JSON_NATIVE):
                value[key] = _to_jsonable(item)
        return value
    if isinstance(value, list):
        for index, item in enumerate(value):
            if not isinstance(item, _JSON_NATIVE):
                value[index] = _to_jsonable(item)
        return value
    if isinstance(value, tuple):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return pydantic_encoder(value)


class ResourceBuilder[ResourceModelT: ResourceModel[BaseModel], TProperties: BaseModel]:
    """
    Builder class for constructing AWS resource models with strongly-typed properties.

    Provides a fluent interface to collect the resource's `Type`, `Properties`
    and extra context, then constructs the model in a single pass at `build`.
    Deferring construction lets us validate `Properties` exactly once per
    resource, instead of instantiating an empty default model up front and
    immediately discarding it.

    Type Parameters:
        ResourceModelT: A subclass of `ResourceModel` with properties of type `TProperties`.
        TProperties: A Pydantic `BaseModel` representing the resource's properties.

    Example:
        >>> builder = ResourceBuilder(MyResourceModel)
        >>> resource = builder.with_properties({"Name": "example", "Size": 42}).build()
    """

    def __init__(self, model_cls: type[ResourceModelT]) -> None:
        """
        Initialize the builder for a resource model class.

        Args:
            model_cls: The resource model class to construct on `build`.
        """
        self._model_cls = model_cls
        self._properties: dict[str, Any] | None = None
        self._type: str | None = None
        self._extra_context: dict[str, Any] | None = None

    def with_properties(self, data: dict[str, Any]) -> Self:
        """
        Set the fields of the resource's `Properties`.

        Repeated calls merge, with later values taking precedence.

        Args:
            data: A dictionary of property names and their corresponding values to set.

        Returns:
            Self: The builder instance for method chaining.
        """
        self._properties = (
            data if self._properties is None else {**self._properties, **data}
        )
        return self

    def with_extra_context(self, data: dict[str, Any]) -> Self:
        """
        Set enrichments for the resource model.
        """
        self._extra_context = (
            data if self._extra_context is None else {**self._extra_context, **data}
        )
        return self

    def with_type(self, type: str) -> Self:
        """
        Set the type of the resource model.
        """
        self._type = type
        return self

    def build(self) -> Dict[str, Any]:
        """
        Construct the resource model in a single validation pass and return it
        as a JSON-native dict.

        Returns:
            Dict[str, Any]: The built resource model dictionary.
        """
        if self._properties is None:
            raise ValueError(
                "No data has been set for the resource model, use `with_properties` to set data."
            )

        # Supplying ``Properties`` directly skips the model's empty default
        # factory and validates the payload exactly once.
        fields: dict[str, Any] = {"Properties": self._properties}
        if self._type is not None:
            fields["Type"] = self._type
        model = self._model_cls(**fields)

        if self._extra_context:
            model.ExtraContext = model.ExtraContext.copy(update=self._extra_context)

        return _to_jsonable(model.dict(exclude_unset=True, by_alias=True))
