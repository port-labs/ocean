import tempfile
from unittest.mock import patch
from port_ocean.utils.ipc import FileIPC


class TestFileIPCErrorHandling:
    def test_save_and_load_normal_operation(self) -> None:
        """Test that normal save and load operations work correctly."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a simple IPC instance and manually set file path to temp dir
            ipc = FileIPC("test_process", "test_name", default_return="default")
            ipc.file_path = f"{temp_dir}/test_name.pkl"

            # Save data
            test_data = {"key": "value", "number": 42}
            ipc.save(test_data)

            # Load data
            loaded_data = ipc.load()
            assert loaded_data == test_data

    def test_load_missing_file_returns_default(self) -> None:
        """Test that loading a non-existent file returns the default value."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("port_ocean.utils.ipc.os.makedirs"):
                ipc = FileIPC(
                    "test_process", "test_name", default_return="default_value"
                )
                ipc.file_path = f"{temp_dir}/nonexistent.pkl"

                result = ipc.load()
                assert result == "default_value"

    def test_load_corrupted_pickle_returns_default(self) -> None:
        """Test that loading a corrupted pickle file returns default value and logs warning."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("port_ocean.utils.ipc.os.makedirs"):
                ipc = FileIPC("test_process", "test_name", default_return="fallback")
                ipc.file_path = f"{temp_dir}/corrupted.pkl"

                # Create a corrupted pickle file
                with open(ipc.file_path, "wb") as f:
                    f.write(b"corrupted pickle data")

                with patch("port_ocean.utils.ipc.logger.warning") as mock_logger:
                    result = ipc.load()

                    assert result == "fallback"
                    mock_logger.assert_called_once()
                    assert "Failed to load IPC data" in str(mock_logger.call_args)

    def test_load_truncated_pickle_returns_default(self) -> None:
        """Test that loading a truncated pickle file (EOFError) returns default value."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("port_ocean.utils.ipc.os.makedirs"):
                ipc = FileIPC("test_process", "test_name", default_return=[])
                ipc.file_path = f"{temp_dir}/truncated.pkl"

                # Create a truncated pickle file (empty file)
                with open(ipc.file_path, "wb"):
                    pass  # Create empty file

                with patch("port_ocean.utils.ipc.logger.warning") as mock_logger:
                    result = ipc.load()

                    assert result == []
                    mock_logger.assert_called_once()

    def test_load_type_error_during_unpickling_returns_default(self) -> None:
        """Test that TypeError during unpickling (e.g., constructor mismatch) returns default value."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("port_ocean.utils.ipc.os.makedirs"):
                ipc = FileIPC(
                    "test_process", "test_name", default_return="type_error_fallback"
                )
                ipc.file_path = f"{temp_dir}/type_error.pkl"

                # Create a dummy file so existence check passes
                with open(ipc.file_path, "wb") as f:
                    f.write(b"dummy content")

                # Mock pickle.load to raise TypeError (simulating constructor signature mismatch)
                with patch(
                    "pickle.load",
                    side_effect=TypeError(
                        "KindNotImplementedException.__init__() missing 1 required positional argument: 'available_kinds'"
                    ),
                ):
                    with patch("port_ocean.utils.ipc.logger.warning") as mock_logger:
                        result = ipc.load()

                        assert result == "type_error_fallback"
                        mock_logger.assert_called_once()
                        assert "KindNotImplementedException" in str(
                            mock_logger.call_args
                        )

    def test_load_attribute_error_during_unpickling_returns_default(self) -> None:
        """Test that AttributeError during unpickling returns default value."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("port_ocean.utils.ipc.os.makedirs"):
                ipc = FileIPC(
                    "test_process", "test_name", default_return="attr_error_fallback"
                )
                ipc.file_path = f"{temp_dir}/attr_error.pkl"

                # Create a dummy file so existence check passes
                with open(ipc.file_path, "wb") as f:
                    f.write(b"dummy content")

                # Mock pickle.load to raise AttributeError
                with patch(
                    "pickle.load",
                    side_effect=AttributeError(
                        "module 'some_module' has no attribute 'SomeClass'"
                    ),
                ):
                    with patch("port_ocean.utils.ipc.logger.warning") as mock_logger:
                        result = ipc.load()

                        assert result == "attr_error_fallback"
                        mock_logger.assert_called_once()

    def test_load_import_error_during_unpickling_returns_default(self) -> None:
        """Test that ImportError during unpickling returns default value."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("port_ocean.utils.ipc.os.makedirs"):
                ipc = FileIPC(
                    "test_process", "test_name", default_return="import_error_fallback"
                )
                ipc.file_path = f"{temp_dir}/import_error.pkl"

                # Create a dummy file so existence check passes
                with open(ipc.file_path, "wb") as f:
                    f.write(b"dummy content")

                # Mock pickle.load to raise ImportError
                with patch(
                    "pickle.load",
                    side_effect=ImportError("No module named 'missing_module'"),
                ):
                    with patch("port_ocean.utils.ipc.logger.warning") as mock_logger:
                        result = ipc.load()

                        assert result == "import_error_fallback"
                        mock_logger.assert_called_once()
