from typing import Any, Self
from aws.core.modeling.resource_models import ResourceModel
from pydantic import BaseModel
from typing import Dict


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

    def with_properties(self, data: dict[str, Any]) -> Self:
        """
        Set multiple fields in the resource's `Properties` attribute.

        Args:
            data: A dictionary of property names and their corresponding values to set.

        Returns:
            Self: The builder instance for method chaining.
        """

        current_data = self._model.Properties.dict(exclude_unset=True)
        current_data.update(data)
        self._model.Properties = type(self._model.Properties)(**current_data)
        self._props_set = True
        return self

    def with_extra_context(self, data: dict[str, Any]) -> Self:
        """
        Set enrichments for the resource model.
        """
        self._model.ExtraContext = self._model.ExtraContext.copy(
            update=data, include=data.keys()
        )
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
        resource = self._model.dict(exclude_unset=True, by_alias=True)
        return resource
