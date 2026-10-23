package com.etendoerp.copilot.toolpack.tools;

import java.io.BufferedReader;
import java.io.IOException;
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
import java.util.UUID;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

import javax.enterprise.context.ApplicationScoped;
import javax.inject.Named;

import org.apache.commons.csv.CSVFormat;
import org.apache.commons.csv.CSVParser;
import org.apache.commons.csv.CSVRecord;
import org.apache.poi.ss.usermodel.Cell;
import org.apache.poi.ss.usermodel.CellType;
import org.apache.poi.ss.usermodel.DateUtil;
import org.apache.poi.ss.usermodel.DataFormatter;
import org.apache.poi.ss.usermodel.Row;
import org.apache.poi.ss.usermodel.Sheet;
import org.apache.poi.ss.usermodel.Workbook;
import org.apache.poi.ss.usermodel.WorkbookFactory;
import org.codehaus.jettison.json.JSONArray;
import org.codehaus.jettison.json.JSONException;
import org.codehaus.jettison.json.JSONObject;
import org.openbravo.base.provider.OBProvider;
import org.openbravo.dal.core.OBContext;
import org.openbravo.dal.service.OBDal;

import com.etendoerp.copilot.data.CopilotApp;
import com.etendoerp.copilot.engine.tool.ServerTool;
import com.etendoerp.copilot.engine.tool.ToolExecutionContext;
import com.etendoerp.task.data.Status;
import com.etendoerp.task.data.Task;
import com.etendoerp.task.data.TaskType;

import dev.langchain4j.agent.tool.ToolSpecification;

/** Parses batch input files and creates Copilot tasks using Etendo's DAL model. */
@ApplicationScoped
@Named("TaskCreatorTool")
public class TaskCreatorTool implements ServerTool {

  static final String TASK_TYPE_COPILOT = "A83E397389DB42559B2D7719A442168F";
  static final String TASK_STATUS_PENDING = "D0FCC72902F84486A890B70C1EB10C9C";
  private static final DateTimeFormatter EXCEL_TIMESTAMP =
      DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss", Locale.ROOT);
  private static final String DESCRIPTION = "Processes a ZIP, CSV, or Excel file and creates a task for each extracted file or row. For ZIP files, each uncompressed file's full path is added to the question/request. For CSV or Excel files, the header row is skipped and each subsequent row task includes the header and the row data. If the file format is unsupported, a task is created with the file path.";

  @Override
  public String name() {
    return "TaskCreatorTool";
  }

  @Override
  public ToolSpecification specification() {
    return FileToolSupport.spec(name(), DESCRIPTION,
        "{\"question\":{\"type\":\"string\",\"title\":\"Question\",\"description\":\"Question/request for the Task. The tool will create a task for\\n        each extracted file or row. The question will be used as the task description,\\n        for  the item, so is recommended that be a singularized question/request.\\n        For example, if the file contains a list of products and the main objective is\\n        to \\\"process\\\" the products, the question should be \\\"Process the \\\"product\\\".\\\"\\n        \"},"
            + "\"file_path\":{\"type\":\"string\",\"title\":\"File Path\",\"description\":\"Path to the ZIP, CSV, XLS, or XLSX file.\"},"
            + "\"group_id\":{\"type\":\"string\",\"title\":\"Group ID\",\"description\":\"ID of the group to which the task belongs. If not provided, the tool will create it.\"},"
            + "\"groupby\":{\"type\":\"array\",\"items\":{\"type\":\"string\"},\"default\":[],\"title\":\"Group By\",\"description\":\"Optional list of column names to group rows by when processing CSV/XLS files. If provided, rows that share the same values for these columns will be sent as a single task (the task item will be a JSON array string with all rows in the group). If no grouping is desired, send an empty array [].\"},"
            + "\"task_type_id\":{\"anyOf\":[{\"type\":\"string\"},{\"type\":\"null\"}],\"title\":\"Task Type\",\"description\":\"ID of the task type. If not provided, the tool use the Copilot's default task type.\"},"
            + "\"status_id\":{\"anyOf\":[{\"type\":\"string\"},{\"type\":\"null\"}],\"title\":\"Status\",\"description\":\"ID of the pending status. If not provided, the tool will create it.\"},"
            + "\"agent_id\":{\"anyOf\":[{\"type\":\"string\"},{\"type\":\"null\"}],\"title\":\"Agent Id\",\"description\":\"ID of the agent to which the task is assigned. This agent will be who processes the task. If not provided, the tool will use the current main assistant's ID.\"},"
            + "\"preview\":{\"anyOf\":[{\"type\":\"boolean\"},{\"type\":\"null\"}],\"title\":\"Preview\",\"description\":\"If true, the tool will return the column names (or file contents for ZIP) instead of creating tasks.\"}}",
        "question", "file_path", "group_id", "task_type_id", "status_id", "agent_id", "preview");
  }

  @Override
  public String execute(JSONObject args, ToolExecutionContext ctx) throws Exception {
    try {
      String fileValue = args == null ? null : args.optString("file_path", null);
      if (fileValue == null || fileValue.isEmpty()) {
        throw new IllegalArgumentException("'file_path' parameter is required.");
      }
      Path file = FileToolSupport.readPath(ctx, fileValue);
      List<String> groupBy = readGroupBy(args == null ? null : args.opt("groupby"));
      if (args != null && args.optBoolean("preview", false)) {
        return new JSONObject().put("preview", previewFile(file)).toString();
      }

      String question = args == null ? "" : args.optString("question", "");
      String taskTypeId = valueOr(args == null ? null : args.optString("task_type_id", null), TASK_TYPE_COPILOT);
      String statusId = valueOr(args == null ? null : args.optString("status_id", null), TASK_STATUS_PENDING);
      String groupId = valueOr(args == null ? null : args.optString("group_id", null), ctx.conversationId());
      if (groupId == null || groupId.isBlank()) {
        groupId = UUID.randomUUID().toString();
      }
      String agentId = valueOr(args.optString("agent_id", null), ctx.agentId());
      List<String> items = processFile(file, groupBy, ctx);
      for (String item : items) {
        createTask(question, taskTypeId, statusId, agentId, groupId, item);
      }
      return new JSONObject().put("message",
          "Bulk Task creation process completed, the tasks from this batch group has the group id: " + groupId)
          .toString();
    } catch (IllegalArgumentException e) {
      return error("Tool error creating tasks: " + detail(e));
    } catch (Exception e) {
      return error("Unexpected error creating tasks: " + detail(e));
    }
  }

  static List<String> processFile(Path file, List<String> groupBy, ToolExecutionContext ctx) throws Exception {
    if (file == null || !Files.exists(file)) {
      throw new IllegalArgumentException("File not found: " + file);
    }
    String path = file.toString();
    if (path.endsWith(".zip")) {
      return processZip(file, ctx);
    }
    if (path.endsWith(".csv")) {
      return groupBy == null || groupBy.isEmpty() ? processCsv(file) : processGroupedCsv(file, groupBy);
    }
    if (path.endsWith(".xls") || path.endsWith(".xlsx")) {
      return processExcel(file, groupBy == null ? List.of() : groupBy);
    }
    return List.of(path);
  }

  static List<String> readGroupBy(Object groupBy) {
    if (groupBy == null || groupBy == JSONObject.NULL) {
      return List.of();
    }
    List<String> result = new ArrayList<>();
    if (groupBy instanceof JSONArray array) {
      for (int i = 0; i < array.length(); i++) {
        String value = array.optString(i, "").trim();
        if (!value.isEmpty()) {
          result.add(value);
        }
      }
      return result;
    }
    if (groupBy instanceof String text) {
      for (String value : text.split(",")) {
        if (!value.trim().isEmpty()) {
          result.add(value.trim());
        }
      }
      return result;
    }
    throw new IllegalArgumentException("Invalid 'groupby' parameter. Provide a list or a comma-separated string of column names.");
  }

  static JSONObject previewFile(Path file) throws Exception {
    if (file == null || !Files.exists(file)) {
      throw new IllegalArgumentException("File not found: " + file);
    }
    String path = file.toString();
    if (path.endsWith(".zip")) {
      JSONArray names = new JSONArray();
      try (ZipInputStream input = new ZipInputStream(Files.newInputStream(file))) {
        ZipEntry entry;
        while ((entry = input.getNextEntry()) != null) {
          if (!entry.getName().startsWith("__MACOSX/")) {
            names.put(entry.getName());
          }
        }
      } catch (Exception e) {
        throw new IllegalArgumentException("Error previewing ZIP file " + file + ": " + detail(e), e);
      }
      return new JSONObject().put("type", "zip").put("files", names);
    }
    if (path.endsWith(".csv")) {
      try (CSVParser parser = CSVFormat.DEFAULT.parse(Files.newBufferedReader(file, StandardCharsets.UTF_8))) {
        List<CSVRecord> records = parser.getRecords();
        if (records.isEmpty()) {
          throw new IOException("CSV file is empty.");
        }
        JSONArray headers = new JSONArray();
        for (String header : records.get(0)) {
          headers.put(header);
        }
        return new JSONObject().put("type", "csv").put("columns", headers);
      } catch (Exception e) {
        throw new IllegalArgumentException("Error previewing CSV file " + file + ": " + detail(e), e);
      }
    }
    if (path.endsWith(".xls") || path.endsWith(".xlsx")) {
      try (Workbook workbook = WorkbookFactory.create(file.toFile())) {
        return new JSONObject().put("type", "excel").put("columns", excelHeaders(workbook));
      } catch (Exception e) {
        throw new IllegalArgumentException("Error previewing Excel file " + file + ": " + detail(e), e);
      }
    }
    return new JSONObject().put("type", "file").put("name", file.getFileName().toString());
  }

  private static List<String> processZip(Path zipPath, ToolExecutionContext ctx) throws IOException {
    Path extractRoot = ToolWorkspace.workDir(ctx).resolve("copilotAttachedFiles").resolve(UUID.randomUUID().toString()).normalize();
    Files.createDirectories(extractRoot);
    List<String> extracted = new ArrayList<>();
    try (ZipInputStream input = new ZipInputStream(Files.newInputStream(zipPath))) {
      ZipEntry entry;
      while ((entry = input.getNextEntry()) != null) {
        String name = entry.getName();
        if (name.startsWith("__MACOSX/")) {
          continue;
        }
        Path destination = extractRoot.resolve(name).normalize();
        if (!destination.startsWith(extractRoot)) {
          throw new IOException("ZIP entry escapes the extraction directory: " + name);
        }
        if (entry.isDirectory()) {
          Files.createDirectories(destination);
        } else {
          if (destination.getParent() != null) {
            Files.createDirectories(destination.getParent());
          }
          Files.copy(input, destination);
          extracted.add(destination.toString());
        }
      }
    } catch (Exception e) {
      throw new IllegalArgumentException("Error processing ZIP file " + zipPath + ": " + detail(e), e);
    }
    return extracted;
  }

  private static List<String> processCsv(Path csvPath) throws IOException {
    List<String> result = new ArrayList<>();
    try (CSVParser parser = CSVFormat.DEFAULT.parse(Files.newBufferedReader(csvPath, StandardCharsets.UTF_8))) {
      List<CSVRecord> records = parser.getRecords();
      if (records.isEmpty()) {
        throw new IOException("CSV file is empty.");
      }
      List<String> headers = records.get(0).toList();
      for (int i = 1; i < records.size(); i++) {
        result.add(pythonDict(headers, records.get(i).toList()));
      }
    } catch (Exception e) {
      throw new IllegalArgumentException("Error processing CSV file " + csvPath + ": " + detail(e), e);
    }
    return result;
  }

  private static List<String> processGroupedCsv(Path csvPath, List<String> groupBy) throws Exception {
    try (BufferedReader reader = Files.newBufferedReader(csvPath, StandardCharsets.UTF_8);
        CSVParser parser = CSVFormat.DEFAULT.withFirstRecordAsHeader().parse(reader)) {
      List<String> headers = parser.getHeaderNames();
      validateGroupColumns(groupBy, headers, "CSV");
      Map<String, Integer> headerIndexes = parser.getHeaderMap();
      Map<List<String>, List<Map<String, String>>> groups = new LinkedHashMap<>();
      for (CSVRecord record : parser) {
        List<String> key = new ArrayList<>();
        Map<String, String> row = new LinkedHashMap<>();
        for (String header : headers) {
          Integer index = headerIndexes.get(header);
          String value = index == null || index >= record.size() ? null : record.get(index);
          row.put(header, value);
        }
        for (String column : groupBy) {
          key.add(row.get(column));
        }
        groups.computeIfAbsent(key, ignored -> new ArrayList<>()).add(row);
      }
      List<String> result = new ArrayList<>();
      for (List<Map<String, String>> rows : groups.values()) {
        result.add(groupedRowsJson(rows));
      }
      return result;
    } catch (IllegalArgumentException e) {
      throw e;
    } catch (Exception e) {
      throw new IllegalArgumentException("Error processing CSV file " + csvPath + " with grouping " + groupBy + ": " + detail(e), e);
    }
  }

  private static List<String> processExcel(Path excelPath, List<String> groupBy) throws Exception {
    try (Workbook workbook = WorkbookFactory.create(excelPath.toFile())) {
      Sheet sheet = workbook.getNumberOfSheets() == 0 ? null : workbook.getSheetAt(0);
      if (sheet == null || sheet.getPhysicalNumberOfRows() == 0) {
        throw new IllegalArgumentException("Error processing Excel file " + excelPath + ": file has no rows");
      }
      DataFormatter formatter = new DataFormatter();
      List<String> headers = rowValues(sheet.getRow(sheet.getFirstRowNum()), formatter);
      if (groupBy == null || groupBy.isEmpty()) {
        List<String> result = new ArrayList<>();
        for (int rowIndex = sheet.getFirstRowNum() + 1; rowIndex <= sheet.getLastRowNum(); rowIndex++) {
          Row row = sheet.getRow(rowIndex);
          if (row != null) {
            List<String> values = rowValues(row, formatter);
            if (values.stream().anyMatch(value -> !value.isEmpty())) {
              result.add(pythonExcelDict(headers, row, formatter));
            }
          }
        }
        return result;
      }
      validateGroupColumns(groupBy, headers, "Excel");
      Map<List<String>, List<Map<String, String>>> groups = new LinkedHashMap<>();
      for (int rowIndex = sheet.getFirstRowNum() + 1; rowIndex <= sheet.getLastRowNum(); rowIndex++) {
        Row row = sheet.getRow(rowIndex);
        if (row == null) {
          continue;
        }
        List<String> values = rowValues(row, formatter);
        if (values.stream().noneMatch(value -> !value.isEmpty())) {
          continue;
        }
        Map<String, String> object = rowMap(headers, values);
        List<String> key = new ArrayList<>();
        for (String column : groupBy) {
          key.add(object.get(column));
        }
        groups.computeIfAbsent(key, ignored -> new ArrayList<>()).add(object);
      }
      List<String> result = new ArrayList<>();
      List<Map.Entry<List<String>, List<Map<String, String>>>> sortedGroups = new ArrayList<>(groups.entrySet());
      sortedGroups.sort((left, right) -> compareGroupKeys(left.getKey(), right.getKey()));
      for (Map.Entry<List<String>, List<Map<String, String>>> group : sortedGroups) {
        result.add(groupedRowsJson(group.getValue()));
      }
      return result;
    } catch (IllegalArgumentException e) {
      throw e;
    } catch (Exception e) {
      throw new IllegalArgumentException("Error processing Excel file " + excelPath + " with grouping " + groupBy + ": " + detail(e), e);
    }
  }

  private static List<String> excelHeaders(Workbook workbook) {
    List<String> headers = new ArrayList<>();
    if (workbook.getNumberOfSheets() == 0) {
      return headers;
    }
    Sheet sheet = workbook.getSheetAt(0);
    Row header = sheet.getRow(sheet.getFirstRowNum());
    if (header != null) {
      headers.addAll(rowValues(header, new DataFormatter()));
    }
    return headers;
  }

  private static List<String> rowValues(Row row, DataFormatter formatter) {
    List<String> values = new ArrayList<>();
    if (row == null) {
      return values;
    }
    int last = Math.max(row.getLastCellNum(), 0);
    for (int i = 0; i < last; i++) {
      Cell cell = row.getCell(i, Row.MissingCellPolicy.RETURN_BLANK_AS_NULL);
      values.add(cell == null ? "" : formatter.formatCellValue(cell));
    }
    return values;
  }


  private static Map<String, String> rowMap(List<String> headers, List<String> values) {
    Map<String, String> row = new LinkedHashMap<>();
    for (int i = 0; i < headers.size(); i++) {
      row.put(headers.get(i), i < values.size() ? values.get(i) : "");
    }
    return row;
  }

  private static int compareGroupKeys(List<String> left, List<String> right) {
    int length = Math.min(left.size(), right.size());
    for (int i = 0; i < length; i++) {
      int comparison = String.valueOf(left.get(i)).compareTo(String.valueOf(right.get(i)));
      if (comparison != 0) {
        return comparison;
      }
    }
    return Integer.compare(left.size(), right.size());
  }
  private static String groupedRowsJson(List<Map<String, String>> rows) {
    StringBuilder json = new StringBuilder("[");
    for (int rowIndex = 0; rowIndex < rows.size(); rowIndex++) {
      if (rowIndex > 0) {
        json.append(", ");
      }
      json.append('{');
      boolean first = true;
      for (Map.Entry<String, String> entry : rows.get(rowIndex).entrySet()) {
        if (!first) {
          json.append(", ");
        }
        json.append(jsonString(entry.getKey())).append(": ");
        String value = entry.getValue();
        json.append(value == null ? "null" : jsonString(value));
        first = false;
      }
      json.append('}');
    }
    return json.append(']').toString();
  }

  private static String jsonString(String value) {
    StringBuilder escaped = new StringBuilder(value.length() + 2).append('"');
    for (int i = 0; i < value.length(); i++) {
      char current = value.charAt(i);
      switch (current) {
        case '"' -> escaped.append("\\\"");
        case '\\' -> escaped.append("\\\\");
        case '\b' -> escaped.append("\\b");
        case '\f' -> escaped.append("\\f");
        case '\n' -> escaped.append("\\n");
        case '\r' -> escaped.append("\\r");
        case '\t' -> escaped.append("\\t");
        default -> {
          if (current < 0x20) {
            escaped.append("\\u");
            for (int shift = 12; shift >= 0; shift -= 4) {
              escaped.append("0123456789abcdef".charAt((current >> shift) & 0x0F));
            }
          } else {
            escaped.append(current);
          }
        }
      }
    }
    return escaped.append('"').toString();
  }
  private static String pythonDict(List<String> headers, List<String> values) {
    Map<String, String> row = new LinkedHashMap<>();
    int limit = Math.min(headers.size(), values.size());
    for (int i = 0; i < limit; i++) {
      row.put(headers.get(i), values.get(i));
    }
    StringBuilder text = new StringBuilder("{");
    for (Map.Entry<String, String> entry : row.entrySet()) {
      if (text.length() > 1) {
        text.append(", ");
      }
      text.append(pythonQuote(entry.getKey())).append(": ").append(pythonQuote(entry.getValue()));
    }
    return text.append('}').toString();
  }

  private static String pythonExcelDict(List<String> headers, Row row, DataFormatter formatter) {
    StringBuilder text = new StringBuilder("{");
    for (int i = 0; i < headers.size(); i++) {
      if (i > 0) {
        text.append(", ");
      }
      Cell cell = row.getCell(i, Row.MissingCellPolicy.RETURN_BLANK_AS_NULL);
      text.append(pythonQuote(headers.get(i))).append(": ").append(pythonExcelValue(cell, formatter));
    }
    return text.append('}').toString();
  }

  private static String pythonExcelValue(Cell cell, DataFormatter formatter) {
    if (cell == null) {
      return "nan";
    }
    CellType type = cell.getCellType() == CellType.FORMULA ? cell.getCachedFormulaResultType() : cell.getCellType();
    return switch (type) {
      case STRING -> {
        String value = cell.getStringCellValue();
        yield value.isEmpty() ? "nan" : pythonQuote(value);
      }
      case BOOLEAN -> cell.getBooleanCellValue() ? "True" : "False";
      case NUMERIC -> {
        if (DateUtil.isCellDateFormatted(cell)) {
          String timestamp = DateUtil.getLocalDateTime(cell.getNumericCellValue()).format(EXCEL_TIMESTAMP);
          yield "Timestamp(" + pythonQuote(timestamp) + ")";
        }
        double value = cell.getNumericCellValue();
        if (value == Math.rint(value) && value >= Long.MIN_VALUE && value <= Long.MAX_VALUE) {
          yield Long.toString((long) value);
        }
        yield Double.toString(value);
      }
      case BLANK -> "nan";
      default -> pythonQuote(formatter.formatCellValue(cell));
    };
  }

  private static String pythonQuote(String value) {
    char quote = value.indexOf('\'') >= 0 && value.indexOf('"') < 0 ? '"' : '\'';
    StringBuilder repr = new StringBuilder(value.length() + 2).append(quote);
    for (int i = 0; i < value.length(); i++) {
      char current = value.charAt(i);
      switch (current) {
        case '\\' -> repr.append("\\\\");
        case '\n' -> repr.append("\\n");
        case '\r' -> repr.append("\\r");
        case '\t' -> repr.append("\\t");
        default -> {
          if (current == quote) {
            repr.append('\\').append(current);
          } else if (current < 0x20 || current == 0x7F) {
            repr.append("\\x")
                .append("0123456789abcdef".charAt((current >> 4) & 0x0F))
                .append("0123456789abcdef".charAt(current & 0x0F));
          } else {
            repr.append(current);
          }
        }
      }
    }
    return repr.append(quote).toString();
  }

  private static void validateGroupColumns(List<String> groupBy, List<String> headers, String type) {
    for (String column : groupBy) {
      if (!headers.contains(column)) {
        throw new IllegalArgumentException("Group by column '" + column + "' not found in " + type + " headers: " + headers);
      }
    }
  }

  private static void createTask(String question, String taskTypeId, String statusId, String agentId,
      String groupId, String item) {
    Task task = OBProvider.getInstance().get(Task.class);
    task.setNewOBObject(true);
    task.setETCOPAgent(agentId == null || agentId.isBlank() ? null : OBDal.getInstance().get(CopilotApp.class, agentId));
    task.setEtcopQuestion(question + ":" + item);
    task.setStatus(OBDal.getInstance().get(Status.class, statusId));
    task.setEtcopGroup(groupId);
    task.setAssignedUser(OBContext.getOBContext().getUser());
    task.setTaskType(OBDal.getInstance().get(TaskType.class, taskTypeId));
    OBDal.getInstance().save(task);
  }

  private static String valueOr(String value, String fallback) {
    return value == null || value.isEmpty() ? fallback : value;
  }

  private static String detail(Exception e) {
    return e.getMessage() == null ? e.getClass().getSimpleName() : e.getMessage();
  }

  private static String error(String message) throws JSONException {
    return new JSONObject().put("error", message).toString();
  }
}
