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

  /** Reads a managed tool API-key record before consulting legacy properties/environment. */
  public static String get(String name) {
    String provider = providerType(name);
    if (provider != null) {
      try {
        String managedValue = com.etendoerp.copilot.config.ProviderCredentials.create()
            .resolveToolApiKey(provider);
        if (managedValue != null && !managedValue.isBlank()) {
          return managedValue;
        }
      } catch (RuntimeException e) {
        log.debug("Managed tool credential lookup was unavailable for provider {}.", provider);
      }
    }
    if (WARNED.add(name)) {
      log.warn("Tool secret '{}' is read from legacy configuration; migrate it to an AI API Key record.", name);
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

  private static String providerType(String name) {
    String normalized = name.toLowerCase(java.util.Locale.ROOT);
    if (normalized.contains("tavily")) return "tavily";
    if (normalized.contains("resend")) return "resend";
    return null;
}
  }
