package com.etendoerp.copilot.toolpack.tools;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;
import org.junit.Test;

public class MemoryToolTest {
  @Test
  public void advertisesMemoryModesAndArguments() {
    var spec = new MemoryTool().specification();
    assertEquals("MemoryTool", spec.name());
    assertTrue(spec.parameters().properties().keySet().containsAll(
        java.util.List.of("mode", "memory", "query", "memory_id", "k")));
    assertTrue(spec.parameters().required().contains("mode"));
  }
}
