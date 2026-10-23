package com.etendoerp.copilot.toolpack.tools;

import static org.junit.Assert.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.Assert.assertTrue;

import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

import org.apache.poi.ss.usermodel.Row;
import org.apache.poi.ss.usermodel.Sheet;
import org.apache.poi.xssf.usermodel.XSSFWorkbook;
import org.codehaus.jettison.json.JSONArray;
import org.codehaus.jettison.json.JSONObject;
import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.TemporaryFolder;

public class TaskCreatorToolTest {

  @Rule
  public TemporaryFolder temporaryFolder = new TemporaryFolder();

  @Test
  public void csvRowsBecomePythonStyleDictionaries() throws Exception {
    Path csv = temporaryFolder.newFile("rows.csv").toPath();
    Files.writeString(csv, "name,note\nAda,\"hello, world\"\n", StandardCharsets.UTF_8);

    List<String> rows = TaskCreatorTool.processFile(csv, List.of(), null);

    assertEquals(List.of("{'name': 'Ada', 'note': 'hello, world'}"), rows);
  }

  @Test
  public void groupedCsvKeepsFirstSeenGroupOrderAndCombinesRowsAsJson() throws Exception {
    Path csv = temporaryFolder.newFile("groups.csv").toPath();
    Files.writeString(csv, "kind,name\nB,one\nA,two\nB,three\n", StandardCharsets.UTF_8);

    List<String> groups = TaskCreatorTool.processFile(csv, List.of("kind"), null);

    assertEquals(2, groups.size());
    assertEquals("[{\"kind\": \"B\", \"name\": \"one\"}, {\"kind\": \"B\", \"name\": \"three\"}]", groups.get(0));
    JSONArray first = new JSONArray(groups.get(0));
    JSONArray second = new JSONArray(groups.get(1));
    assertEquals("B", first.getJSONObject(0).getString("kind"));
    assertEquals("one", first.getJSONObject(0).getString("name"));
    assertEquals("three", first.getJSONObject(1).getString("name"));
    assertEquals("A", second.getJSONObject(0).getString("kind"));
  }

  @Test
  public void groupedExcelRowsAreSortedByGroupKeys() throws Exception {
    Path excel = temporaryFolder.newFile("groups.xlsx").toPath();
    try (XSSFWorkbook workbook = new XSSFWorkbook(); OutputStream output = Files.newOutputStream(excel)) {
      Sheet sheet = workbook.createSheet();
      Row header = sheet.createRow(0);
      header.createCell(0).setCellValue("kind");
      header.createCell(1).setCellValue("name");
      Row first = sheet.createRow(1);
      first.createCell(0).setCellValue("B");
      first.createCell(1).setCellValue("one");
      Row second = sheet.createRow(2);
      second.createCell(0).setCellValue("A");
      second.createCell(1).setCellValue("two");
      workbook.write(output);
    }

    List<String> groups = TaskCreatorTool.processFile(excel, List.of("kind"), null);
    JSONArray firstGroup = new JSONArray(groups.get(0));

    assertEquals("A", firstGroup.getJSONObject(0).getString("kind"));
  }

  @Test
  public void excelRowsKeepNumbersAndPythonStringQuoting() throws Exception {
    Path excel = temporaryFolder.newFile("typed-rows.xlsx").toPath();
    try (XSSFWorkbook workbook = new XSSFWorkbook(); OutputStream output = Files.newOutputStream(excel)) {
      Sheet sheet = workbook.createSheet();
      Row header = sheet.createRow(0);
      header.createCell(0).setCellValue("count");
      header.createCell(1).setCellValue("name");
      Row row = sheet.createRow(1);
      row.createCell(0).setCellValue(1);
      row.createCell(1).setCellValue("O'Reilly");
      workbook.write(output);
    }

    List<String> items = TaskCreatorTool.processFile(excel, List.of(), null);

    assertEquals(List.of("{'count': 1, 'name': \"O'Reilly\"}"), items);
  }

  @Test
  public void groupedCsvEscapesJsonQuotesAndNewlines() throws Exception {
    Path csv = temporaryFolder.newFile("escaped-groups.csv").toPath();
    Files.writeString(csv, "kind,note\nA,\"say \"\"hi\"\"\nand leave\"\n", StandardCharsets.UTF_8);

    List<String> groups = TaskCreatorTool.processFile(csv, List.of("kind"), null);
    JSONArray rows = new JSONArray(groups.get(0));

    assertEquals("say \"hi\"\nand leave", rows.getJSONObject(0).getString("note"));
  }

  @Test
  public void groupedCsvRejectsUnknownGroupColumn() throws Exception {
    Path csv = temporaryFolder.newFile("missing-column.csv").toPath();
    Files.writeString(csv, "name\nAda\n", StandardCharsets.UTF_8);

    IllegalArgumentException error = assertThrows(IllegalArgumentException.class,
        () -> TaskCreatorTool.processFile(csv, List.of("department"), null));

    assertTrue(error.getMessage().contains("Group by column 'department' not found in CSV headers"));
  }

  @Test
  public void zipTraversalIsRejected() throws Exception {
    String previousWorkspace = System.getProperty("COPILOT_WORKSPACE");
    System.setProperty("COPILOT_WORKSPACE", temporaryFolder.getRoot().toPath().toString());
    try {
      Path zip = temporaryFolder.newFile("unsafe.zip").toPath();
      try (OutputStream file = Files.newOutputStream(zip); ZipOutputStream output = new ZipOutputStream(file)) {
        output.putNextEntry(new ZipEntry("../escape.txt"));
        output.write("unsafe".getBytes(StandardCharsets.UTF_8));
        output.closeEntry();
      }

      IllegalArgumentException error = assertThrows(IllegalArgumentException.class,
          () -> TaskCreatorTool.processFile(zip, List.of(), null));
      assertTrue(error.getMessage().contains("ZIP entry escapes the extraction directory"));
    } finally {
      if (previousWorkspace == null) {
        System.clearProperty("COPILOT_WORKSPACE");
      } else {
        System.setProperty("COPILOT_WORKSPACE", previousWorkspace);
      }
    }
  }

  @Test
  public void groupByAcceptsListsAndCommaSeparatedCompatibilityInput() throws Exception {
    assertEquals(List.of("kind", "region"), TaskCreatorTool.readGroupBy(new JSONArray("[\"kind\", \"region\"]")));
    assertEquals(List.of("kind", "region"), TaskCreatorTool.readGroupBy("kind, region"));
  }

  @Test
  public void previewReturnsCsvColumnNames() throws Exception {
    Path csv = temporaryFolder.newFile("preview.csv").toPath();
    Files.writeString(csv, "name,department\nAda,Engineering\n", StandardCharsets.UTF_8);

    JSONObject preview = TaskCreatorTool.previewFile(csv);

    assertEquals("csv", preview.getString("type"));
    assertEquals("name", preview.getJSONArray("columns").getString(0));
    assertEquals("department", preview.getJSONArray("columns").getString(1));
  }
}
