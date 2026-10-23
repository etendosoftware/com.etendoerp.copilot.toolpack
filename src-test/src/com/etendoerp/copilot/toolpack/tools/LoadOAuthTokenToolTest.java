package com.etendoerp.copilot.toolpack.tools;

import static org.junit.Assert.assertEquals;

import org.junit.Test;

public class LoadOAuthTokenToolTest {

  @Test
  public void toolSpecUsesRegisteredToolName() {
    assertEquals("LoadOAuthTokenTool", new LoadOAuthTokenTool().specification().name());
  }
}
