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

    Provides a fluent interface to set multiple fields on the `Properties`
    attribute of a given resource model, which is expected to be a subclass of
    `BaseResponseModel` parameterized with a Pydantic `BaseModel` for its properties.

    Type Parameters:
        ResourceModelT: A subclass of `BaseResponseModel` with properties of type `TProperties`.
        TProperties: A Pydantic `BaseModel` representing the resource's properties.

    Example:
        >>> builder = ModelBuilder(MyResourceModel(Type="...", Properties=MyProperties()))
        >>> resource = builder.with_data({"Name": "example", "Size": 42}).build()
    """

    def __init__(self, model: ResourceModelT) -> None:
        """
        Initialize the builder with a resource model instance.

        Args:
            model: An instance of a resource model to be built or modified.
        """
        self._model = model
        self._props_set = False

    def with_properties(self, data: dict[str, Any]) -> Self:
        """
        Set multiple fields in the resource's `Properties` attribute.

        Args:
            data: A dictionary of property names and their corresponding values to set.

        Returns:
            Self: The builder instance for method chaining.
        """

        # The inspector hands us a fresh model with no explicitly-set properties,
        # so build straight from ``data``. Only merge with the existing values on
        # the rare path where properties were already set.
        if self._model.Properties.__fields_set__:
            data = {**self._model.Properties.dict(exclude_unset=True), **data}
        self._model.Properties = type(self._model.Properties)(**data)
        self._props_set = True
        return self

    def with_extra_context(self, data: dict[str, Any]) -> Self:
        """
        Set enrichments for the resource model.
        """
        self._model.ExtraContext = self._model.ExtraContext.copy(update=data)
        return self

    def with_type(self, type: str) -> Self:
        """
        Set the type of the resource model.
        """
        self._model.Type = type
        return self

    def build(self) -> Dict[str, Any]:
        """
        Finalize and return the constructed resource model.

        Returns:
            Dict[str, Any]: The built resource model dictionary.
        """
        if not self._props_set:
            raise ValueError(
                "No data has been set for the resource model, use `with_data` to set data."
            )

        return _to_jsonable(self._model.dict(exclude_unset=True, by_alias=True))
