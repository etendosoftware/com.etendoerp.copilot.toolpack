package com.etendoerp.copilot.toolpack.tools;

import java.io.IOException;
import java.net.Inet4Address;
import java.net.Inet6Address;
import java.net.InetAddress;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.file.Path;
import java.time.Duration;
import java.util.Locale;
import java.util.UUID;
import javax.enterprise.context.ApplicationScoped;
import javax.inject.Named;
import org.codehaus.jettison.json.JSONObject;
import com.etendoerp.copilot.engine.tool.ServerTool;
import com.etendoerp.copilot.engine.tool.ToolExecutionContext;
import dev.langchain4j.agent.tool.ToolSpecification;

@ApplicationScoped
@Named("FileDownloaderTool")
public class FileDownloaderTool implements ServerTool {
  private static final int MAX_REDIRECTS = 3;
  private static final Duration CONNECT_TIMEOUT = Duration.ofSeconds(15);
  private static final Duration REQUEST_TIMEOUT = Duration.ofSeconds(60);

  public String name() { return "FileDownloaderTool"; }

  public ToolSpecification specification() {
    return FileToolSupport.spec(name(), "This tool receives a URL, downloads the file to a temporary directory in the tool workspace and returns the path to the temporary file.",
        "{\"file_path_or_url\":{\"type\":\"string\",\"title\":\"File path or URL\",\"description\":\"The file path or URL to download.\"}}", "file_path_or_url");
  }

  public String execute(JSONObject args, ToolExecutionContext context) throws Exception {
    String input = FileToolSupport.requiredString(args, "file_path_or_url");
    URI current;
    try {
      current = checkedUri(URI.create(input));
    } catch (IllegalArgumentException e) {
      return new JSONObject().put("error", "The provided input is not a valid URL.").toString();
    }

    HttpClient client = HttpClient.newBuilder().connectTimeout(CONNECT_TIMEOUT)
        .followRedirects(HttpClient.Redirect.NEVER).build();
    HttpResponse<java.io.InputStream> response;
    for (int redirects = 0; ; redirects++) {
      response = client.send(HttpRequest.newBuilder(current).timeout(REQUEST_TIMEOUT).GET().build(),
          HttpResponse.BodyHandlers.ofInputStream());
      int status = response.statusCode();
      if (status >= 300 && status < 400) {
        try (java.io.InputStream ignored = response.body()) { /* close redirect response */ }
        if (redirects >= MAX_REDIRECTS) return downloadError("Too many redirects.");
        String location = response.headers().firstValue("location").orElse(null);
        if (location == null) return downloadError("File could not be downloaded. Status code: " + status);
        try {
          current = checkedRedirect(current, location);
        } catch (IllegalArgumentException e) {
          return downloadError("The redirect URL is not allowed.");
        }
        continue;
      }
      if (status != 200) {
        try (java.io.InputStream ignored = response.body()) { /* close error response */ }
        return downloadError("File could not be downloaded. Status code: " + status);
      }
      break;
    }

    String filename = current.getPath();
    filename = filename == null || filename.isEmpty() ? "downloaded_file" : Path.of(filename).getFileName().toString();
    filename = FileToolSupport.sanitizeFilename(filename);
    if (filename.isBlank()) filename = "downloaded_file";
    String type = response.headers().firstValue("content-type").orElse("");
    if (type.toLowerCase(Locale.ROOT).contains("text") && !filename.contains(".")) filename += ".txt";
    Path target = ToolWorkspace.workDir(context).resolve("download_" + UUID.randomUUID() + "_" + filename);
    try (java.io.InputStream body = response.body()) {
      Path written = FileToolSupport.writeStream(context, target.toString(), body, ToolWorkspace.maxFileBytes());
      return new JSONObject().put("temp_file_path", written.toString()).toString();
    }
  }

  static URI checkedUri(URI uri) {
    if (uri == null || !uri.isAbsolute() || uri.getRawUserInfo() != null || uri.getHost() == null
        || !("http".equalsIgnoreCase(uri.getScheme()) || "https".equalsIgnoreCase(uri.getScheme()))) {
      throw new IllegalArgumentException("Only absolute HTTP(S) URLs are allowed");
    }
    try {
      InetAddress[] addresses = InetAddress.getAllByName(uri.getHost());
      if (addresses.length == 0) throw new IllegalArgumentException("Host has no addresses");
      for (InetAddress address : addresses) if (isUnsafeAddress(address)) throw new IllegalArgumentException("Unsafe destination address");
    } catch (IOException e) {
      throw new IllegalArgumentException("Unable to resolve destination host", e);
    }
    return uri;
  }
  static URI checkedRedirect(URI current, String location) {
    return checkedUri(current.resolve(location));
  }

  private static boolean isUnsafeAddress(InetAddress address) {
    if (address.isAnyLocalAddress() || address.isLoopbackAddress() || address.isLinkLocalAddress()
        || address.isSiteLocalAddress() || address.isMulticastAddress()) return true;
    byte[] b = address.getAddress();
    if (address instanceof Inet4Address) {
      int a = b[0] & 255, second = b[1] & 255;
      return a == 0 || a == 10 || a == 127 || a >= 224 || (a == 100 && second >= 64 && second <= 127)
          || (a == 169 && second == 254) || (a == 172 && second >= 16 && second <= 31)
          || (a == 192 && second == 168);
    }
    if (address instanceof Inet6Address) {
      int first = b[0] & 255;
      // IPv6 unique-local and the well-known IPv4-mapped metadata endpoint range.
      return (first & 0xfe) == 0xfc || (first == 0x00 && (b[1] & 255) == 0x64 && (b[2] & 255) == 0xff
          && (b[3] & 255) == 0x9b);
    }
    return true;
  }

  private static String downloadError(String message) throws Exception {
    return new JSONObject().put("error", message).toString();
  }
}
