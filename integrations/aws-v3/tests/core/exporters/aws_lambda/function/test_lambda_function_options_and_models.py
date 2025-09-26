import pytest
from pydantic import ValidationError

from aws.core.exporters.aws_lambda.function.models import (
    LambdaFunction,
    LambdaFunctionProperties,
    SingleLambdaFunctionRequest,
    PaginatedLambdaFunctionRequest,
)


class TestSingleLambdaFunctionRequest:

    def test_initialization_with_required_fields(self) -> None:
        """Test initialization with required fields only."""
        options = SingleLambdaFunctionRequest(
            region="us-west-2", account_id="123456789012", function_name="test-function"
        )
        assert options.region == "us-west-2"
        assert options.account_id == "123456789012"
        assert options.function_name == "test-function"
        assert options.include == []

    def test_initialization_with_all_fields(self) -> None:
        """Test initialization with all fields."""
        include_list = ["ListFunctionsAction"]
        options = SingleLambdaFunctionRequest(
            region="eu-central-1",
            account_id="123456789012",
            function_name="test-function",
            include=include_list,
        )
        assert options.region == "eu-central-1"
        assert options.account_id == "123456789012"
        assert options.function_name == "test-function"
        assert options.include == include_list

    def test_missing_required_region(self) -> None:
        """Test validation error when region is missing."""
        with pytest.raises(ValidationError) as exc_info:
            SingleLambdaFunctionRequest(
                account_id="123456789012", function_name="test-function"
            )  # type: ignore
        assert "region" in str(exc_info.value)

    def test_missing_required_function_name(self) -> None:
        """Test validation error when function_name is missing."""
        with pytest.raises(ValidationError) as exc_info:
            SingleLambdaFunctionRequest(
                region="us-east-1", account_id="123456789012"
            )  # type: ignore
        assert "function_name" in str(exc_info.value)

    def test_empty_include_list(self) -> None:
        """Test initialization with empty include list."""
        options = SingleLambdaFunctionRequest(
            region="us-east-1",
            account_id="123456789012",
            function_name="test-function",
            include=[],
        )
        assert options.region == "us-east-1"
        assert options.include == []

    def test_include_list_validation(self) -> None:
        """Test include list with multiple actions."""
        options = SingleLambdaFunctionRequest(
            region="ap-southeast-1",
            account_id="123456789012",
            function_name="test-function",
            include=["ListFunctionsAction", "GetFunctionAction"],
        )
        assert len(options.include) == 2
        assert "ListFunctionsAction" in options.include
        assert "GetFunctionAction" in options.include


class TestPaginatedLambdaFunctionRequest:

    def test_inheritance(self) -> None:
        """Test that PaginatedLambdaFunctionRequest inherits properly."""
        options = PaginatedLambdaFunctionRequest(
            region="us-west-2", account_id="123456789012"
        )
        assert isinstance(options, PaginatedLambdaFunctionRequest)

    def test_initialization_with_required_fields(self) -> None:
        """Test initialization with required fields only."""
        options = PaginatedLambdaFunctionRequest(
            region="us-east-1", account_id="123456789012"
        )
        assert options.region == "us-east-1"
        assert options.account_id == "123456789012"
        assert options.include == []

    def test_initialization_with_include(self) -> None:
        """Test initialization with include actions."""
        include_list = ["ListFunctionsAction"]
        options = PaginatedLambdaFunctionRequest(
            region="ap-southeast-2", account_id="123456789012", include=include_list
        )
        assert options.region == "ap-southeast-2"
        assert options.account_id == "123456789012"
        assert options.include == include_list


class TestLambdaFunctionProperties:

    def test_initialization_empty(self) -> None:
        """Test initialization with default values."""
        properties = LambdaFunctionProperties()
        assert properties.FunctionName == ""
        assert properties.FunctionArn == ""
        assert properties.Runtime == ""
        assert properties.Handler == ""
        assert properties.MemorySize == 128
        assert properties.Timeout == 3
        assert properties.State == ""
        assert properties.LastModified == ""

    def test_initialization_with_properties(self) -> None:
        """Test initialization with specific properties."""
        properties = LambdaFunctionProperties(
            FunctionName="test-function",
            FunctionArn="arn:aws:lambda:us-east-1:123456789012:function:test-function",
            Runtime="python3.9",
            Handler="index.handler",
            MemorySize=512,
            Timeout=30,
            State="Active",
            LastModified="2023-12-01T10:30:00.000+0000",
            Tags=[{"Key": "Environment", "Value": "test"}],
        )
        assert properties.FunctionName == "test-function"
        assert (
            properties.FunctionArn
            == "arn:aws:lambda:us-east-1:123456789012:function:test-function"
        )
        assert properties.Runtime == "python3.9"
        assert properties.Handler == "index.handler"
        assert properties.MemorySize == 512
        assert properties.Timeout == 30
        assert properties.State == "Active"
        assert properties.LastModified == "2023-12-01T10:30:00.000+0000"
        assert properties.Tags == [{"Key": "Environment", "Value": "test"}]

    def test_dict_exclude_none(self) -> None:
        """Test dict serialization with exclude_none=True."""
        properties = LambdaFunctionProperties(
            FunctionName="test-function",
            Runtime="python3.9",
            Tags=[{"Key": "Project", "Value": "demo"}],
        )
        result = properties.dict(exclude_none=True)
        assert result["FunctionName"] == "test-function"
        assert result["Runtime"] == "python3.9"
        assert result["Tags"] == [{"Key": "Project", "Value": "demo"}]
        # MemorySize is included because it has a default value, not None
        assert "MemorySize" in result
        assert result["MemorySize"] == 128

    def test_all_properties_assignment(self) -> None:
        """Test assignment of all available properties."""
        properties = LambdaFunctionProperties(
            FunctionName="comprehensive-function",
            FunctionArn="arn:aws:lambda:us-east-1:123456789012:function:comprehensive-function",
            Runtime="python3.9",
            Handler="main.handler",
            MemorySize=1024,
            Timeout=60,
            State="Active",
            LastModified="2023-12-01T10:30:00.000+0000",
            CodeSha256="abcd1234efgh5678ijkl9012mnop3456qrst7890uvwx1234yzab5678cdef",
            CodeSize=2048000,
            Description="A comprehensive test function",
            Role="arn:aws:iam::123456789012:role/lambda-execution-role",
            LastUpdateStatus="Successful",
            LastUpdateStatusReason="The function was successfully updated",
            LastUpdateStatusReasonCode="Successful",
            Version="$LATEST",
            RevisionId="12345678-1234-1234-1234-123456789012",
            PackageType="Zip",
            MasterArn=None,
            SigningJobArn=None,
            SigningProfileVersionArn=None,
            StateReason="The function is ready",
            StateReasonCode="OK",
            DeadLetterConfig={"TargetArn": "arn:aws:sqs:us-east-1:123456789012:my-dlq"},
            Environment={"Variables": {"ENV_VAR_1": "value1"}},
            VpcConfig={"VpcId": "vpc-12345678", "SubnetIds": ["subnet-12345678"]},
            TracingConfig={"Mode": "Active"},
            LoggingConfig={"LogFormat": "Text", "ApplicationLogLevel": "INFO"},
            EphemeralStorage={"Size": {"Size": 10240}},
            ImageConfigResponse={"ImageConfig": {"Command": ["python", "app.py"]}},
            RuntimeVersionConfig={
                "RuntimeVersionArn": "arn:aws:lambda:us-east-1::runtime:python3.9"
            },
            SnapStart={"ApplyOn": "PublishedVersions", "OptimizationStatus": "On"},
            Layers=[{"Arn": "arn:aws:lambda:us-east-1:123456789012:layer:my-layer:1"}],
            Architectures=["x86_64"],
            FileSystemConfigs=[
                {
                    "Arn": "arn:aws:elasticfilesystem:us-east-1:123456789012:access-point/fsap-12345678"
                }
            ],
            Tags=[{"Key": "Name", "Value": "test-function"}],
            KmsKeyArn="arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012",
        )

        # Verify key properties
        assert properties.FunctionName == "comprehensive-function"
        assert properties.Runtime == "python3.9"
        assert properties.MemorySize == 1024
        assert properties.Tags == [{"Key": "Name", "Value": "test-function"}]

    def test_aliases_work_correctly(self) -> None:
        """Test that field aliases work correctly."""
        properties = LambdaFunctionProperties(
            KmsKeyArn="arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012",
        )

        # Test that aliases are used in serialization
        result = properties.dict(by_alias=True)
        assert "KMSKeyArn" in result

        # Test that field names work in direct access
        assert (
            properties.KmsKeyArn
            == "arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012"
        )


class TestLambdaFunction:

    def test_initialization_with_identifier(self) -> None:
        """Test initialization with just an identifier."""
        lambda_function = LambdaFunction(
            Properties=LambdaFunctionProperties(FunctionName="test-function")
        )
        assert lambda_function.Type == "AWS::Lambda::Function"
        assert lambda_function.Properties.FunctionName == "test-function"

    def test_initialization_with_properties(self) -> None:
        """Test initialization with full properties."""
        properties = LambdaFunctionProperties(
            FunctionName="test-function",
            Runtime="python3.9",
            Handler="index.handler",
            MemorySize=512,
        )
        lambda_function = LambdaFunction(Properties=properties)
        assert lambda_function.Properties == properties
        assert lambda_function.Properties.FunctionName == "test-function"
        assert lambda_function.Properties.Runtime == "python3.9"
        assert lambda_function.Properties.Handler == "index.handler"
        assert lambda_function.Properties.MemorySize == 512

    def test_type_is_fixed(self) -> None:
        """Test that Type is always the same for all instances."""
        func1 = LambdaFunction(
            Properties=LambdaFunctionProperties(FunctionName="function-1")
        )
        func2 = LambdaFunction(
            Properties=LambdaFunctionProperties(FunctionName="function-2")
        )
        assert func1.Type == "AWS::Lambda::Function"
        assert func2.Type == "AWS::Lambda::Function"

    def test_dict_exclude_none(self) -> None:
        """Test dict serialization with exclude_none=True."""
        lambda_function = LambdaFunction(
            Properties=LambdaFunctionProperties(FunctionName="test-function")
        )
        data = lambda_function.dict(exclude_none=True)
        assert data["Type"] == "AWS::Lambda::Function"
        assert data["Properties"]["FunctionName"] == "test-function"

    def test_properties_default_factory(self) -> None:
        """Test that Properties uses default_factory correctly."""
        func1 = LambdaFunction(
            Properties=LambdaFunctionProperties(FunctionName="function-1")
        )
        func2 = LambdaFunction(
            Properties=LambdaFunctionProperties(FunctionName="function-2")
        )
        assert func1.Properties is not func2.Properties
        assert func1.Properties.FunctionName == "function-1"
        assert func2.Properties.FunctionName == "function-2"

    def test_complex_properties_serialization(self) -> None:
        """Test serialization of complex nested properties."""
        properties = LambdaFunctionProperties(
            FunctionName="complex-function",
            Environment={"Variables": {"ENV_VAR_1": "value1", "ENV_VAR_2": "value2"}},
            VpcConfig={
                "VpcId": "vpc-12345678",
                "SubnetIds": ["subnet-12345678", "subnet-87654321"],
                "SecurityGroupIds": ["sg-12345678"],
            },
            Tags=[
                {"Key": "Environment", "Value": "production"},
                {"Key": "Project", "Value": "web-app"},
            ],
        )
        lambda_function = LambdaFunction(Properties=properties)

        data = lambda_function.dict(exclude_none=True)
        assert data["Properties"]["Environment"]["Variables"]["ENV_VAR_1"] == "value1"
        assert data["Properties"]["VpcConfig"]["VpcId"] == "vpc-12345678"
        assert len(data["Properties"]["VpcConfig"]["SubnetIds"]) == 2
        assert len(data["Properties"]["Tags"]) == 2
