package com.etendoerp.copilot.toolpack.tools;

import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

import javax.enterprise.context.ApplicationScoped;
import javax.inject.Named;

import org.codehaus.jettison.json.JSONException;
import org.codehaus.jettison.json.JSONObject;

import com.etendoerp.copilot.engine.tool.ServerTool;
import com.etendoerp.copilot.engine.tool.ToolExecutionContext;

import dev.langchain4j.agent.tool.ToolSpecification;

/** Lists, creates, reads and uploads Google spreadsheets. */
@ApplicationScoped
@Named("GoogleSpreadsheetsTool")
public class GoogleSpreadsheetsTool implements ServerTool {

  private static final String DESCRIPTION = "Tool to interact with Google Spreadsheets through Google Drive API. The tool have the following modes: - list: List all accessible spreadsheets.\n- create: Create a new spreadsheet with the specified name. Optionally add headers as the first row.\n- upload: Upload a csv file to Google Drive as a new spreadsheet.\n- read: Read the content of a specified spreadsheet.\n- download: Download a specified spreadsheet as a CSV file.";

  @Override
  public String name() {
    return "GoogleSpreadsheetsTool";
  }

  @Override
  public ToolSpecification specification() {
    return FileToolSupport.spec(name(), DESCRIPTION,
        "{\"alias\":{\"type\":\"string\",\"title\":\"Alias\",\"description\":\"Alias of the OAuth token to use.\"},"
            + "\"mode\":{\"type\":\"string\",\"title\":\"Mode\",\"description\":\"Action to perform\"},"
            + "\"name\":{\"anyOf\":[{\"type\":\"string\"},{\"type\":\"null\"}],\"default\":null,\"title\":\"Name\",\"description\":\"Name of spreadsheet to create (required for create/upload mode). \"},"
            + "\"file_id\":{\"anyOf\":[{\"type\":\"string\"},{\"type\":\"null\"}],\"default\":null,\"title\":\"File Id\",\"description\":\"ID of the spreadsheet to read (required for read mode).\"},"
            + "\"range\":{\"anyOf\":[{\"type\":\"string\"},{\"type\":\"null\"}],\"default\":null,\"title\":\"Range\",\"description\":\"Cell range to read (optional, defaults to A1:Z1000).\"},"
            + "\"file_path\":{\"anyOf\":[{\"type\":\"string\"},{\"type\":\"null\"}],\"default\":null,\"title\":\"File Path\",\"description\":\"Local path to the CSV file to upload (required for upload mode).\"},"
            + "\"headers\":{\"anyOf\":[{\"type\":\"array\",\"items\":{\"type\":\"string\"}},{\"type\":\"null\"}],\"default\":null,\"title\":\"Headers\",\"description\":\"List of headers to add to the spreadsheet (optional, for create mode).\"}}",
        "alias", "mode");
  }

  @Override
  public String execute(JSONObject args, ToolExecutionContext ctx) throws Exception {
    try {
      String alias = args.getString("alias");
      String mode = args.getString("mode").toLowerCase(Locale.ROOT);
      return switch (mode) {
        case "list" -> listMode(ctx, alias);
        case "create" -> createMode(ctx, alias, args);
        case "upload" -> uploadMode(ctx, alias, args);
        case "read" -> readMode(ctx, alias, args);
        case "download" -> downloadMode(ctx, alias, args);
        default -> error("Unsupported mode: " + mode);
      };
    } catch (Exception e) {
      return error("GoogleSheetsTool error: " + detail(e));
    }
  }

  private static String listMode(ToolExecutionContext ctx, String alias) throws Exception {
    List<JSONObject> files = GoogleServiceUtil.listAccessibleFiles(ctx, "spreadsheet", alias);
    if (files.isEmpty()) {
      return message("No spreadsheets found.");
    }
    StringBuilder formatted = new StringBuilder();
    for (JSONObject file : files) {
      if (formatted.length() > 0) {
        formatted.append('\n');
      }
      formatted.append("- ").append(file.optString("name", "null"))
          .append(" (ID: ").append(file.optString("id", "null")).append(')');
    }
    return message("Spreadsheets found:\n" + formatted);
  }

  private static String createMode(ToolExecutionContext ctx, String alias, JSONObject args) throws Exception {
    String name = args.optString("name", null);
    if (name == null || name.isEmpty()) {
      return error("Missing 'name' parameter for create mode.");
    }
    JSONObject created = GoogleServiceUtil.createDriveFile(ctx, name,
        "application/vnd.google-apps.spreadsheet", alias);
    String id = created.getString("id");
    JSONArrayHeaders headers = headers(args);
    String url = "https://docs.google.com/spreadsheets/d/" + id + "/edit";
    if (!headers.values().isEmpty()) {
      try {
        List<List<?>> values = List.of(new ArrayList<>(headers.values()));
        GoogleServiceUtil.updateSpreadsheetValues(ctx, id, alias, "A1", values);
        return message("✅ Spreadsheet '" + created.optString("name", name) + "' created with headers: "
            + String.join(", ", headers.values()) + ".\n🔗 ID: " + id + "\n🔗 Link: " + url);
      } catch (Exception e) {
        return message("✅ Spreadsheet '" + created.optString("name", name) + "' created with ID: " + id
            + ".\n⚠️ Warning: Failed to add headers: " + detail(e) + "\n🔗 Link: " + url);
      }
    }
    return message("✅ Spreadsheet '" + created.optString("name", name) + "' created with ID: " + id
        + ".\n🔗 Link: " + url);
  }

  private static String readMode(ToolExecutionContext ctx, String alias, JSONObject args) throws Exception {
    String fileId = args.optString("file_id", null);
    if (fileId == null || fileId.isEmpty()) {
      return error("Missing 'file_id' parameter for read mode.");
    }
    String range = args.optString("range", GoogleServiceUtil.DEFAULT_RANGE);
    List<List<String>> values = GoogleServiceUtil.readSheet(ctx, alias, fileId, range);
    if (values.isEmpty()) {
      return message("Sheet is empty.");
    }
    StringBuilder formatted = new StringBuilder();
    for (List<String> row : values) {
      if (formatted.length() > 0) {
        formatted.append('\n');
      }
      formatted.append(String.join(", ", row));
    }
    return message("Spreadsheet content:\n" + formatted);
  }

  private static String downloadMode(ToolExecutionContext ctx, String alias, JSONObject args) throws Exception {
    String fileId = args.optString("file_id", null);
    if (fileId == null || fileId.isEmpty()) {
      return error("Missing 'file_id' parameter for download mode.");
    }
    String range = args.optString("range", GoogleServiceUtil.DEFAULT_RANGE);
    try {
      String filePath = GoogleServiceUtil.downloadSheetAsCsv(ctx, alias, fileId, range);
      return message("✅ CSV file downloaded at: " + filePath);
    } catch (Exception e) {
      return error("❌ Failed to download sheet as CSV: " + detail(e));
    }
  }

  private static String uploadMode(ToolExecutionContext ctx, String alias, JSONObject args) throws Exception {
    String file = args.optString("file_path", null);
    if (file == null || file.isEmpty()) {
      return error("Missing 'file_path' parameter for upload mode.");
    }
    Path path = FileToolSupport.readPath(ctx, file);
    String name = args.optString("name", null);
    if (name == null || name.isEmpty()) {
      name = path.getFileName().toString();
    }
    try {
      JSONObject uploaded = GoogleServiceUtil.uploadCsvAsSpreadsheet(ctx, alias, path, name);
      String link = "https://docs.google.com/spreadsheets/d/" + uploaded.getString("id") + "/edit";
      return message("✅ CSV file '" + uploaded.getString("name") + "' uploaded successfully.\n🔗 Link: " + link);
    } catch (Exception e) {
      return error("❌ Failed to upload CSV: " + detail(e));
    }
  }

  private static JSONArrayHeaders headers(JSONObject args) throws JSONException {
    org.codehaus.jettison.json.JSONArray values = args.optJSONArray("headers");
    List<String> result = new ArrayList<>();
    if (values != null) {
      for (int i = 0; i < values.length(); i++) {
        result.add(values.getString(i));
      }
    }
    return new JSONArrayHeaders(result);
  }

  private record JSONArrayHeaders(List<String> values) {
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
