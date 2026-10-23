package com.etendoerp.copilot.toolpack.tools;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNotNull;

import org.junit.Test;

public class GoogleToolsTest {

  @Test
  public void driveToolExposesItsPythonToolNameAndSchema() {
    var specification = new GoogleDriveTool().specification();
    assertEquals("GoogleDriveTool", specification.name());
    assertNotNull(specification.parameters());
  }

  @Test
  public void spreadsheetsToolExposesItsPythonToolNameAndSchema() {
    var specification = new GoogleSpreadsheetsTool().specification();
    assertEquals("GoogleSpreadsheetsTool", specification.name());
    assertNotNull(specification.parameters());
  }
}
