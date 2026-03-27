from tools import FileDownloaderTool


def test_invalid_url():
    tool = FileDownloaderTool()
    invalid_url = "invalid-url"

    input_params = {"file_path_or_url": invalid_url}
    result = tool.run(input_params)

    assert "error" in result
    assert result["error"] == "The provided input is not a valid URL."


def test_url_with_non_200_status_code(requests_mock):
    tool = FileDownloaderTool()
    non_200_url = "https://example.com/404"

    requests_mock.get(non_200_url, status_code=404)

    input_params = {"file_path_or_url": non_200_url}
    result = tool.run(input_params)

    assert "error" in result
    assert result["error"] == "File could not be downloaded. Status code: 404"


def test_valid_url_text_file(requests_mock):
    tool = FileDownloaderTool()
    valid_url = "https://example.com/sample.txt"

    requests_mock.get(
        valid_url, text="Sample text content", headers={"content-type": "text/plain"}
    )

    input_params = {"file_path_or_url": valid_url}
    result = tool.run(input_params)

    assert "temp_file_path" in result
    assert result["temp_file_path"].endswith(".txt")


def test_valid_url_binary_file(requests_mock):
    tool = FileDownloaderTool()
    valid_url = "https://example.com/sample.bin"

    requests_mock.get(
        valid_url,
        content=b"Sample binary content",
        headers={"content-type": "application/octet-stream"},
    )

    input_params = {"file_path_or_url": valid_url}
    result = tool.run(input_params)

    assert "temp_file_path" in result
    assert result["temp_file_path"].endswith(".bin")
