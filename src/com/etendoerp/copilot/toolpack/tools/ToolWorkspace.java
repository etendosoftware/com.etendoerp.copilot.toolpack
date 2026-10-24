package com.etendoerp.copilot.toolpack.tools;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.attribute.FileTime;
import java.nio.file.attribute.PosixFilePermission;
import java.nio.file.attribute.PosixFilePermissions;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;

import org.openbravo.base.session.OBPropertiesProvider;

import com.etendoerp.copilot.engine.tool.ToolExecutionContext;

/** Central filesystem policy for Copilot tools. */
public final class ToolWorkspace {
  public enum Access { READ, WRITE }

  private static final String LEGACY_ROOTS = "copilot.tools.fs.roots";
  private static final String READ_ROOTS = "copilot.tools.fs.read.roots";
  private static final String WRITE_ROOTS = "copilot.tools.fs.write.roots";
  private static final String WORKSPACE_PROPERTY = "copilot.tools.workspace.dir";
  private static final String LEGACY_WORKSPACE_PROPERTY = "COPILOT_WORKSPACE";
  private static final String WORKDIR_PROPERTY = "COPILOT_WORKING_DIR";
  private static final long DEFAULT_MAX_CONVERSATION_BYTES = 100L * 1024 * 1024;
  private static final int DEFAULT_MAX_CONVERSATION_FILES = 1000;
  private static final long DEFAULT_MAX_FILE_BYTES = 25L * 1024 * 1024;
  private static final Map<String, Usage> USAGE = new ConcurrentHashMap<>();

  private ToolWorkspace() {}

  public static Path workDir(ToolExecutionContext ctx) {
    String configured = property(WORKSPACE_PROPERTY);
    if (configured == null || configured.isBlank()) configured = property(LEGACY_WORKSPACE_PROPERTY);
    if (configured == null || configured.isBlank()) configured = property(WORKDIR_PROPERTY);
    Path root;
    if (configured == null || configured.isBlank()) {
      String client = safeSegment(identityPart(ctx == null ? null : ctx.clientId(), "mcp"));
      String user = safeSegment(identityPart(ctx == null ? null : ctx.userId(), "mcp"));
      root = Paths.get(System.getProperty("java.io.tmpdir"), "etendo-copilot-workspaces", client, user);
      if (isHardDenied(root)) root = Paths.get("/tmp", "etendo-copilot-workspaces", client, user);
      if (isHardDenied(root)) root = Paths.get(System.getProperty("user.home"),
          "etendo-copilot-workspaces", client, user);
    } else {
      root = Paths.get(configured);
    }
    if (!root.isAbsolute()) throw new IllegalArgumentException("Conversation workspace must be an absolute path");
    Path canonicalRoot = root.toAbsolutePath().normalize();
    if (isHardDenied(canonicalRoot)) throw new IllegalArgumentException("Conversation workspace is in a protected filesystem area");
    try {
      Path existingRoot = existingAncestor(canonicalRoot).toRealPath();
      if (isHardDenied(existingRoot)) throw new IllegalArgumentException("Conversation workspace is in a protected filesystem area");
      Path dir = canonicalRoot.resolve(safeSegment(conversation(ctx))).normalize();
      if (!dir.startsWith(canonicalRoot)) throw new IllegalArgumentException("Invalid conversation workspace");
      Files.createDirectories(canonicalRoot);
      setOwnerOnly(canonicalRoot);
      Files.createDirectories(dir);
      setOwnerOnly(dir);
      Path real = dir.toRealPath();
      if (!real.startsWith(canonicalRoot.toRealPath()) || isHardDenied(real)) {
        throw new IllegalArgumentException("Conversation workspace is outside the allowed filesystem area");
      }
      Files.setLastModifiedTime(real, FileTime.from(Instant.now()));
      Path cleanupRoot = managedRoot(ctx, configured);
      int cleanupDepth = managedDepth(configured);
      WorkspaceJanitor.maybeClean(cleanupRoot, cleanupDepth, workspaceTtl(),
          candidate -> WorkspaceJanitor.isActive(candidate, cleanupRoot, cleanupDepth));
      return real;
    } catch (IOException e) {
      throw new IllegalStateException("Unable to create or validate tool workspace", e);
    }
  }

  static void cleanExpiredWorkspaces() {
    String configured = property(WORKSPACE_PROPERTY);
    if (configured == null || configured.isBlank()) configured = property(LEGACY_WORKSPACE_PROPERTY);
    if (configured == null || configured.isBlank()) configured = property(WORKDIR_PROPERTY);
    Path root = managedRoot(null, configured);
    int depth = managedDepth(configured);
    if (root != null && !isHardDenied(root)) {
      WorkspaceJanitor.maybeClean(root, depth, workspaceTtl(),
          candidate -> WorkspaceJanitor.isActive(candidate, root, depth));
    }
  }

  private static int managedDepth(String configured) {
    return configured == null || configured.isBlank() ? 3 : 1;
  }

  private static Path managedRoot(ToolExecutionContext ctx, String configured) {
    if (configured != null && !configured.isBlank()) return Paths.get(configured).toAbsolutePath().normalize();
    String client = safeSegment(identityPart(ctx == null ? null : ctx.clientId(), "mcp"));
    Path candidate = Paths.get(System.getProperty("java.io.tmpdir"), "etendo-copilot-workspaces");
    if (isHardDenied(candidate)) candidate = Paths.get("/tmp", "etendo-copilot-workspaces");
    if (isHardDenied(candidate)) candidate = Paths.get(System.getProperty("user.home"), "etendo-copilot-workspaces");
    return candidate.resolve(client).toAbsolutePath().normalize().getParent();
  }

  private static Duration workspaceTtl() {
    long configuredHours = positiveLong(WorkspaceJanitor.TTL_HOURS_PROPERTY, WorkspaceJanitor.DEFAULT_TTL_HOURS);
    return Duration.ofHours(Math.min(configuredHours, Duration.ofDays(3650).toHours()));
  }

  private static void setOwnerOnly(Path directory) throws IOException {
    try {
      Files.setPosixFilePermissions(directory, PosixFilePermissions.fromString("rwx------"));
    } catch (UnsupportedOperationException ignored) {
      // The platform has no POSIX permission model.
    }
  }
  private static String identityPart(String value, String fallback) {
    return value == null || value.isBlank() ? fallback : value;
  }

  /** Existing path resolution is read-only by default. */
  public static Path resolve(ToolExecutionContext ctx, String path) {
    return resolveRead(ctx, path);
  }

  public static Path resolveRead(ToolExecutionContext ctx, String path) {
    return resolve(ctx, path, Access.READ);
  }

  public static Path resolveWrite(ToolExecutionContext ctx, String path) {
    return resolve(ctx, path, Access.WRITE);
  }

  public static Path resolve(ToolExecutionContext ctx, String path, Access access) {
    if (path == null || path.isBlank()) throw new IllegalArgumentException("Path is required");
    Path workspace = workDir(ctx);
    Path supplied = Paths.get(path);
    Path resolved = (supplied.isAbsolute() ? supplied : workspace.resolve(supplied)).toAbsolutePath().normalize();
    List<Path> roots = allowedRoots(workspace, access);
    for (Path root : roots) {
      Path realRoot;
      try {
        realRoot = root.toRealPath();
      } catch (IOException e) {
        throw new IllegalArgumentException("Configured filesystem root is unavailable: " + root, e);
      }
      Path existing = existingAncestor(resolved);
      try {
        Path realExisting = existing.toRealPath();
        if (!realExisting.startsWith(realRoot) || isHardDenied(resolved) || isHardDenied(realExisting)) continue;
        if (Files.exists(resolved, LinkOption.NOFOLLOW_LINKS)) {
          Path realPath = resolved.toRealPath();
          if (!realPath.startsWith(realRoot) || isHardDenied(realPath)) continue;
          rejectHardLink(realPath);
          return realPath;
        }
        Path candidate = realExisting.resolve(existing.relativize(resolved)).normalize();
        if (!candidate.startsWith(realRoot) || isHardDenied(candidate)) continue;
        return candidate;
      } catch (IOException e) {
        throw new IllegalArgumentException("Unable to resolve tool path: " + path, e);
      }
    }
    throw new IllegalArgumentException("Path is outside the configured or safe filesystem roots: " + path);
  }

  /** Resolve a destination's parent to its real path before opening or creating the file. */
  public static Path resolveWriteParent(ToolExecutionContext ctx, String path) throws IOException {
    Path target = resolveWrite(ctx, path);
    Path parent = target.getParent();
    if (parent == null) throw new IllegalArgumentException("A file destination must have a parent directory");
    Files.createDirectories(parent);
    Path realParent = parent.toRealPath();
    Path verified = resolveWrite(ctx, realParent.resolve(target.getFileName()).toString());
    return verified;
  }

  public static Object writeLock(ToolExecutionContext ctx) {
    return USAGE.computeIfAbsent(usageKey(ctx), ignored -> new Usage());
  }
  public static void checkWrite(ToolExecutionContext ctx, Path path, long bytes, int files) throws IOException {
    if (bytes < 0 || bytes > maxFileBytes()) throw new IllegalArgumentException("File exceeds the configured per-file size limit");
    Path target = resolveWrite(ctx, path.toString());
    rejectHardLinkIfPresent(target);
    Usage usage = USAGE.computeIfAbsent(usageKey(ctx), ignored -> new Usage());
    synchronized (usage) {
      ensureUsageLoaded(ctx, usage);
      Long prior = usage.files.get(target.toString());
      boolean existingUntracked = prior == null && Files.isRegularFile(target, LinkOption.NOFOLLOW_LINKS);
      long previousBytes = prior == null ? 0 : prior;
      long untrackedBytes = existingUntracked ? Files.size(target) : 0;
      long newBytes = Math.addExact(usage.bytes - previousBytes + untrackedBytes, bytes);
      int newFiles = usage.files.size() - (prior == null ? 0 : 1)
          + (existingUntracked ? 1 : files);
      if (newBytes > maxConversationBytes() || newFiles > maxConversationFiles()) {
        throw new IllegalArgumentException("Conversation filesystem quota exceeded");
      }
    }
  }

  public static int maxArchiveEntries() { return (int) Math.min(Integer.MAX_VALUE, positiveLong("copilot.tools.fs.archive.max.entries", 1000)); }
  public static long maxArchiveBytes() { return positiveLong("copilot.tools.fs.archive.max.bytes", 100L * 1024 * 1024); }
  public static double maxCompressionRatio() {
    String value = property("copilot.tools.fs.archive.max.ratio");
    if (value == null || value.isBlank()) return 100.0;
    try { double parsed = Double.parseDouble(value); return parsed > 0 ? parsed : 100.0; }
    catch (NumberFormatException ignored) { return 100.0; }
  }

  public static void recordWrite(ToolExecutionContext ctx, Path path) throws IOException {
    Path target = resolveWrite(ctx, path.toString());
    rejectHardLinkIfPresent(target);
    long size = Files.size(target);
    if (size > maxFileBytes()) throw new IllegalArgumentException("File exceeds the configured per-file size limit");
    Usage usage = USAGE.computeIfAbsent(usageKey(ctx), ignored -> new Usage());
    synchronized (usage) {
      Long previous = usage.files.put(target.toString(), size);
      long total = usage.bytes - (previous == null ? 0 : previous) + size;
      if (total > maxConversationBytes() || usage.files.size() > maxConversationFiles()) {
        if (previous == null) usage.files.remove(target.toString()); else usage.files.put(target.toString(), previous);
        throw new IllegalArgumentException("Conversation filesystem quota exceeded");
      }
      usage.bytes = total;
    }
    removeExecutePermission(target);
  }

  public static long maxFileBytes() { return positiveLong("copilot.tools.fs.max.file.bytes", DEFAULT_MAX_FILE_BYTES); }
  public static long maxConversationBytes() { return positiveLong("copilot.tools.fs.max.conversation.bytes", DEFAULT_MAX_CONVERSATION_BYTES); }
  public static int maxConversationFiles() { return (int) Math.min(Integer.MAX_VALUE, positiveLong("copilot.tools.fs.max.conversation.files", DEFAULT_MAX_CONVERSATION_FILES)); }

  public static void removeExecutePermission(Path path) throws IOException {
    try {
      Set<PosixFilePermission> permissions = Files.getPosixFilePermissions(path, LinkOption.NOFOLLOW_LINKS);
      permissions.remove(PosixFilePermission.OWNER_EXECUTE);
      permissions.remove(PosixFilePermission.GROUP_EXECUTE);
      permissions.remove(PosixFilePermission.OTHERS_EXECUTE);
      Files.setPosixFilePermissions(path, permissions);
    } catch (UnsupportedOperationException ignored) {
      if (!path.toFile().setExecutable(false, false)) {
        throw new IOException("Unable to remove executable permission from " + path);
      }
    }
  }

  private static List<Path> allowedRoots(Path workspace, Access access) {
    List<Path> roots = new ArrayList<>();
    roots.add(workspace.toAbsolutePath().normalize());
    String configured = property(access == Access.READ ? READ_ROOTS : WRITE_ROOTS);
    if ((configured == null || configured.isBlank())) configured = property(LEGACY_ROOTS);
    if (configured != null && !configured.isBlank()) {
      for (String entry : configured.split(",")) {
        if (entry.isBlank()) continue;
        Path root = Paths.get(entry.trim());
        if (!root.isAbsolute()) throw new IllegalArgumentException((access == Access.READ ? READ_ROOTS : WRITE_ROOTS) + " entries must be absolute paths");
        Path normalized = root.normalize();
        if (isHardDenied(normalized)) throw new IllegalArgumentException("Configured filesystem roots cannot include a protected application or system path");
        if (!Files.isDirectory(normalized)) throw new IllegalArgumentException("Configured filesystem root must be an existing directory: " + normalized);
        roots.add(normalized);
      }
    }
    return roots;
  }

  private static boolean isHardDenied(Path path) {
    Path normalized = path.toAbsolutePath().normalize();
    for (Path part : normalized) {
      String name = part.toString();
      if (name.equalsIgnoreCase(".git") || name.equalsIgnoreCase("Openbravo.properties")
          || name.equalsIgnoreCase("gradle.properties")) return true;
    }
    Path home = Paths.get(System.getProperty("user.home", "~")).toAbsolutePath().normalize();
    if (normalized.startsWith(home)) {
      Path relative = home.relativize(normalized);
      for (Path part : relative) if (part.toString().startsWith(".")) return true;
    }
    String catalina = System.getProperty("catalina.base");
    if (catalina != null) {
      Path base = Paths.get(catalina).toAbsolutePath().normalize();
      if (normalized.startsWith(base.resolve("webapps")) || normalized.startsWith(base.resolve("conf"))) return true;
    }
    String userDir = System.getProperty("user.dir");
    if (userDir != null) {
      Path app = Paths.get(userDir).toAbsolutePath().normalize();
      Path config = app.resolve("config");
      if (normalized.startsWith(config) || normalized.startsWith(app.resolve("WebContent"))
          || normalized.startsWith(app.resolve("build/local-env/catalina/webapps"))) return true;
    }
    Path deployment = deploymentRoot();
    return deployment != null && normalized.startsWith(deployment);
  }

  private static Path deploymentRoot() {
    try {
      Path location = Paths.get(ToolWorkspace.class.getProtectionDomain().getCodeSource().getLocation().toURI()).toAbsolutePath().normalize();
      for (Path part : location) {
        if (part.toString().equalsIgnoreCase("WEB-INF")) {
          Path result = location;
          while (result != null && !result.getFileName().toString().equalsIgnoreCase("WEB-INF")) result = result.getParent();
          return result == null ? null : result.getParent();
        }
      }
    } catch (Exception ignored) {
      return null;
    }
    return null;
  }

  private static Path existingAncestor(Path path) {
    Path existing = path;
    while (existing != null && !Files.exists(existing, LinkOption.NOFOLLOW_LINKS)) existing = existing.getParent();
    return existing == null ? path.getRoot() : existing;
  }

  private static void rejectHardLink(Path path) throws IOException {
    if (Files.isRegularFile(path, LinkOption.NOFOLLOW_LINKS)) rejectHardLinkIfPresent(path);
  }

  private static void rejectHardLinkIfPresent(Path path) throws IOException {
    if (!Files.exists(path, LinkOption.NOFOLLOW_LINKS)) return;
    try {
      Object count = Files.getAttribute(path, "unix:nlink", LinkOption.NOFOLLOW_LINKS);
      if (count instanceof Number n && n.longValue() > 1) {
        throw new IllegalArgumentException("Hard-linked files cannot be accessed by Copilot tools");
      }
    } catch (UnsupportedOperationException ignored) {
      // Platforms without link-count support still receive symlink and canonical-path checks.
    }
  }

  private static String usageKey(ToolExecutionContext ctx) {
    return workDir(ctx).toString() + "\u0000" + conversation(ctx);
  }

  static void forgetUsage(Path workspace) {
    String prefix = workspace.toString() + "\u0000";
    USAGE.keySet().removeIf(key -> key.startsWith(prefix));
  }

  private static void ensureUsageLoaded(ToolExecutionContext ctx, Usage usage) throws IOException {
    if (usage.initialized) return;
    try (var paths = Files.walk(workDir(ctx))) {
      for (Path path : (Iterable<Path>) paths::iterator) {
        if (Files.isRegularFile(path, LinkOption.NOFOLLOW_LINKS) && !isHardDenied(path)) {
          rejectHardLinkIfPresent(path);
          long size = Files.size(path);
          usage.files.put(path.toRealPath().toString(), size);
          usage.bytes = Math.addExact(usage.bytes, size);
        }
      }
    }
    usage.initialized = true;
  }
  private static long positiveLong(String key, long fallback) {
    String value = property(key);
    if (value == null || value.isBlank()) return fallback;
    try {
      long parsed = Long.parseLong(value.trim());
      return parsed > 0 ? parsed : fallback;
    } catch (NumberFormatException ignored) {
      return fallback;
    }
  }

  private static String property(String key) {
    String value = System.getProperty(key);
    if (value != null && !value.isBlank()) return value;
    try {
      return OBPropertiesProvider.getInstance().getOpenbravoProperties().getProperty(key);
    } catch (RuntimeException ignored) {
      return null;
    }
  }

  private static String conversation(ToolExecutionContext ctx) {
    String conversation = ctx == null ? null : ctx.conversationId();
    return conversation == null || conversation.isBlank() ? "mcp" : safeSegment(conversation);
  }

  private static String safeSegment(String value) {
    String sanitized = value.replaceAll("[^A-Za-z0-9._-]", "_");
    if (sanitized.isBlank() || sanitized.equals(".") || sanitized.equals("..")) return "default";
    return sanitized;
  }

  public static void recordDelete(ToolExecutionContext ctx, Path path) throws IOException {
    Path target = resolveWrite(ctx, path.toString());
    Usage usage = USAGE.computeIfAbsent(usageKey(ctx), ignored -> new Usage());
    synchronized (usage) {
      ensureUsageLoaded(ctx, usage);
      Long removed = usage.files.remove(target.toString());
      if (removed != null) usage.bytes -= removed;
      Files.deleteIfExists(target);
    }
  }
  private static final class Usage {
    private long bytes;
    private boolean initialized;
    private final Map<String, Long> files = new ConcurrentHashMap<>();
  }
}
