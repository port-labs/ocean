from typing import Self, TypedDict, List
from aws.core.modeling.resource_models import ResourceModel
from pydantic import BaseModel


class PropertiesData(TypedDict, total=False):
    """Type-safe properties data"""

    pass  # Will be extended by specific resource types


class MetadataData(TypedDict, total=False):
    """Type-safe metadata data"""

    __Region: str
    __AccountId: str
    __Kind: str


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

    def with_properties(self, properties: List[PropertiesData]) -> Self:
        """
        Set properties in the resource's `Properties` attribute.
        Merges multiple property dictionaries into the model.

        Args:
            properties: A list of property dictionaries to merge.

        Returns:
            Self: The builder instance for method chaining.
        """
        all_properties = {}
        for props in properties:
            if props:
                all_properties.update(props)

        if all_properties:
            current_properties = self._model.Properties.dict()
            updated_properties = {**current_properties, **all_properties}

            self._model.Properties = self._model.Properties.__class__(
                **updated_properties
            )
            self._props_set = True

        return self

    def with_metadata(self, data: MetadataData) -> Self:
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

        return self._model.copy(
            update={"__Region": self._region, "__AccountId": self._account_id}
        )
