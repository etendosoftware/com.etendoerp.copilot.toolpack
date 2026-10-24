/*
 *************************************************************************
 * All portions are Copyright © 2026 FUTIT SERVICES, S.L
 * All Rights Reserved.
 *************************************************************************
 */
package com.etendoerp.copilot.toolpack.tools;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

import javax.enterprise.context.ApplicationScoped;
import javax.inject.Named;

import org.codehaus.jettison.json.JSONArray;
import org.codehaus.jettison.json.JSONObject;

import com.etendoerp.copilot.engine.team.TeamTaskState;
import com.etendoerp.copilot.engine.tool.ServerTool;
import com.etendoerp.copilot.engine.tool.ToolExecutionContext;

import dev.langchain4j.agent.tool.ToolSpecification;
import dev.langchain4j.model.chat.request.json.JsonObjectSchema;
import dev.langchain4j.model.chat.request.json.JsonRawSchema;

/** Manages the bounded task queue belonging to one team execution context. */
@ApplicationScoped
@Named("TaskManagementTool")
public class TaskManagementTool implements ServerTool {
  @Override
  public String name() {
    return "TaskManagementTool";
  }

  @Override
  public ToolSpecification specification() {
    return ToolSpecification.builder().name(name())
        .description("Manage supervisor work tasks. Modes: get_next, add_tasks, status, mark_done.")
        .parameters(JsonObjectSchema.builder()
            .addProperty("mode", JsonRawSchema.from("{\"type\":\"string\",\"enum\":[\"get_next\",\"add_tasks\",\"status\",\"mark_done\"],\"description\":\"Operation to perform\"}"))
            .addProperty("new_tasks", JsonRawSchema.from("{\"type\":\"array\",\"items\":{\"type\":\"string\"},\"description\":\"Tasks to append when mode is add_tasks\"}"))
            .required(Arrays.asList("mode"))
            .build())
        .build();
  }

  @Override
  public String execute(JSONObject arguments, ToolExecutionContext context) throws Exception {
    String mode = arguments.optString("mode", "");
    List<String> tasks = readTasks(arguments.optJSONArray("new_tasks"));
    Object stateValue = context.attributes().computeIfAbsent(TeamTaskState.CONTEXT_ATTRIBUTE,
        ignored -> new TeamTaskState());
    if (!(stateValue instanceof TeamTaskState)) {
      throw new IllegalStateException("The team task-state context attribute has an unexpected type.");
    }
    return ((TeamTaskState) stateValue).apply(mode, tasks);
  }

  private List<String> readTasks(JSONArray tasks) throws Exception {
    if (tasks == null) return null;
    if (tasks.length() > TeamTaskState.MAX_PENDING_TASKS) {
      throw new IllegalArgumentException("At most " + TeamTaskState.MAX_PENDING_TASKS + " tasks can be added at once.");
    }
    List<String> result = new ArrayList<>(tasks.length());
    for (int i = 0; i < tasks.length(); i++) {
      Object value = tasks.get(i);
      if (!(value instanceof String)) {
        throw new IllegalArgumentException("Each task must be a string.");
      }
      result.add((String) value);
    }
    return result;
  }
}
