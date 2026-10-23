package com.etendoerp.copilot.toolpack.tools;

import static org.junit.Assert.assertEquals;

import org.junit.Test;

public class AttachFileToolTest {

  @Test
  public void toolSpecUsesRegisteredToolName() {
    assertEquals("AttachFileTool", new AttachFileTool().specification().name());
  }
}
