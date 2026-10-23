package com.etendoerp.copilot.toolpack.tools;

import java.net.http.HttpRequest;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import org.apache.commons.csv.CSVFormat;
import org.apache.commons.csv.CSVPrinter;
import org.codehaus.jettison.json.JSONArray;
import org.codehaus.jettison.json.JSONException;
import org.codehaus.jettison.json.JSONObject;

import com.etendoerp.copilot.engine.tool.ToolExecutionContext;
import com.etendoerp.copilot.engine.tool.http.EtendoHttp;

/** Shared Google Drive and Sheets REST operations used by the toolpack tools. */
public final class GoogleServiceUtil {

  public static final String DEFAULT_RANGE = "A1:Z1000";
  public static final String APPLICATION_JSON = "application/json";
  private static final String DRIVE_API = "https://www.googleapis.com/drive/v3/files";
  private static final String DRIVE_UPLOAD_API = "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart";
  private static final String SHEETS_API = "https://sheets.googleapis.com/v4/spreadsheets";
  private static final Pattern SHEET_URL = Pattern.compile("https://docs\\.google\\.com/spreadsheets/d/([a-zA-Z0-9-_]+)");
  private static final DateTimeFormatter DOWNLOAD_STAMP = DateTimeFormatter.ofPattern("yyyyMMdd_HHmmss", Locale.ROOT);
  private static final Map<String, String> MIME_TYPES = Map.of(
      "spreadsheet", "application/vnd.google-apps.spreadsheet",
      "doc", "application/vnd.google-apps.document",
      "slides", "application/vnd.google-apps.presentation",
      "pdf", "application/pdf",
      "pdfs", "application/pdf");

  private GoogleServiceUtil() {
  }

  public static String getTokenByAlias(ToolExecutionContext ctx, String alias) {
    Object stored = ctx.attributes().get("oauth_tokens");
    if (!(stored instanceof Map<?, ?> tokens) || !tokens.containsKey(alias)) {
      throw new IllegalArgumentException("Token with alias '" + alias + "' not found.");
    }
    Object tokenInfo = tokens.get(alias);
    if (!(tokenInfo instanceof Map<?, ?> tokenMap) || tokenMap.get("token") == null) {
      throw new IllegalArgumentException("Token with alias '" + alias + "' not found.");
    }
    return String.valueOf(tokenMap.get("token"));
  }

  public static String extractSheetIdFromUrl(String url) {
    Matcher match = SHEET_URL.matcher(url == null ? "" : url);
    if (!match.find()) {
      throw new IllegalArgumentException("Invalid URL. Couldn't extract spreadsheet ID.");
    }
    return match.group(1);
  }

  public static String getTabName(ToolExecutionContext ctx, int index, String sheetId, String alias) throws Exception {
    JSONObject spreadsheet = get(ctx, alias, SHEETS_API + "/" + pathSegment(sheetId));
    JSONArray sheets = spreadsheet.optJSONArray("sheets");
    if (sheets == null || sheets.length() == 0) {
      throw new IllegalStateException("Spreadsheet doesn't contain tabs.");
    }
    int resolvedIndex = index < 0 ? sheets.length() + index : index;
    if (resolvedIndex < 0 || resolvedIndex >= sheets.length()) {
      throw new IllegalArgumentException("Wrong tab number.");
    }
    return sheets.getJSONObject(resolvedIndex).getJSONObject("properties").getString("title");
  }

  public static List<List<String>> readSheet(ToolExecutionContext ctx, String alias, String fileId,
      String range) throws Exception {
    String rangeValue = range == null || range.isEmpty() ? DEFAULT_RANGE : range;
    String url = SHEETS_API + "/" + pathSegment(fileId) + "/values/" + pathSegment(rangeValue);
    JSONObject response = get(ctx, alias, url);
    JSONArray rows = response.optJSONArray("values");
    List<List<String>> result = new ArrayList<>();
    if (rows == null) {
      return result;
    }
    for (int i = 0; i < rows.length(); i++) {
      JSONArray row = rows.optJSONArray(i);
      List<String> values = new ArrayList<>();
      if (row != null) {
        for (int j = 0; j < row.length(); j++) {
          Object value = row.get(j);
          values.add(value == JSONObject.NULL ? "" : String.valueOf(value));
        }
      }
      result.add(values);
    }
    return result;
  }

  public static JSONObject updateSpreadsheetValues(ToolExecutionContext ctx, String fileId, String alias,
      String range, List<? extends List<?>> values) throws Exception {
    JSONArray rowValues = new JSONArray();
    for (List<?> row : values) {
      JSONArray rowArray = new JSONArray();
      for (Object value : row) {
        rowArray.put(value);
      }
      rowValues.put(rowArray);
    }
    JSONObject body = new JSONObject().put("range", range).put("majorDimension", "ROWS").put("values", rowValues);
    String url = SHEETS_API + "/" + pathSegment(fileId) + "/values/" + pathSegment(range)
        + "?valueInputOption=RAW";
    return requestJson(ctx, alias, "PUT", url, body.toString());
  }

  public static List<JSONObject> listAccessibleFiles(ToolExecutionContext ctx, String fileType, String alias)
      throws Exception {
    String mimeType = MIME_TYPES.get(fileType == null ? "" : fileType.toLowerCase(Locale.ROOT));
    if (mimeType == null) {
      throw new IllegalArgumentException("Unsupported file type: " + fileType);
    }
    String query = "mimeType='" + mimeType + "'";
    JSONObject response = get(ctx, alias, DRIVE_API + "?q=" + query(query)
        + "&fields=" + query("files(id,name,mimeType)") + "&pageSize=100", "Error getting files: ");
    JSONArray files = response.optJSONArray("files");
    List<JSONObject> result = new ArrayList<>();
    if (files != null) {
      for (int i = 0; i < files.length(); i++) {
        result.add(files.getJSONObject(i));
      }
    }
    return result;
  }

  public static JSONObject createDriveFile(ToolExecutionContext ctx, String name, String mimeType,
      String alias) throws Exception {
    JSONObject metadata = new JSONObject().put("name", name).put("mimeType", mimeType);
    return requestJson(ctx, alias, "POST", DRIVE_API, metadata.toString());
  }

  public static String getDriveFileName(ToolExecutionContext ctx, String alias, String fileId) throws Exception {
    JSONObject response = get(ctx, alias, DRIVE_API + "/" + pathSegment(fileId) + "?fields=name");
    return response.optString("name", "spreadsheet");
  }

  public static String downloadSheetAsCsv(ToolExecutionContext ctx, String alias, String fileId,
      String range) throws Exception {
    List<List<String>> values = readSheet(ctx, alias, fileId, range);
    if (values.isEmpty()) {
      throw new IllegalStateException("No data found in the specified sheet or range.");
    }
    String fileName = getDriveFileName(ctx, alias, fileId);
    String safeName = fileName.replaceAll("[^\\p{Alnum}_-]", "_");
    Path destination = ToolWorkspace.resolveWrite(ctx, ToolWorkspace.workDir(ctx).resolve("temp_" + safeName + "_"
        + LocalDateTime.now().format(DOWNLOAD_STAMP) + ".csv").toString());
    java.io.StringWriter writer = new java.io.StringWriter();
    try (CSVPrinter printer = new CSVPrinter(writer, CSVFormat.DEFAULT)) {
      for (List<String> row : values) printer.printRecord(row);
    }
    FileToolSupport.writeBytes(ctx, destination.toString(), writer.toString().getBytes(StandardCharsets.UTF_8));
    return destination.toString();
  }

  public static JSONObject uploadFileSimple(ToolExecutionContext ctx, String alias, Path localPath,
      String driveFilename, String mimeType) throws Exception {
    if (!Files.isRegularFile(localPath)) {
      throw new IllegalArgumentException("File not found: " + localPath);
    }
    JSONObject metadata = new JSONObject().put("name", driveFilename);
    return multipartUpload(ctx, alias, localPath, driveFilename, mimeType, metadata, false);
  }

  public static JSONObject uploadCsvAsSpreadsheet(ToolExecutionContext ctx, String alias,
      Path localCsvPath, String sheetName) throws Exception {
    if (!Files.isRegularFile(localCsvPath)) {
      throw new IllegalArgumentException("File not found: " + localCsvPath);
    }
    JSONObject metadata = new JSONObject().put("name", sheetName)
        .put("mimeType", "application/vnd.google-apps.spreadsheet");
    return multipartUpload(ctx, alias, localCsvPath, localCsvPath.getFileName().toString(),
        "text/csv", metadata, true);
  }

  private static JSONObject multipartUpload(ToolExecutionContext ctx, String alias, Path filePath,
      String filename, String mimeType, JSONObject metadata, boolean csvSpreadsheetUpload) throws Exception {
    String token = getTokenByAlias(ctx, alias);
    String boundary = "copilot-" + java.util.UUID.randomUUID();
    byte[] metadataPart = ("--" + boundary + "\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n"
        + metadata + "\r\n--" + boundary + "\r\nContent-Type: " + mimeType
        + "\r\nContent-Disposition: attachment; filename=\"" + quoteFilename(filename)
        + "\"\r\n\r\n").getBytes(StandardCharsets.UTF_8);
    byte[] finalBoundary = ("\r\n--" + boundary + "--\r\n").getBytes(StandardCharsets.UTF_8);
    HttpRequest.BodyPublisher content = HttpRequest.BodyPublishers.concat(
        HttpRequest.BodyPublishers.ofByteArray(metadataPart),
        HttpRequest.BodyPublishers.ofFile(filePath),
        HttpRequest.BodyPublishers.ofByteArray(finalBoundary));
    Map<String, String> headers = new LinkedHashMap<>();
    headers.put("Authorization", "Bearer " + token);
    headers.put("Content-Type", "multipart/related; boundary=" + boundary);
    EtendoHttp.HttpResult response = EtendoHttp.callBody(ctx, "POST", DRIVE_UPLOAD_API, headers, content, null);
    if (response.status() != 200) {
      String operation = csvSpreadsheetUpload ? "Failed to upload CSV as spreadsheet: " : "Upload failed: ";
      throw new IllegalStateException(operation + response.status() + " - " + response.body());
    }
    return new JSONObject(response.body());
  }

  private static JSONObject get(ToolExecutionContext ctx, String alias, String url) throws Exception {
    return get(ctx, alias, url, null);
  }

  private static JSONObject get(ToolExecutionContext ctx, String alias, String url,
      String operationErrorPrefix) throws Exception {
    Map<String, String> headers = new LinkedHashMap<>();
    headers.put("Authorization", "Bearer " + getTokenByAlias(ctx, alias));
    EtendoHttp.HttpResult response = EtendoHttp.call(ctx, "GET", url, headers, null, null);
    if (response.status() != 200) {
      if (operationErrorPrefix != null) {
        throw new IllegalStateException(operationErrorPrefix + response.status());
      }
      if (response.status() == 401) {
        throw new IllegalStateException("Unauthorized Operation - Refresh the token.");
      }
      throw new IllegalStateException("Google API request failed: HTTP " + response.status());
    }
    return new JSONObject(response.body());
  }

  private static JSONObject requestJson(ToolExecutionContext ctx, String alias, String method,
      String url, String body) throws Exception {
    Map<String, String> headers = new LinkedHashMap<>();
    headers.put("Authorization", "Bearer " + getTokenByAlias(ctx, alias));
    headers.put("Content-Type", APPLICATION_JSON);
    headers.put("Accept", APPLICATION_JSON);
    EtendoHttp.HttpResult response = EtendoHttp.call(ctx, method, url, headers, body, null);
    if (response.status() != 200) {
      if (response.status() == 401) {
        throw new IllegalStateException("Unauthorized Operation - Refresh the token.");
      }
      if ("POST".equals(method)) {
        throw new IllegalStateException("Failed to create file: HTTP " + response.status());
      }
      throw new IllegalStateException("Google API request failed: HTTP " + response.status() + " - " + response.body());
    }
    return new JSONObject(response.body());
  }

  private static String query(String value) {
    return URLEncoder.encode(value, StandardCharsets.UTF_8).replace("+", "%20");
  }

  private static String pathSegment(String value) {
    return query(value);
  }

  private static String quoteFilename(String name) {
    return name.replace("\\", "_").replace("\"", "_").replace("\r", "_").replace("\n", "_");
  }

}
