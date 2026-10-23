package com.etendoerp.copilot.toolpack.tools;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNotNull;

import org.junit.Test;

public class ToolSpecificationsTest {
  @Test public void tavilyContractNamesRequiredQuery() {
    var spec = new TavilySearchTool().specification();
    assertEquals("TavilySearchTool", spec.name());
    assertNotNull(spec.parameters());
  }

  @Test public void audioContractNamesRequiredPath() {
    var spec = new AudioTool().specification();
    assertEquals("AudioTool", spec.name());
    assertNotNull(spec.parameters());
  }
  @Test public void sendEmailContractNamesAllRequiredFields() {
    var spec = new SendEmailTool().specification();
    assertEquals("SendEmailTool", spec.name());
    assertNotNull(spec.parameters());
  }

}
