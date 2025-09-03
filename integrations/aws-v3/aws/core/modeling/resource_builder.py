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
        >>> builder = ResourceBuilder(MyResourceModel(Type="...", Properties=MyProperties()), "eu-west-1", "123456789")
        >>> resource = builder.with_properties([{"Name": "example"}, {"Tags": [{"Key": "Env", "Value": "prod"}]}]).with_metadata({"__Kind": "AWS::S3::Bucket"}).build()
    """

    def __init__(self, model: ResourceModelT, region: str, account_id: str) -> None:
        """
        Initialize the builder with a resource model instance and context.

        Args:
            model: An instance of a resource model to be built or modified.
            region: The AWS region for this resource.
            account_id: The AWS account ID for this resource.
        """
        self._model = model
        self._region = region
        self._account_id = account_id

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
        current_data = self._model.dict()
        updated_data = {**current_data, **data}

        self._model = self._model.__class__(**updated_data)
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

        self._model.account_id = self._account_id
        self._model.region = self._region

        return self._model
