package com.etendoerp.copilot.toolpack.tools;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

import java.util.List;

import org.codehaus.jettison.json.JSONArray;
import org.codehaus.jettison.json.JSONObject;
import org.junit.Test;

import dev.langchain4j.data.message.ImageContent;
import dev.langchain4j.data.message.SystemMessage;
import dev.langchain4j.data.message.TextContent;
import dev.langchain4j.data.message.UserMessage;

public class ExcelOCRToolTest {
  @Test
  public void specificationMatchesPythonToolContract() throws Exception {
    var specification = new ExcelOCRTool().specification();
    assertEquals("ExcelOCRTool", specification.name());
    assertEquals("Extract structured data from Excel using OCR + Vision model.", specification.description());
    assertTrue(specification.parameters().toString().contains("path"));
    assertTrue(specification.parameters().toString().contains("question"));
  }

  @Test
  public void promptAndTableImageAreBuiltFromSpreadsheetRows() throws Exception {
    JSONArray rows = new JSONArray().put(new JSONArray().put("Invoice").put("Total"))
        .put(new JSONArray().put("INV-1").put("42.00"));
    List<dev.langchain4j.data.message.ChatMessage> messages = ExcelOCRTool.buildMessages(rows, "Extract invoice number and total");
    assertEquals(3, messages.size());
    assertTrue(((SystemMessage) messages.get(0)).text().contains("Don't summarize or omit rows"));
    UserMessage imageMessage = (UserMessage) messages.get(1);
    assertTrue(imageMessage.contents().get(0) instanceof ImageContent);
    assertEquals("image/png", ((ImageContent) imageMessage.contents().get(0)).image().mimeType());
    UserMessage questionMessage = (UserMessage) messages.get(2);
    assertTrue(questionMessage.contents().get(0) instanceof TextContent);
    assertEquals("Extract invoice number and total", ((TextContent) questionMessage.contents().get(0)).text());
  }

  @Test
  public void longSheetsArePagedWithoutDroppingRows() throws Exception {
    JSONArray rows = new JSONArray();
    for (int i = 0; i < 71; i++) rows.put(new JSONArray().put("row " + i));
    List<dev.langchain4j.data.message.ChatMessage> messages = ExcelOCRTool.buildMessages(rows, "Extract all");
    assertEquals(4, messages.size());
    assertEquals("Extract all", ((TextContent) ((UserMessage) messages.get(3)).contents().get(0)).text());
  }
}
