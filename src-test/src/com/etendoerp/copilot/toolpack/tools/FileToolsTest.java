package com.etendoerp.copilot.toolpack.tools;

import static org.junit.jupiter.api.Assertions.*;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import org.apache.commons.compress.archivers.zip.ZipArchiveEntry;
import org.apache.commons.compress.archivers.zip.ZipArchiveOutputStream;
import org.codehaus.jettison.json.JSONObject;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;

class FileToolsTest {
  private static final String WORKSPACE = "COPILOT_WORKSPACE";
  private static final String ROOTS = "copilot.tools.fs.roots";
  private static final String READ_ROOTS = "copilot.tools.fs.read.roots";
  private static final String WRITE_ROOTS = "copilot.tools.fs.write.roots";
  private static final String MAX_FILE_BYTES = "copilot.tools.fs.max.file.bytes";
  private static final String MAX_CONVERSATION_BYTES = "copilot.tools.fs.max.conversation.bytes";
  private static final String MAX_CONVERSATION_FILES = "copilot.tools.fs.max.conversation.files";
  private static final String MAX_ARCHIVE_ENTRIES = "copilot.tools.fs.archive.max.entries";
  private static final String MAX_ARCHIVE_BYTES = "copilot.tools.fs.archive.max.bytes";
  private static final String MAX_ARCHIVE_RATIO = "copilot.tools.fs.archive.max.ratio";
  private final String oldWorkspace = System.getProperty(WORKSPACE);
  private final String oldRoots = System.getProperty(ROOTS);
  private final String oldReadRoots = System.getProperty(READ_ROOTS);
  private final String oldWriteRoots = System.getProperty(WRITE_ROOTS);
  private final String oldMaxFileBytes = System.getProperty(MAX_FILE_BYTES);
  private final String oldMaxConversationBytes = System.getProperty(MAX_CONVERSATION_BYTES);
  private final String oldMaxConversationFiles = System.getProperty(MAX_CONVERSATION_FILES);
  private final String oldMaxArchiveEntries = System.getProperty(MAX_ARCHIVE_ENTRIES);
  private final String oldMaxArchiveBytes = System.getProperty(MAX_ARCHIVE_BYTES);
  private final String oldMaxArchiveRatio = System.getProperty(MAX_ARCHIVE_RATIO);
  private final String oldUserDir = System.getProperty("user.dir");

  @AfterEach void restoreWorkspace() {
    restoreProperty(WORKSPACE, oldWorkspace);
    restoreProperty(ROOTS, oldRoots);
    restoreProperty(READ_ROOTS, oldReadRoots);
    restoreProperty(WRITE_ROOTS, oldWriteRoots);
    restoreProperty(MAX_FILE_BYTES, oldMaxFileBytes);
    restoreProperty(MAX_CONVERSATION_BYTES, oldMaxConversationBytes);
    restoreProperty(MAX_CONVERSATION_FILES, oldMaxConversationFiles);
    restoreProperty(MAX_ARCHIVE_ENTRIES, oldMaxArchiveEntries);
    restoreProperty(MAX_ARCHIVE_BYTES, oldMaxArchiveBytes);
    restoreProperty(MAX_ARCHIVE_RATIO, oldMaxArchiveRatio);
    restoreProperty("user.dir", oldUserDir);
  }

  private static void restoreProperty(String key, String value) {
    if (value == null) System.clearProperty(key); else System.setProperty(key, value);
  }

  private Path workspace() throws Exception {
    Path root = Files.createTempDirectory("file-tools-test");
    System.setProperty(WORKSPACE, root.toString());
    Path conversation = root.resolve("default");
    Files.createDirectories(conversation);
    return conversation.toRealPath();
  }

  @Test void conversationQuotaCountsBytesAndFiles() throws Exception {
    Path dir = workspace();
    System.setProperty(MAX_CONVERSATION_BYTES, "5");
    System.setProperty(MAX_CONVERSATION_FILES, "1");
    FileToolSupport.writeString(null, dir.resolve("one.txt").toString(), "123");
    assertThrows(IllegalArgumentException.class,
        () -> FileToolSupport.writeString(null, dir.resolve("two.txt").toString(), "4"));
    assertThrows(IllegalArgumentException.class,
        () -> FileToolSupport.writeString(null, dir.resolve("one.txt").toString(), "123456"));
  }
  @Test void workspaceScopesConversationAndRejectsTraversal() throws Exception {
    Path root = workspace();
    assertTrue(ToolWorkspace.workDir(null).startsWith(root.toRealPath()));
    assertThrows(IllegalArgumentException.class, () -> ToolWorkspace.resolve(null, "../../secret.txt"));
  }

  @Test void configuredRootsAllowSourcePathsAndRejectTraversalAndSymlinks() throws Exception {
    Path workspace = workspace();
    Path sourceRoot = Files.createTempDirectory("tool-source-root");
    Path outside = Files.createTempDirectory("tool-outside-root");
    System.setProperty(ROOTS, sourceRoot.toString());
    Path sourceFile = Files.writeString(sourceRoot.resolve("Source.java"), "class Source {}");
    assertEquals(sourceFile.toRealPath(), ToolWorkspace.resolve(null, sourceFile.toString()));
    assertThrows(IllegalArgumentException.class,
        () -> ToolWorkspace.resolve(null, sourceRoot.resolve("../outside.txt").toString()));
    Path escape = workspace.resolve("escape");
    try {
      Files.createSymbolicLink(escape, outside);
      assertThrows(IllegalArgumentException.class,
          () -> ToolWorkspace.resolve(null, escape.resolve("secret.txt").toString()));
    } catch (UnsupportedOperationException | java.nio.file.FileSystemException ignored) {
      // Symlinks may not be available to the current test user or filesystem.
    }
  }

  @Test void readWriteCopyAndDirectoryToolsUseScopedPaths() throws Exception {
    Path dir = workspace();
    var write = new WriteFileTool();
    write.execute(new JSONObject().put("filepath", "folder/input.txt").put("content", "alpha\nbeta"), null);
    assertEquals("alpha\nbeta", Files.readString(dir.resolve("folder/input.txt")));
    assertTrue(new ReadFileTool().execute(new JSONObject().put("filepath", "folder/input.txt"), null).contains("alpha\\nbeta"));
    new FileCopyTool().execute(new JSONObject().put("source_path", "folder/input.txt").put("destination_directory", "copied"), null);
    assertEquals("alpha\nbeta", Files.readString(dir.resolve("copied/input.txt")));
    String listing = new PrintDirectoryTool().execute(new JSONObject().put("path", ".").put("recursive", true), null);
    assertTrue(listing.contains("input.txt"));
    assertTrue(listing.contains("copied"));
  }

  @Test void separateReadWriteRootsDenyProtectedPathsAndEnforceWriteLimits() throws Exception {
    Path conversation = workspace();
    Path readRoot = Files.createTempDirectory("file-read-root");
    Path writeRoot = Files.createTempDirectory("file-write-root");
    Path source = Files.writeString(readRoot.resolve("source.txt"), "read");
    System.setProperty("copilot.tools.fs.read.roots", readRoot.toString());
    System.setProperty("copilot.tools.fs.write.roots", writeRoot.toString());
    assertEquals(source.toRealPath(), ToolWorkspace.resolveRead(null, source.toString()));
    assertThrows(IllegalArgumentException.class,
        () -> ToolWorkspace.resolveWrite(null, readRoot.resolve("not-writable.txt").toString()));
    System.setProperty("user.dir", readRoot.toString());
    assertThrows(IllegalArgumentException.class,
        () -> ToolWorkspace.resolveRead(null, readRoot.resolve("config/secret.txt").toString()));
    System.setProperty("copilot.tools.fs.write.roots", readRoot.toString());
    assertThrows(IllegalArgumentException.class,
        () -> ToolWorkspace.resolveWrite(null, readRoot.resolve("config/secret.txt").toString()));
    System.setProperty("copilot.tools.fs.read.roots", "/");
    System.setProperty("copilot.tools.fs.write.roots", "/");
    assertThrows(IllegalArgumentException.class, () -> ToolWorkspace.resolveRead(null, "/tmp/Openbravo.properties"));
    assertThrows(IllegalArgumentException.class, () -> ToolWorkspace.resolveWrite(null, "/tmp/Openbravo.properties"));
    System.setProperty("copilot.tools.fs.max.file.bytes", "4");
    assertThrows(IllegalArgumentException.class, () -> new WriteFileTool().execute(
        new JSONObject().put("filepath", writeRoot.resolve("large.txt").toString()).put("content", "12345"), null));
    new WriteFileTool().execute(new JSONObject().put("filepath", writeRoot.resolve("safe.txt").toString())
        .put("content", "safe"), null);
    assertFalse(Files.isExecutable(writeRoot.resolve("safe.txt")));
    assertEquals(conversation.toRealPath(), ToolWorkspace.workDir(null));
  }

  @Test void readAndWriteRejectHardLinksAndDestinationSymlinkEscapes() throws Exception {
    Path workspace = workspace();
    Path external = Files.createTempDirectory("file-hardlink-test");
    Path secret = Files.writeString(external.resolve("secret.txt"), "secret");
    try {
      Path hardLink = workspace.resolve("hardlink.txt");
      Files.createLink(hardLink, secret);
      assertThrows(IllegalArgumentException.class, () -> ToolWorkspace.resolveRead(null, hardLink.toString()));
    } catch (UnsupportedOperationException | java.nio.file.FileSystemException ignored) {
      // Hard links may not be available on the test filesystem.
    }
    try {
      Path link = workspace.resolve("destination");
      Files.createSymbolicLink(link, external);
      assertThrows(IllegalArgumentException.class, () -> FileToolSupport.writeBytes(null,
          link.resolve("escape.txt").toString(), new byte[] {1}));
    } catch (UnsupportedOperationException | java.nio.file.FileSystemException ignored) {
      // Symlinks may not be available on the test filesystem.
    }
  }
  @Test void toolNamesAndSpecificationsMatchEtcoptValues() {
    assertTool(new ReadFileTool(), "ReadFileTool"); assertTool(new WriteFileTool(), "WriteFileTool");
    assertTool(new PrintDirectoryTool(), "PrintDirectoryTool"); assertTool(new FileCopyTool(), "FileCopyTool");
    assertTool(new FileDownloaderTool(), "FileDownloaderTool"); assertTool(new UncompressTool(), "UncompressTool");
    assertTool(new PdfToImagesTool(), "PdfToImagesTool"); assertTool(new XLSTool(), "XLSTool");
    assertTool(new CodbarTool(), "CodbarTool");
  }

  private static void assertTool(com.etendoerp.copilot.engine.tool.ServerTool tool, String name) {
    assertEquals(name, tool.name()); assertEquals(name, tool.specification().name());
    assertNotNull(tool.specification().parameters());
  }
  @Test void spreadsheetReadsCsvRowsAndHeaders() throws Exception {
    Path dir = workspace();
    Files.writeString(dir.resolve("rows.csv"), "name,count\nalpha,2\nbeta,3\n");
    var tool = new XLSTool();
    assertEquals("[[\"name\",\"count\"],[\"alpha\",\"2\"],[\"beta\",\"3\"]]",
        tool.execute(new JSONObject().put("path", "rows.csv"), null));
    assertEquals("[\"name\",\"count\"]",
        tool.execute(new JSONObject().put("path", "rows.csv").put("only_headers", true), null));
  }

  @Test void archiveExtractsZipAndDownloaderRejectsNonUrl() throws Exception {
    Path dir = workspace();
    Path zip = dir.resolve("bundle.zip");
    try (var output = new java.util.zip.ZipOutputStream(Files.newOutputStream(zip))) {
      output.putNextEntry(new java.util.zip.ZipEntry("nested/value.txt"));
      output.write("ok".getBytes(java.nio.charset.StandardCharsets.UTF_8));
      output.closeEntry();
    }
    String extracted = new UncompressTool().execute(new JSONObject().put("compressed_file_path", "bundle.zip"), null);
    assertTrue(new JSONObject(extracted).getJSONArray("uncompressed_files_paths").getString(0).endsWith("nested/value.txt"));
    assertFalse(Files.isExecutable(dir.resolve("bundle/nested/value.txt")));
    assertEquals("{\"error\":\"The provided input is not a valid URL.\"}",
        new FileDownloaderTool().execute(new JSONObject().put("file_path_or_url", "local.txt"), null));
  }
  @Test void archiveExtractionRejectsTraversalAndConfiguredLimits() throws Exception {
    Path dir = workspace();
    Path zip = dir.resolve("guarded.zip");
    try (ZipArchiveOutputStream output = new ZipArchiveOutputStream(Files.newOutputStream(zip))) {
      ZipArchiveEntry link = new ZipArchiveEntry("link");
      link.setUnixMode(0120777);
      output.putArchiveEntry(link);
      output.write("outside".getBytes(java.nio.charset.StandardCharsets.UTF_8));
      output.closeArchiveEntry();
    }
    assertThrows(IllegalArgumentException.class, () ->
        new UncompressTool().execute(new JSONObject().put("compressed_file_path", "guarded.zip"), null));

    try (var output = new java.util.zip.ZipOutputStream(Files.newOutputStream(zip))) {
      output.putNextEntry(new java.util.zip.ZipEntry("../escaped.txt"));
      output.write("escape".getBytes(java.nio.charset.StandardCharsets.UTF_8));
      output.closeEntry();
    }
    assertThrows(IllegalArgumentException.class, () ->
        new UncompressTool().execute(new JSONObject().put("compressed_file_path", "guarded.zip"), null));
    assertFalse(Files.exists(dir.resolve("escaped.txt")));

    Files.delete(zip);
    try (var output = new java.util.zip.ZipOutputStream(Files.newOutputStream(zip))) {
      for (String name : List.of("one.txt", "two.txt")) {
        output.putNextEntry(new java.util.zip.ZipEntry(name));
        output.write("expanded".getBytes(java.nio.charset.StandardCharsets.UTF_8));
        output.closeEntry();
      }
    }
    System.setProperty(MAX_ARCHIVE_ENTRIES, "1");
    assertThrows(IllegalArgumentException.class, () ->
        new UncompressTool().execute(new JSONObject().put("compressed_file_path", "guarded.zip"), null));
    System.clearProperty(MAX_ARCHIVE_ENTRIES);
    System.setProperty(MAX_ARCHIVE_BYTES, "1");
    assertThrows(IllegalArgumentException.class, () ->
        new UncompressTool().execute(new JSONObject().put("compressed_file_path", "guarded.zip"), null));
    System.clearProperty(MAX_ARCHIVE_BYTES);
    System.setProperty(MAX_ARCHIVE_RATIO, "0.001");
    assertThrows(IllegalArgumentException.class, () ->
        new UncompressTool().execute(new JSONObject().put("compressed_file_path", "guarded.zip"), null));
  }


  @Test void barcodeAndPdfToolsRejectMissingFiles() throws Exception {
    workspace();
    assertThrows(Exception.class, () -> new PdfToImagesTool().execute(new JSONObject().put("path", "missing.pdf"), null));
    assertEquals("{\"message\":[]}", new CodbarTool().execute(new JSONObject().put("filepath", new org.codehaus.jettison.json.JSONArray().put("missing.png")), null));
  }

}
