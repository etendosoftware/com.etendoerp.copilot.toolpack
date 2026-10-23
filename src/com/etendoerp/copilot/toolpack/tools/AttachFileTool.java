package com.etendoerp.copilot.toolpack.tools;

import java.io.File;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashMap;

import javax.enterprise.context.ApplicationScoped;
import javax.inject.Named;

import org.codehaus.jettison.json.JSONException;
import org.codehaus.jettison.json.JSONObject;
import org.openbravo.base.weld.WeldUtils;
import org.openbravo.client.application.attachment.AttachImplementationManager;

import com.etendoerp.copilot.engine.tool.ServerTool;
import com.etendoerp.copilot.engine.tool.ToolExecutionContext;
import com.etendoerp.copilot.engine.tool.http.WebhookInvoker;

import dev.langchain4j.agent.tool.ToolSpecification;

/** Adds a workspace file to an accessible Etendo record. */
@ApplicationScoped
@Named("AttachFileTool")
public class AttachFileTool implements ServerTool {

  private static final String DESCRIPTION = "Uploads a file to an API after checking its existence and accessibility.";

  @Override
  public String name() {
    return "AttachFileTool";
  }

  @Override
  public ToolSpecification specification() {
    return FileToolSupport.spec(name(), DESCRIPTION,
        "{\"filepath\":{\"type\":\"string\",\"title\":\"Filepath\",\"description\":\"The path of the file to upload\"},"
            + "\"ad_tab_id\":{\"type\":\"string\",\"title\":\"Ad Tab Id\",\"description\":\"A string of 32 chars which is the ID of the Tab\"},"
            + "\"record_id\":{\"type\":\"string\",\"title\":\"Record Id\",\"description\":\"A string of 32 chars which is the ID of the record\"}}",
        "filepath", "ad_tab_id", "record_id");
  }

  @Override
  public String execute(JSONObject args, ToolExecutionContext ctx) throws Exception {
    try {
      String filepath = FileToolSupport.requiredString(args, "filepath");
      String tabId = FileToolSupport.requiredString(args, "ad_tab_id");
      String recordId = FileToolSupport.requiredString(args, "record_id");
      Path path = FileToolSupport.readPath(ctx, filepath);
      if (!Files.isRegularFile(path) || !Files.isReadable(path)) {
        return error("File does not exist or is not accessible");
      }

      // Keep the webhook's role-level permission boundary while using the native attachment API.
      WebhookInvoker.authorize(ctx, "AttachFile");
      File file = path.toFile();
      AttachImplementationManager manager = WeldUtils
          .getInstanceFromStaticBeanManager(AttachImplementationManager.class);
      manager.upload(new HashMap<>(), tabId, recordId, file.getName(), file);
      return new JSONObject().put("message", "Attachment created successfully").toString();
    } catch (Exception e) {
      return error(e.getMessage() == null ? e.getClass().getSimpleName() : e.getMessage());
    }
  }


  private static String error(String message) throws JSONException {
    return new JSONObject().put("error", message).toString();
  }
}
