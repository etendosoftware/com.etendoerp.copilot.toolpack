package com.etendoerp.copilot.toolpack.tools;

import javax.enterprise.context.ApplicationScoped;
import javax.inject.Inject;
import javax.inject.Named;
import org.codehaus.jettison.json.JSONObject;
import com.etendoerp.copilot.engine.tool.ServerTool;
import com.etendoerp.copilot.engine.tool.ToolExecutionContext;
import com.etendoerp.copilot.kb.AgentMemoryService;
import com.etendoerp.copilot.kb.KnowledgeBaseStore;
import dev.langchain4j.agent.tool.ToolSpecification;
import dev.langchain4j.model.chat.request.json.JsonObjectSchema;
import dev.langchain4j.model.chat.request.json.JsonRawSchema;

/** Per-agent, per-user memory operations stored in a namespace separate from KB documents. */
@ApplicationScoped
@Named("MemoryTool")
public class MemoryTool implements ServerTool {
  @Inject AgentMemoryService memoryService;
  @Override public String name() { return "MemoryTool"; }
  @Override public ToolSpecification specification() {
    return ToolSpecification.builder().name(name())
        .description("Store, search, update and delete private memories for the current agent and user.")
        .parameters(JsonObjectSchema.builder()
            .addProperty("mode", JsonRawSchema.from("{\"type\":\"string\",\"enum\":[\"add\",\"search\",\"update\",\"delete\"]}"))
            .addProperty("memory", JsonRawSchema.from("{\"type\":[\"string\",\"null\"]}"))
            .addProperty("query", JsonRawSchema.from("{\"type\":[\"string\",\"null\"]}"))
            .addProperty("memory_id", JsonRawSchema.from("{\"type\":[\"string\",\"null\"]}"))
            .addProperty("k", JsonRawSchema.from("{\"type\":\"integer\",\"default\":3}"))
            .required("mode").build()).build();
  }
  @Override public String execute(JSONObject args, ToolExecutionContext context) throws Exception {
    String mode = args.optString("mode", "");
    String agent = context.agentId();
    String user = context.userId();
    JSONObject result = new JSONObject();
    switch (mode) {
      case "add": {
        String text = args.optString("memory", "");
        if (text.isBlank()) result.put("error", "The 'memory' parameter is required for 'add' mode.");
        else {
          String id = memoryService.add(agent, user, text);
          result.put("result", "Memory added for user_id " + user + ": " + text + " (memory_id: " + id + ")");
        }
        break;
      }
      case "search": {
        String query = args.optString("query", "");
        if (query.isBlank()) {
          result.put("error", "The 'query' parameter is required for 'search' mode.");
          break;
        }
        var matches = memoryService.search(agent, user, query, args.optInt("k", 3));
        StringBuilder formatted = new StringBuilder();
        for (KnowledgeBaseStore.Match match : matches) {
          if (formatted.length() > 0) formatted.append('\n');
          formatted.append("- ").append(match.content()).append(" (memory_id: ").append(match.sourceId()).append(')');
        }
        result.put("result", formatted.length() == 0
            ? "No memories found for user_id " + user + " with query: " + query : formatted.toString());
        break;
      }
      case "update": {
        String id = args.optString("memory_id", "");
        String text = args.optString("memory", "");
        if (id.isBlank() || text.isBlank()) {
          result.put("error", "Both 'memory_id' and 'memory' are required for 'update' mode.");
        } else if (!memoryService.update(agent, user, id, text)) {
          result.put("error", "No memory found with memory_id " + id + " for user_id " + user);
        } else {
          result.put("result", "Memory updated for user_id " + user + ": " + text + " (memory_id: " + id + ")");
        }
        break;
      }
      case "delete": {
        String id = args.optString("memory_id", "");
        if (id.isBlank()) {
          result.put("error", "The 'memory_id' parameter is required for 'delete' mode.");
        } else if (!memoryService.delete(agent, user, id)) {
          result.put("error", "No memory found with memory_id " + id + " for user_id " + user);
        } else {
          result.put("result", "Memory with memory_id " + id + " deleted for user_id " + user);
        }
        break;
      }
      default: result.put("error", "Invalid mode. Use add, search, update, or delete.");
    }
    return result.toString();
  }
}
