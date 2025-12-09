import zipfile
from pathlib import Path

import pandas as pd
import pytest

import importlib


from tools.TaskCreatorTool import (
    process_zip,
    process_csv,
    process_xls,
    process_file,
    get_or_create_task_type,
    get_or_create_status,
    send_taskapi_request,
    TaskCreatorTool,
)

tc = importlib.import_module("tools.TaskCreatorTool")


class FakeResp:
    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json = json_data or {}

    def json(self):
        return self._json


def test_process_zip_creates_and_returns_files(tmp_path, monkeypatch):
    # Create a zip file with two files
    zip_path = tmp_path / "files.zip"
    with zipfile.ZipFile(zip_path, "w") as z:
        z.writestr("a.txt", "hello")
        z.writestr("b.txt", "world")

    # Ensure non-docker branch for predictable temp location
    monkeypatch.setattr(tc, "is_docker", lambda: False)

    result = process_zip(str(zip_path))
    # We expect two extracted files
    assert len(result) == 2
    basenames = {Path(p).name for p in result}
    assert basenames == {"a.txt", "b.txt"}
    # Files should exist on disk
    for p in result:
        assert Path(p).exists()


def test_process_csv_reads_rows(tmp_path):
    csv_file = tmp_path / "data.csv"
    csv_file.write_text("col1,col2\n1,foo\n2,bar\n", encoding="utf-8")

    rows = process_csv(str(csv_file))
    assert len(rows) == 2
    assert "'col1': '1'" in rows[0] or '"col1": "1"' in rows[0]
    assert "foo" in rows[0]


def test_process_xls_uses_pandas(monkeypatch, tmp_path):
    # Monkeypatch pandas.read_excel to return a predictable DataFrame
    df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})

    monkeypatch.setattr(pd, "read_excel", lambda path: df)

    # Path can be nonexistent because read_excel is mocked
    rows = process_xls(str(tmp_path / "fake.xlsx"))
    assert len(rows) == 2
    assert "'a': 1" in rows[0] or '"a": 1' in rows[0]


def test_process_file_raises_for_missing():
    with pytest.raises(Exception):
        process_file("/non/existent/file.xyz")


def test_process_file_unsupported_returns_path(tmp_path):
    f = tmp_path / "some.bin"
    f.write_text("data")
    res = process_file(str(f))
    assert res == [str(f)]


def test_get_or_create_task_type_existing(monkeypatch):
    # Simulate simple_request_to_etendo returning an existing task type
    def fake_simple(method, payload, path):
        return FakeResp(200, {"response": {"data": [{"id": "T123"}]}})

    monkeypatch.setattr(tc, "simple_request_to_etendo", fake_simple)
    tt = get_or_create_task_type("Copilot")
    assert tt == "T123"


def test_get_or_create_task_type_creates_when_missing(monkeypatch):
    # First call (GET) returns empty list, second (POST) returns created id
    calls = {"count": 0}

    def fake_simple(method, payload, path):
        calls["count"] += 1
        if calls["count"] == 1:
            return FakeResp(200, {"response": {"data": []}})
        return FakeResp(200, {"response": {"data": [{"id": "NEW"}]}})

    monkeypatch.setattr(tc, "simple_request_to_etendo", fake_simple)
    tt = get_or_create_task_type("Copilot")
    assert tt == "NEW"


def test_get_or_create_status_existing(monkeypatch):
    def fake_simple(method, payload, path):
        return FakeResp(200, {"response": {"data": [{"id": "S1"}]}})

    monkeypatch.setattr(tc, "simple_request_to_etendo", fake_simple)
    sid = get_or_create_status("Pending")
    assert sid == "S1"


def test_get_or_create_status_creates_when_missing(monkeypatch):
    calls = {"count": 0}

    def fake_simple(method, payload, path):
        calls["count"] += 1
        if calls["count"] == 1:
            return FakeResp(200, {"response": {"data": []}})
        return FakeResp(200, {"response": {"data": [{"id": "S_NEW"}]}})

    monkeypatch.setattr(tc, "simple_request_to_etendo", fake_simple)
    sid = get_or_create_status("Pending")
    assert sid == "S_NEW"


def test_send_taskapi_request_builds_payload(monkeypatch):
    captured = {}

    def fake_request(method, payload, path, host, token):
        captured["args"] = (method, payload, path, host, token)
        return FakeResp(201, {"ok": True})

    monkeypatch.setattr(tc, "request_to_etendo", fake_request)
    resp = send_taskapi_request("Q", "TT", "ST", "AG", "GR", "ITEM", "H", "T")
    assert resp.status_code == 201
    assert captured["args"][0] == "POST"
    assert captured["args"][1]["taskType"] == "TT"
    assert "etcopQuestion" in captured["args"][1]


def test_task_creator_tool_run_creates_tasks(monkeypatch):
    # Patch heavy operations: file processing and network calls
    # Note: process_file now takes 2 parameters: path and groupby
    monkeypatch.setattr(tc, "process_file", lambda p, g=None: ["i1", "i2"])
    monkeypatch.setattr(
        tc, "send_taskapi_request", lambda *a, **k: FakeResp(200, {"ok": True})
    )
    monkeypatch.setattr(tc, "get_etendo_host", lambda: "h")
    monkeypatch.setattr(tc, "get_etendo_token", lambda: "t")

    # ThreadContext provides conversation and assistant ids when none provided
    class DummyTC:
        @staticmethod
        def get_data(k):
            return "GID" if k == "conversation_id" else "AID"

    monkeypatch.setattr(tc, "ThreadContext", DummyTC)

    tool = TaskCreatorTool()
    out = tool.run({"question": "Do it", "file_path": "ignored"})
    assert "GID" in out["message"]


def test_task_creator_tool_run_propagates_error(monkeypatch):
    def _raise(p):
        raise RuntimeError("boom")

    monkeypatch.setattr(tc, "process_file", _raise)
    tool = TaskCreatorTool()
    with pytest.raises(tc.ToolException):
        tool.run({"question": "x", "file_path": "doesnotmatter"})
