package com.etendoerp.copilot.toolpack.tools;

import java.nio.file.Files;
import java.time.Duration;
import java.util.LinkedHashMap;
import java.util.Iterator;
import java.util.Locale;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import javax.enterprise.context.ApplicationScoped;
import javax.inject.Named;

import org.codehaus.jettison.json.JSONArray;
import org.codehaus.jettison.json.JSONException;
import org.codehaus.jettison.json.JSONObject;

import com.etendoerp.copilot.engine.tool.ServerTool;
import com.etendoerp.copilot.engine.tool.ToolExecutionContext;
import com.etendoerp.copilot.engine.tool.http.EtendoHttp;

import dev.langchain4j.agent.tool.ToolSpecification;

/** Generic HTTP request tool for Etendo and third-party APIs. */
@ApplicationScoped
@Named("APICallTool")
public class APICallTool implements ServerTool {

  private static final Pattern BASE64_FILE = Pattern.compile("@BASE64_(.*?)@");
  private static final String DESCRIPTION = " This Tool, executes a call to an API, and returns the response. This tool requires the following parameters:\n"
      + "    - url: The url of the API (for example: https://api.example.com) (required)\n"
      + "    - endpoint: The endpoint of the API (for example: /endpoint) (required)\n"
      + "    - method: The method of the API (GET, POST and PUT only supported). If not defined, it will be inferred from the endpoint. (for example: GET) (required)\n"
      + "    - body_params: The body of the API (only for POST method)\n"
      + "    - query_params: The query params of the API in json format\n"
      + "    - token: The bearer token of the API (if required)";

  @Override
  public String name() {
    return "APICallTool";
  }

  @Override
  public ToolSpecification specification() {
    return FileToolSupport.spec(name(), DESCRIPTION,
        "{\"url\":{\"type\":\"string\",\"title\":\"URL\",\"description\":\"The url of the API. Is mandatory.\"},"
            + "\"endpoint\":{\"type\":\"string\",\"title\":\"Endpoint\",\"description\":\"The endpoint of the API. Is mandatory.\"},"
            + "\"method\":{\"type\":\"string\",\"title\":\"Method\",\"enum\":[\"GET\",\"POST\",\"PUT\"],\"description\":\"The method of the API (GET, POST or PUT only supported). if not defined, it will be inferred from the endpoint. Is mandatory.\"},"
            + "\"body_params\":{\"anyOf\":[{\"type\":\"string\"},{\"type\":\"null\"}],\"title\":\"Body Params\",\"description\":\"The body of the API (only for POST method). Is mandatory.\"},"
            + "\"query_params\":{\"anyOf\":[{\"type\":\"string\"},{\"type\":\"null\"}],\"title\":\"Query Params\",\"description\":\"The query params of the API in json format. Is mandatory.\"},"
            + "\"token\":{\"anyOf\":[{\"type\":\"string\"},{\"type\":\"null\"}],\"title\":\"Token\",\"description\":\"The bearer token of the API. Is mandatory.\"}}",
        "url", "endpoint", "method", "body_params", "query_params", "token");
  }

  /** Destination is argument-dependent; EtendoHttp enforces the WS gate only for Etendo calls. */
  @Override
  public boolean needsWebService() {
    return false;
  }

  @Override
  public String execute(JSONObject args, ToolExecutionContext ctx) throws Exception {
    String url = args == null ? null : args.optString("url", null);
    String endpoint = args == null ? null : args.optString("endpoint", null);
    String method = args == null ? null : args.optString("method", null);
    String body = args == null ? null : args.optString("body_params", null);
    String query = args == null ? null : args.optString("query_params", null);
    String token = args == null ? null : args.optString("token", null);
    try {
      if (url == null || url.isEmpty()) {
        return error("url is required");
      }
      if (endpoint == null || endpoint.isEmpty()) {
        return error("endpoint is required");
      }
      if (method == null || method.isEmpty()) {
        String[] parts = endpoint.split(" ", 2);
        if (parts.length == 2 && (parts[0].equalsIgnoreCase("GET") || parts[0].equalsIgnoreCase("POST"))) {
          method = parts[0].toUpperCase(Locale.ROOT);
          endpoint = parts[1];
        } else {
          return error("method is required");
        }
      } else if (endpoint.startsWith("GET ") || endpoint.startsWith("POST ")) {
        String[] parts = endpoint.split(" ", 2);
        endpoint = parts[1];
        method = method.isEmpty() ? parts[0].toUpperCase(Locale.ROOT) : method;
      }
      endpoint = appendQuery(endpoint, query);
      String normalizedMethod = method.toUpperCase(Locale.ROOT);
      if (!normalizedMethod.equals("GET") && !normalizedMethod.equals("POST") && !normalizedMethod.equals("PUT")) {
        return error("Method " + method + " not supported");
      }
      if (body != null && body.contains("@BASE64_")) {
        body = replaceFilePlaceholders(body, ctx);
      }
      Map<String, String> headers = new LinkedHashMap<>();
      if (token != null && !token.isEmpty()) {
        headers.put("Authorization", "Bearer " + token);
      }
      if (normalizedMethod.equals("POST") || normalizedMethod.equals("PUT")) {
        headers.put("Content-Type", "application/json");
        headers.put("Accept", "application/json");
      }
      EtendoHttp.HttpResult result = EtendoHttp.call(ctx, normalizedMethod, url + endpoint, headers,
          body, Duration.ofMinutes(2));
      return new JSONObject().put("requestResponse", result.body())
          .put("requestStatusCode", result.status()).toString();
    } catch (Exception e) {
      return error(e.getMessage() == null ? e.getClass().getSimpleName() : e.getMessage());
    }
  }

  static String appendQuery(String endpoint, String query) throws JSONException {
    if (query == null || query.isEmpty()) {
      return endpoint;
    }
    if (!query.startsWith("{")) {
      throw new IllegalArgumentException("query_params must be a json object");
    }
    JSONObject values = new JSONObject(query);
    StringBuilder result = new StringBuilder(endpoint);
    Iterator<String> keys = values.keys();
    boolean first = !endpoint.contains("?");
    while (keys.hasNext()) {
      String key = keys.next();
      Object raw = values.get(key);
      String value;
      if (raw instanceof JSONArray array) {
        StringBuilder joined = new StringBuilder();
        for (int i = 0; i < array.length(); i++) {
          if (i > 0) joined.append(',');
          joined.append(array.get(i));
        }
        value = joined.toString();
      } else if (raw instanceof Number number) {
        value = number.toString();
      } else if (raw instanceof Boolean bool) {
        value = bool ? "True" : "False";
      } else {
        value = (String) raw;
      }
      result.append(first ? '?' : '&').append(key).append('=').append(value.replace(" ", "%20"));
      first = false;
    }
    return result.toString();
  }

  private static String replaceFilePlaceholders(String body, ToolExecutionContext ctx) throws Exception {
    Matcher matcher = BASE64_FILE.matcher(body);
    StringBuffer replaced = new StringBuffer();
    while (matcher.find()) {
      var path = FileToolSupport.readPath(ctx, matcher.group(1));
      String encoded = java.util.Base64.getEncoder().encodeToString(Files.readAllBytes(path));
      matcher.appendReplacement(replaced, Matcher.quoteReplacement(encoded));
    }
    matcher.appendTail(replaced);
    return replaced.toString();
  }

  private static String error(String message) throws JSONException {
    return new JSONObject().put("error", message).toString();
  }
}
