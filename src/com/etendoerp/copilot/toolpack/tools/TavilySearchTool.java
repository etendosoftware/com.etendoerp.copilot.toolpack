package com.etendoerp.copilot.toolpack.tools;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;

import javax.enterprise.context.ApplicationScoped;
import javax.inject.Named;

import org.codehaus.jettison.json.JSONObject;

import com.etendoerp.copilot.engine.tool.ServerTool;
import com.etendoerp.copilot.engine.tool.ToolExecutionContext;
import com.etendoerp.copilot.toolpack.tools.support.ToolSecrets;

import dev.langchain4j.agent.tool.ToolSpecification;
import dev.langchain4j.model.chat.request.json.JsonObjectSchema;
import dev.langchain4j.model.chat.request.json.JsonRawSchema;

/** Internet search backed by the Tavily REST API. */
@ApplicationScoped
@Named("TavilySearchTool")
public class TavilySearchTool implements ServerTool {
  private static final String DESCRIPTION = "Tool to perform searches in Tavily. Tavily is a search engine that allows you to search the internet for information. This tool will return the search results for the given query";
  private static final HttpClient HTTP = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(20)).build();

  @Override public String name() { return "TavilySearchTool"; }

  @Override public ToolSpecification specification() {
    return ToolSpecification.builder().name(name()).description(DESCRIPTION)
        .parameters(JsonObjectSchema.builder()
            .addProperty("query", JsonRawSchema.from("{\"type\":\"string\",\"description\":\"Query to search in internet for.\"}"))
            .required(java.util.Collections.singletonList("query")).build()).build();
  }

  @Override public String execute(JSONObject arguments, ToolExecutionContext context) throws Exception {
    String query = arguments.optString("query", null);
    String key = ToolSecrets.get("tavily.api.key");
    if (key == null) throw new IllegalStateException("Tavily API key is not configured (tavily.api.key)");
    JSONObject body = new JSONObject();
    body.put("api_key", key);
    body.put("query", query);
    HttpRequest request = HttpRequest.newBuilder(URI.create("https://api.tavily.com/search"))
        .timeout(Duration.ofSeconds(60)).header("Content-Type", "application/json")
        .POST(HttpRequest.BodyPublishers.ofString(body.toString())).build();
    HttpResponse<String> response = HTTP.send(request, HttpResponse.BodyHandlers.ofString());
    if (response.statusCode() < 200 || response.statusCode() >= 300) {
      throw new IllegalStateException("Tavily search failed (HTTP " + response.statusCode() + ")");
    }
    return response.body();
  }
}
