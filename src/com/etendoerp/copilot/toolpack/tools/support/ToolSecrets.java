package com.etendoerp.copilot.toolpack.tools.support;

import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;

import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;
import org.openbravo.base.session.OBPropertiesProvider;

/** Transitional lookup for tool API credentials. */
public final class ToolSecrets {
  private static final Logger log = LogManager.getLogger(ToolSecrets.class);
  private static final Set<String> WARNED = ConcurrentHashMap.newKeySet();

  private ToolSecrets() {}

  /** Reads the legacy Etendo property first, then the same-named environment variable. */
  public static String get(String name) {
    if (WARNED.add(name)) {
      log.warn("Tool secret '{}' is read from legacy configuration; migrate it to managed credentials when available.", name);
    }
    try {
      String value = OBPropertiesProvider.getInstance().getOpenbravoProperties().getProperty(name);
      if (value != null && !value.isBlank()) return value;
    } catch (RuntimeException ignored) {
      // Tools may also run without a loaded Openbravo properties instance in tests.
    }
    String envName = name.replace('.', '_').toUpperCase(java.util.Locale.ROOT);
    String value = System.getenv(envName);
    if (value == null || value.isBlank()) value = System.getenv(name);
    return value == null || value.isBlank() ? null : value;
  }
}
