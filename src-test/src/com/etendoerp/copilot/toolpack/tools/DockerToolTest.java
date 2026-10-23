package com.etendoerp.copilot.toolpack.tools;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;

class DockerToolTest {
  @Test void filtersCredentialKeysFromContainerEnvironment() {
    assertTrue(DockerTool.isSecretKey("ETENDO_TOKEN"));
    assertTrue(DockerTool.isSecretKey("apiKey"));
    assertTrue(DockerTool.isSecretKey("password"));
    assertTrue(DockerTool.isSecretKey("auth"));
    assertFalse(DockerTool.isSecretKey("model"));
    assertFalse(DockerTool.isSecretKey("temperature"));
  }

  @Test void dockerNetworkIsOffUnlessConfigured() {
    String key = "copilot.tools.docker.network.enabled";
    String previous = System.getProperty(key);
    try {
      System.clearProperty(key);
      assertFalse(DockerTool.networkEnabled(null));
      System.setProperty(key, "true");
      assertTrue(DockerTool.networkEnabled(null));
      System.setProperty(key, "false");
      assertFalse(DockerTool.networkEnabled(null));
    } finally {
      if (previous == null) System.clearProperty(key); else System.setProperty(key, previous);
    }
  }
}
