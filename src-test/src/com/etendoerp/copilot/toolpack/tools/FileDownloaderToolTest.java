package com.etendoerp.copilot.toolpack.tools;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.net.URI;
import org.codehaus.jettison.json.JSONObject;
import org.junit.jupiter.api.Test;

class FileDownloaderToolTest {
  @Test void rejectsNonHttpSchemesAndPrivateAddresses() throws Exception {
    assertThrows(IllegalArgumentException.class, () -> FileDownloaderTool.checkedUri(URI.create("file:///etc/passwd")));
    assertThrows(IllegalArgumentException.class, () -> FileDownloaderTool.checkedUri(URI.create("http://127.0.0.1/file")));
    assertThrows(IllegalArgumentException.class, () -> FileDownloaderTool.checkedUri(URI.create("http://169.254.169.254/latest/meta-data/")));
    assertEquals("{\"error\":\"The provided input is not a valid URL.\"}",
        new FileDownloaderTool().execute(new JSONObject().put("file_path_or_url", "ftp://example.com/file"), null));
  }

  @Test void rejectsPrivateAddressesAndCredentialsInRedirectTargets() {
    assertThrows(IllegalArgumentException.class, () -> FileDownloaderTool.checkedUri(URI.create("http://[::1]/file")));
    assertThrows(IllegalArgumentException.class, () -> FileDownloaderTool.checkedUri(URI.create("https://user:pass@example.com/file")));
  }
  @Test void rejectsPrivateRedirectTargets() {
    assertThrows(IllegalArgumentException.class, () -> FileDownloaderTool.checkedRedirect(
        URI.create("https://public.example/start"), "http://127.0.0.1/metadata"));
    assertThrows(IllegalArgumentException.class, () -> FileDownloaderTool.checkedRedirect(
        URI.create("https://public.example/start"), "//169.254.169.254/latest/meta-data/"));
  }
}
