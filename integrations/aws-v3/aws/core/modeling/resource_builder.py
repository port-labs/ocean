from typing import Self, List, Any, Dict
from aws.core.modeling.resource_models import ResourceModel
from pydantic import BaseModel


# We use ResourceMetadata from resource_models instead of duplicating here


class ResourceBuilder[ResourceModelT: ResourceModel[BaseModel], TProperties: BaseModel]:
    """
    Builder class for constructing AWS resource models with strongly-typed properties and metadata.

    Provides a fluent interface to set multiple fields on the `Properties`
    attribute of a given resource model, which is expected to be a subclass of
    `BaseResponseModel` parameterized with a Pydantic `BaseModel` for its properties.

    Type Parameters:
        ResourceModelT: A subclass of `BaseResponseModel` with properties of type `TProperties`.
        TProperties: A Pydantic `BaseModel` representing the resource's properties.

    Example:
        >>> builder = ResourceBuilder(MyResourceModel(Type="...", Properties=MyProperties()))
        >>> resource = builder.with_properties([{"Name": "example"}, {"Tags": [{"Key": "Env", "Value": "prod"}]}]).with_metadata({"__Kind": "AWS::S3::Bucket"}).build()
    """

    def __init__(self, model: ResourceModelT) -> None:
        """
        Initialize the builder with a resource model instance.

        Args:
            model: An instance of a resource model to be built or modified.
        """
        self._model = model
        self._props_set = False

    def with_properties(self, properties: List[Dict[str, Any]]) -> Self:
        """
        Set properties in the resource's `Properties` attribute.
        Merges multiple property dictionaries into the model.

        Args:
            properties: A list of property dictionaries to merge.

        Returns:
            Self: The builder instance for method chaining.
        """
        all_properties: dict[str, Any] = {}
        for props in properties:
            if props:
                all_properties.update(props)

        if all_properties:
            for key, value in all_properties.items():
                setattr(self._model.Properties, key, value)
            self._props_set = True

        return self

    def with_metadata(self, data: Dict[str, Any]) -> Self:
        """
        Set metadata fields on the resource with type safety.

        Args:
            data: A dictionary of metadata fields and their corresponding values to set.

        Returns:
            Self: The builder instance for method chaining.
        """
        for key, value in data.items():
            setattr(self._model, key, value)
        return self

    def build(self) -> ResourceModelT:
        """
        Finalize and return the constructed resource model.

        Returns:
            ResourceModelT: The built resource model instance.
        """
        if not self._props_set:
            raise ValueError(
                "No data has been set for the resource model, use `with_properties` to set data."
            )

        return self._model
