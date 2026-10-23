package com.etendoerp.copilot.toolpack.tools;

import java.io.Reader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import javax.enterprise.context.ApplicationScoped;
import javax.inject.Named;

import org.apache.commons.csv.CSVFormat;
import org.apache.commons.csv.CSVParser;
import org.apache.poi.ss.usermodel.DataFormatter;
import org.apache.poi.ss.usermodel.Row;
import org.apache.poi.ss.usermodel.WorkbookFactory;
import org.codehaus.jettison.json.JSONArray;
import org.codehaus.jettison.json.JSONObject;

import com.etendoerp.copilot.engine.tool.ServerTool;
import com.etendoerp.copilot.engine.tool.ToolExecutionContext;
import dev.langchain4j.agent.tool.ToolSpecification;

@ApplicationScoped
@Named("XLSTool")
public class XLSTool implements ServerTool {
  public String name() { return "XLSTool"; }
  public ToolSpecification specification() {
    return FileToolSupport.spec(name(), "A tool to read an XLS/CSV file and retrieve its content.",
        "{\"path\":{\"type\":\"string\",\"description\":\"XLS/CSV file path\"},\"only_headers\":{\"type\":\"boolean\",\"default\":false,\"description\":\"Mode to only read the headers of the file\"}}", "path");
  }

  public String execute(JSONObject arguments, ToolExecutionContext context) throws Exception {
    String input = FileToolSupport.requiredString(arguments, "path");
    Path file = FileToolSupport.readPath(context, input);
    if (!Files.isRegularFile(file)) throw new IllegalArgumentException("Filename " + input + " doesn't exist");
    List<JSONArray> sheets = readAllSheets(file);
    JSONArray rows = sheets.isEmpty() ? new JSONArray() : sheets.get(0);
    JSONArray result = new JSONArray();
    if (arguments.optBoolean("only_headers", false)) {
      if (rows.length() > 0) for (int i = 0; i < rows.getJSONArray(0).length(); i++) result.put(rows.getJSONArray(0).get(i));
    } else result = rows;
    return result.toString();
  }

  /** Read each CSV or workbook sheet as an array of displayed cell strings. */
  static List<JSONArray> readAllSheets(Path file) throws Exception {
    String filename = file.getFileName().toString();
    String ext = filename.substring(filename.lastIndexOf('.') + 1).toLowerCase();
    List<JSONArray> sheets = new ArrayList<>();
    if (ext.equals("csv")) {
      JSONArray rows = new JSONArray();
      try (Reader reader = Files.newBufferedReader(file, StandardCharsets.UTF_8);
          CSVParser parser = CSVFormat.DEFAULT.builder().setHeader().setSkipHeaderRecord(true).build().parse(reader)) {
        JSONArray header = new JSONArray();
        for (String name : parser.getHeaderNames()) header.put(name);
        rows.put(header);
        for (var record : parser) {
          JSONArray row = new JSONArray();
          for (String value : record) row.put(value);
          rows.put(row);
        }
      }
      sheets.add(rows);
      return sheets;
    }
    if (!ext.equals("xls") && !ext.equals("xlsx")) throw new IllegalArgumentException("The file must have a .xls, .xlsx, or .csv extension");
    try (var workbook = WorkbookFactory.create(file.toFile())) {
      DataFormatter formatter = new DataFormatter();
      for (var sheet : workbook) {
        JSONArray rows = new JSONArray();
        for (Row row : sheet) {
          JSONArray values = new JSONArray();
          for (int column = 0; column < row.getLastCellNum(); column++) values.put(formatter.formatCellValue(row.getCell(column)));
          rows.put(values);
        }
        sheets.add(rows);
      }
    }
    return sheets;
  }
}
