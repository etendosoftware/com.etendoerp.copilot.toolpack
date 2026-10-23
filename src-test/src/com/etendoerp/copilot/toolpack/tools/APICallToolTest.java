package com.etendoerp.copilot.toolpack.tools;

import static org.junit.Assert.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import org.junit.Test;

public class APICallToolTest {

  @Test
  public void appendsQueryValuesWithPythonToolEncodingRules() throws Exception {
    assertEquals("/records?active=True", APICallTool.appendQuery("/records", "{\"active\":true}"));
    assertEquals("/records?count=2", APICallTool.appendQuery("/records", "{\"count\":2}"));
    assertEquals("/records?names=one,two", APICallTool.appendQuery("/records", "{\"names\":[\"one\",\"two\"]}"));
    assertEquals("/records?text=two%20words", APICallTool.appendQuery("/records", "{\"text\":\"two words\"}"));
  }

  @Test
  public void appendsToExistingQueryString() throws Exception {
    assertEquals("/records?limit=5&offset=10", APICallTool.appendQuery("/records?limit=5", "{\"offset\":10}"));
  }

  @Test
  public void rejectsNonObjectQueryParameters() {
    assertThrows(IllegalArgumentException.class,
        () -> APICallTool.appendQuery("/records", "limit=5"));
  }
}
