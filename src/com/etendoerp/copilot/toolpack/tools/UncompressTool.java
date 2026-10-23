package com.etendoerp.copilot.toolpack.tools;

import java.io.ByteArrayOutputStream;
import java.io.FilterInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import javax.enterprise.context.ApplicationScoped;
import javax.inject.Named;
import org.apache.commons.compress.archivers.zip.ZipFile;
import org.apache.commons.compress.archivers.zip.ZipArchiveEntry;
import org.apache.commons.compress.compressors.bzip2.BZip2CompressorInputStream;
import org.apache.commons.compress.compressors.gzip.GzipCompressorInputStream;
import org.codehaus.jettison.json.JSONArray;
import org.codehaus.jettison.json.JSONObject;
import com.etendoerp.copilot.engine.tool.ServerTool;
import com.etendoerp.copilot.engine.tool.ToolExecutionContext;
import dev.langchain4j.agent.tool.ToolSpecification;

@ApplicationScoped
@Named("UncompressTool")
public class UncompressTool implements ServerTool {
  public String name() {
    return "UncompressTool";
  }

  public ToolSpecification specification() {
    return FileToolSupport.spec(name(),
        "This tool uncompresses a file and returns the path list of the uncompressed files. It receives a path to a compressed file and uncompresses it.",
        "{\"compressed_file_path\":{\"type\":\"string\",\"description\":\"Path to a compressed file\"}}",
        "compressed_file_path");
  }

  public String execute(JSONObject args, ToolExecutionContext context) throws Exception {
    Path archive = FileToolSupport.readPath(context, FileToolSupport.requiredString(args, "compressed_file_path"));
    String lower = archive.getFileName().toString().toLowerCase();
    String extension = lower.endsWith(".zip") ? ".zip"
        : lower.endsWith(".gz") ? ".gz"
        : lower.endsWith(".bz2") ? ".bz2"
        : lower.endsWith(".rar") ? ".rar" : "";
    if (extension.isEmpty()) {
      return new JSONObject().put("error",
          "Unsupported file type null, supported types are [.zip, .gz, .bz2, .rar]").toString();
    }

    Path output = ToolWorkspace.resolveWrite(context,
        archive.resolveSibling(archive.getFileName().toString().substring(0,
            archive.getFileName().toString().length() - extension.length())).toString());
    Files.createDirectories(output);
    output = ToolWorkspace.resolveWrite(context, output.toString());
    Path canonicalOutput = output.toRealPath();
    Limits limits = new Limits(archive, context);
    switch (extension) {
      case ".gz":
      case ".bz2":
        extractSingle(archive, output, extension, limits);
        break;
      case ".rar":
        extractRar(archive, output, canonicalOutput, limits);
        break;
      default:
        extractZip(archive, output, canonicalOutput, limits);
    }

    List<String> found = new ArrayList<>();
    try (var paths = Files.walk(output)) {
      paths.filter(Files::isRegularFile)
          .filter(path -> !path.toString().contains("/__MACOSX/"))
          .forEach(path -> found.add(path.toString()));
    }
    JSONArray files = new JSONArray();
    found.forEach(files::put);
    return new JSONObject().put("uncompressed_files_paths", files).toString();
  }

  private static void extractSingle(Path archive, Path output, String extension, Limits limits)
      throws IOException {
    String basename = archive.getFileName().toString();
    String filename = basename.substring(0, basename.length() - extension.length());
    Path destination = resolveEntry(output, output, filename, limits.context);
    try (InputStream raw = Files.newInputStream(archive);
        InputStream decoded = extension.equals(".gz") ? new GzipCompressorInputStream(raw)
            : new BZip2CompressorInputStream(raw)) {
      limits.entry();
      FileToolSupport.writeStream(limits.context, destination.toString(), limits.guard(decoded),
          ToolWorkspace.maxFileBytes());
    }
  }

  private static void extractZip(Path archive, Path output, Path canonicalOutput, Limits limits)
      throws IOException {
    try (ZipFile zip = new ZipFile(archive.toFile())) {
      var entries = zip.getEntries();
      while (entries.hasMoreElements()) {
        ZipArchiveEntry entry = entries.nextElement();
        limits.entry();
        if (entry.isUnixSymlink()) throw new IllegalArgumentException("ZIP symbolic links are not allowed");
        Path target = resolveEntry(output, canonicalOutput, entry.getName(), limits.context);
        if (entry.isDirectory()) {
          Files.createDirectories(target);
          ToolWorkspace.resolveWrite(limits.context, target.toString());
        } else {
          try (InputStream contents = zip.getInputStream(entry)) {
            FileToolSupport.writeStream(limits.context, target.toString(), limits.guard(contents),
                ToolWorkspace.maxFileBytes());
          }
        }
      }
    }
  }

  private static void extractRar(Path archive, Path output, Path canonicalOutput, Limits limits)
      throws Exception {
    try (com.github.junrar.Archive rar = new com.github.junrar.Archive(archive.toFile())) {
      for (com.github.junrar.rarfile.FileHeader header : rar.getFileHeaders()) {
        limits.entry();
        Path target = resolveEntry(output, canonicalOutput, header.getFileNameString(), limits.context);
        if (header.isDirectory()) {
          Files.createDirectories(target);
          ToolWorkspace.resolveWrite(limits.context, target.toString());
        } else {
          LimitedByteArrayOutputStream extracted = new LimitedByteArrayOutputStream(limits);
          rar.extractFile(header, extracted);
          FileToolSupport.writeStream(limits.context, target.toString(), extracted.openInputStream(),
              ToolWorkspace.maxFileBytes());
        }
      }
    }
  }
  private static Path resolveEntry(Path output, Path canonicalOutput, String name,
      ToolExecutionContext context) throws IOException {
    Path relative = Path.of(name);
    if (relative.isAbsolute()) throw new IllegalArgumentException("Archive entry escapes destination directory");
    Path target = output.resolve(relative).normalize();
    if (!target.startsWith(output.normalize())) {
      throw new IllegalArgumentException("Archive entry escapes destination directory");
    }
    Path parent = target.getParent();
    if (parent == null || !parent.toAbsolutePath().normalize().startsWith(canonicalOutput)) {
      throw new IllegalArgumentException("Archive entry escapes destination directory");
    }
    Files.createDirectories(parent);
    if (!parent.toRealPath().startsWith(canonicalOutput)) {
      throw new IllegalArgumentException("Archive entry escapes destination directory");
    }
    Path resolved = FileToolSupport.writePath(context, target.toString());
    if (Files.isSymbolicLink(target)) {
      throw new IllegalArgumentException("Symbolic links are not allowed in archive destinations");
    }
    if (!resolved.toAbsolutePath().normalize().startsWith(canonicalOutput)) {
      throw new IllegalArgumentException("Archive entry escapes destination directory");
    }
    return resolved;
  }

  private static final class LimitedByteArrayOutputStream extends ByteArrayOutputStream {
    private final Limits limits;

    private LimitedByteArrayOutputStream(Limits limits) {
      this.limits = limits;
    }

    @Override
    public synchronized void write(int value) {
      limits.count(1);
      if (count >= ToolWorkspace.maxFileBytes()) {
        throw new IllegalArgumentException("File exceeds the configured per-file size limit");
      }
      super.write(value);
    }

    @Override
    public synchronized void write(byte[] bytes, int offset, int length) {
      limits.count(length);
      if ((long) count + length > ToolWorkspace.maxFileBytes()) {
        throw new IllegalArgumentException("File exceeds the configured per-file size limit");
      }
      super.write(bytes, offset, length);
    }
    private synchronized InputStream openInputStream() {
      return new java.io.ByteArrayInputStream(buf, 0, count);
    }
  }

  private static final class Limits {
    private final ToolExecutionContext context;
    private final long compressedBytes;
    private long expandedBytes;
    private int entries;

    private Limits(Path archive, ToolExecutionContext context) throws IOException {
      this.context = context;
      compressedBytes = Math.max(1, Files.size(archive));
    }

    private void entry() {
      if (++entries > ToolWorkspace.maxArchiveEntries()) {
        throw new IllegalArgumentException("Archive exceeds the configured entry limit");
      }
    }

    private void count(long bytes) {
      expandedBytes = Math.addExact(expandedBytes, bytes);
      if (expandedBytes > ToolWorkspace.maxArchiveBytes()) {
        throw new IllegalArgumentException("Archive exceeds the configured expanded size limit");
      }
      if ((double) expandedBytes / compressedBytes > ToolWorkspace.maxCompressionRatio()) {
        throw new IllegalArgumentException("Archive exceeds the configured compression ratio limit");
      }
    }

    private InputStream guard(InputStream input) {
      return new FilterInputStream(input) {
        @Override
        public int read() throws IOException {
          int value = super.read();
          if (value >= 0) Limits.this.count(1);
          return value;
        }

        @Override
        public int read(byte[] buffer, int offset, int length) throws IOException {
          int bytes = super.read(buffer, offset, length);
          if (bytes > 0) Limits.this.count(bytes);
          return bytes;
        }
      };
    }
  }
}
