from typing import Any, Dict, Self


from aws.core.modeling.resource_models import ResourceModel


class ResourceBuilder[ResourceModelT: ResourceModel[Any]]:
    """
    Builder class for constructing AWS resource models with strongly-typed properties.

    Provides a fluent interface to collect the resource's `Type`, `Properties`
    and extra context, then constructs the model in a single pass at `build`.

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

        Args:
            data: A dictionary of property names and their corresponding values to set.

        Returns:
            Self: The builder instance for method chaining.
        """
        self._properties = data
        return self

    def with_extra_context(self, data: dict[str, Any]) -> Self:
        """
        Set enrichments for the resource model.
        """
        self._extra_context = data
        return self

    def with_type(self, type: str) -> Self:
        """
        Set the type of the resource model.
        """
        self._type = type
        return self

    def build(self) -> Dict[str, Any]:
        """
        Finalize and return the constructed resource model.

        Returns:
            Dict[str, Any]: The built resource model dictionary.
        """
        # Explicitly set ``Type`` so it survives ``exclude_unset=True``.
        fields: dict[str, Any] = {
            "Type": self._type,
            "Properties": self._properties,
        }

        if self._extra_context:
            fields["ExtraContext"] = self._extra_context

        model = self._model_cls(**fields)

        return model.model_dump(mode="json", exclude_unset=True, by_alias=True)
