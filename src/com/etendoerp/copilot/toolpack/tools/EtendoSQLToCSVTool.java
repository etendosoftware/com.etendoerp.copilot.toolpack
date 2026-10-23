package com.etendoerp.copilot.toolpack.tools;

import java.io.BufferedWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;

import javax.enterprise.context.ApplicationScoped;
import javax.inject.Named;

import org.apache.commons.csv.CSVFormat;
import org.apache.commons.csv.CSVPrinter;
import org.codehaus.jettison.json.JSONArray;
import org.codehaus.jettison.json.JSONException;
import org.codehaus.jettison.json.JSONObject;

import com.etendoerp.copilot.engine.tool.ServerTool;
import com.etendoerp.copilot.engine.tool.ToolExecutionContext;
import com.etendoerp.copilot.engine.tool.http.WebhookInvoker;

import dev.langchain4j.agent.tool.ToolSpecification;

/** Executes a role-filtered Etendo SQL query through its in-process webhook and writes CSV output. */
@ApplicationScoped
@Named("EtendoSQLToCSVTool")
public class EtendoSQLToCSVTool implements ServerTool {

  private static final String DESCRIPTION = "Tool to execute SQL queries in Etendo using the DBQueryExec webhook and convert results to CSV. This tool connects to Etendo's database through the DBQueryExec webhook, executes SELECT queries, and downloads the JSON result converted to CSV format. REQUIREMENTS: Only SELECT queries are allowed, all tables must have aliases (e.g., 'SELECT u.name FROM ad_user u'), and tables must be accessible to the current user. Security filters are automatically applied by Etendo. Authentication and Etendo host are handled automatically through the copilot context. Parameters: sql_query (required), output_file (optional), include_headers (optional, default: true).";

  @Override
  public String name() {
    return "EtendoSQLToCSVTool";
  }

  @Override
  public ToolSpecification specification() {
    return FileToolSupport.spec(name(), DESCRIPTION,
        "{\"sql_query\":{\"type\":\"string\",\"title\":\"Sql Query\",\"description\":\"SQL SELECT query to execute in Etendo database. All tables must have aliases (e.g., 'SELECT u.name FROM ad_user u').\"},"
            + "\"output_file\":{\"anyOf\":[{\"type\":\"string\"},{\"type\":\"null\"}],\"default\":null,\"title\":\"Output File\",\"description\":\"Path where to save the CSV file. If not provided, a temporary file will be created.\"},"
            + "\"include_headers\":{\"type\":\"boolean\",\"default\":true,\"title\":\"Include Headers\",\"description\":\"Whether to include column headers in the CSV output.\"}}",
        "sql_query");
  }

  @Override
  public String execute(JSONObject args, ToolExecutionContext ctx) throws Exception {
    try {
      String sql = args == null ? null : args.optString("sql_query", null);
      if (sql == null || sql.isEmpty()) {
        return error("Missing required parameter: 'sql_query'");
      }
      if (!validateSqlQuery(sql)) {
        return error("Invalid SQL query. Only SELECT queries are allowed and no dangerous keywords permitted. Note: Etendo also requires all tables to have aliases (e.g., 'FROM ad_user u').");
      }
      boolean includeHeaders = args.optBoolean("include_headers", true);
      String output = args.optString("output_file", null);
      Path destination = FileToolSupport.writePath(ctx, output == null || output.isEmpty()
          ? ToolWorkspace.workDir(ctx).resolve("etendo_query_result_" + UUID.randomUUID() + ".csv").toString()
          : output);

      JSONObject result;
      try {
        result = new JSONObject(WebhookInvoker.invoke(ctx, "DBQueryExec",
            Map.of("Query", sql, "Mode", "EXECUTE_QUERY")));
        if (result.has("error")) {
          throw new IllegalStateException("Webhook error: " + result.optString("error"));
        }
      } catch (Exception e) {
        return error("Failed to execute SQL query: " + message(e));
      }

      JSONArray columns;
      JSONArray rows;
      try {
        columns = arrayValue(result.opt("columns"));
        rows = arrayValue(result.opt("data"));
        if (columns == null || rows == null) {
          throw new IllegalArgumentException("Invalid webhook response format. Expected 'columns' and 'data' fields.");
        }
        if (rows.length() == 0) {
          throw new IllegalArgumentException("No data returned from SQL query.");
        }
        writeCsv(ctx, destination, columns, rows, includeHeaders);
      } catch (Exception e) {
        return error("Failed to convert result to CSV: " + message(e));
      }

      long size = Files.size(destination);
      double sizeMb = size / (1024.0 * 1024.0);
      int count = rows.length();
      String queryPreview = sql.length() > 100 ? sql.substring(0, 100) + "..." : sql;
      String message = String.format(Locale.ROOT,
          "✅ SQL query executed successfully!\n📊 Result: %d rows exported\n📁 CSV file saved at: %s\n📏 File size: %.2f MB\n🔍 Query: %s",
          count, destination, sizeMb, queryPreview);
      return new JSONObject().put("message", message).toString();
    } catch (Exception e) {
      return error("EtendoSQLToCSVTool error: " + message(e));
    }
  }

  static boolean validateSqlQuery(String query) {
    String lower = query.toLowerCase(Locale.ROOT).trim();
    String[] dangerous = { "drop", "delete", "truncate", "alter", "create", "insert", "update", "grant", "revoke", "exec", "execute", "sp_", "xp_" };
    for (String keyword : dangerous) {
      if (lower.contains(keyword)) {
        return false;
      }
    }
    return lower.startsWith("select");
  }

  private static JSONArray arrayValue(Object value) throws JSONException {
    if (value instanceof JSONArray array) {
      return array;
    }
    if (value instanceof String text) {
      return new JSONArray(text);
    }
    return null;
  }

  private static void writeCsv(ToolExecutionContext ctx, Path path, JSONArray columns, JSONArray rows,
      boolean includeHeaders) throws Exception {
    java.io.ByteArrayOutputStream bytes = new java.io.ByteArrayOutputStream();
    try (BufferedWriter writer = new BufferedWriter(new java.io.OutputStreamWriter(bytes, StandardCharsets.UTF_8));
        CSVPrinter printer = new CSVPrinter(writer, CSVFormat.DEFAULT)) {
      if (includeHeaders) printer.printRecord(values(columns));
      for (int i = 0; i < rows.length(); i++) {
        Object rowValue = rows.get(i);
        if (!(rowValue instanceof JSONArray row)) throw new IllegalArgumentException("Expected 'data' to be a list of lists (rows).");
        printer.printRecord(values(row));
      }
    }
    FileToolSupport.writeBytes(ctx, path.toString(), bytes.toByteArray());
  }

  private static List<Object> values(JSONArray array) throws JSONException {
    List<Object> values = new ArrayList<>(array.length());
    for (int i = 0; i < array.length(); i++) {
      Object value = array.get(i);
      values.add(value == JSONObject.NULL ? "" : value);
    }
    return values;
  }

  private static String message(Exception e) {
    return e.getMessage() == null ? e.getClass().getSimpleName() : e.getMessage();
  }

  private static String error(String value) throws JSONException {
    return new JSONObject().put("error", value).toString();
  }
}
