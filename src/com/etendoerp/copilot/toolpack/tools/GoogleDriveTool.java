package com.etendoerp.copilot.toolpack.tools;

import java.nio.file.Path;
import java.util.List;
import java.util.Locale;

import javax.enterprise.context.ApplicationScoped;
import javax.inject.Named;

import org.codehaus.jettison.json.JSONException;
import org.codehaus.jettison.json.JSONObject;

import com.etendoerp.copilot.engine.tool.ServerTool;
import com.etendoerp.copilot.engine.tool.ToolExecutionContext;

import dev.langchain4j.agent.tool.ToolSpecification;

/** Lists Drive files and uploads local workspace files. */
@ApplicationScoped
@Named("GoogleDriveTool")
public class GoogleDriveTool implements ServerTool {

  private static final String DESCRIPTION = "Tool to interact with Google Drive. Supports:\n- 'list': list accessible files of a certain type.\n- 'upload': upload a local file to Drive.";

  @Override
  public String name() {
    return "GoogleDriveTool";
  }

  @Override
  public ToolSpecification specification() {
    return FileToolSupport.spec(name(), DESCRIPTION,
        "{\"alias\":{\"type\":\"string\",\"title\":\"Alias\",\"description\":\"Alias of the OAuth token to use.\"},"
            + "\"mode\":{\"type\":\"string\",\"title\":\"Mode\",\"description\":\"Action to perform: 'list' or 'upload'.\"},"
            + "\"file_type\":{\"anyOf\":[{\"type\":\"string\"},{\"type\":\"null\"}],\"default\":\"spreadsheet\",\"title\":\"File Type\",\"description\":\"File type to filter (spreadsheet, doc, pdf, etc.). Used in 'list' mode.\"},"
            + "\"file_path\":{\"anyOf\":[{\"type\":\"string\"},{\"type\":\"null\"}],\"default\":null,\"title\":\"File Path\",\"description\":\"Local path to the file to upload. Required for 'upload' mode.\"},"
            + "\"name\":{\"anyOf\":[{\"type\":\"string\"},{\"type\":\"null\"}],\"default\":null,\"title\":\"Name\",\"description\":\"Name to assign to the uploaded file in Drive (optional).\"},"
            + "\"mime_type\":{\"anyOf\":[{\"type\":\"string\"},{\"type\":\"null\"}],\"default\":null,\"title\":\"Mime Type\",\"description\":\"MIME type of the file (e.g., 'application/pdf'). Optional.\"}}",
        "alias", "mode");
  }

  @Override
  public String execute(JSONObject args, ToolExecutionContext ctx) throws Exception {
    try {
      String alias = args.getString("alias");
      String mode = args.getString("mode").toLowerCase(Locale.ROOT);
      if ("list".equals(mode)) {
        String fileType = args.optString("file_type", "spreadsheet");
        if (fileType == null || fileType.isEmpty()) {
          return error("Missing 'file_type' parameter for list mode.");
        }
        List<JSONObject> files = GoogleServiceUtil.listAccessibleFiles(ctx, fileType, alias);
        if (files.isEmpty()) {
          return message("No files of type '" + fileType + "' found.");
        }
        StringBuilder formatted = new StringBuilder();
        for (JSONObject file : files) {
          if (formatted.length() > 0) {
            formatted.append('\n');
          }
          formatted.append("- ").append(file.optString("name", "null"))
              .append(" (ID: ").append(file.optString("id", "null")).append(')');
        }
        return message("📂 Files of type '" + fileType + "':\n" + formatted);
      }
      if ("upload".equals(mode)) {
        String filePath = args.getString("file_path");
        Path path = FileToolSupport.readPath(ctx, filePath);
        String driveName = args.optString("name", null);
        if (driveName == null || driveName.isEmpty()) {
          driveName = path.getFileName().toString();
        }
        String mimeType = args.optString("mime_type", "application/octet-stream");
        if (mimeType == null || mimeType.isEmpty()) {
          mimeType = "application/octet-stream";
        }
        JSONObject uploaded = GoogleServiceUtil.uploadFileSimple(ctx, alias, path, driveName, mimeType);
        String link = "https://drive.google.com/file/d/" + uploaded.getString("id") + "/view";
        return message("✅ File '" + uploaded.getString("name") + "' uploaded successfully.\n🔗 Link: " + link);
      }
      return error("Unsupported mode: '" + mode + "'. Use 'list' or 'upload'.");
    } catch (Exception e) {
      return error("❌ GoogleDriveTool error: " + detail(e));
    }
  }

  private static String message(String value) throws JSONException {
    return new JSONObject().put("message", value).toString();
  }

  private static String error(String value) throws JSONException {
    return new JSONObject().put("error", value).toString();
  }

  private static String detail(Exception e) {
    return e.getMessage() == null ? e.getClass().getSimpleName() : e.getMessage();
  }
}
