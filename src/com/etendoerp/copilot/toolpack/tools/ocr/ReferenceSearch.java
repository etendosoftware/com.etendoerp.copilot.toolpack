package com.etendoerp.copilot.toolpack.tools.ocr;

import java.nio.file.Path;
import java.util.Optional;

/** Lookup of an agent's OCR reference template for an input image. */
public interface ReferenceSearch {
  /**
   * Finds the best reference for an agent and image, returning empty when no match meets
   * the configured threshold. Implementations may ignore the threshold when requested.
   */
  Optional<Reference> find(String agentId, Path image, double threshold, boolean ignoreThreshold) throws Exception;

  /** Stored reference image data required by OCR prompt construction. */
  final class Reference {
    private final String path;
    private final String base64;
    public Reference(String path, String base64) { this.path = path; this.base64 = base64; }
    public String path() { return path; }
    public String base64() { return base64; }
  }
}
