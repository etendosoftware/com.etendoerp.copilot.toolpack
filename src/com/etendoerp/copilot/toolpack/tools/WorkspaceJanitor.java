package com.etendoerp.copilot.toolpack.tools;

import java.io.IOException;
import java.nio.file.FileVisitResult;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.nio.file.SimpleFileVisitor;
import java.nio.file.attribute.BasicFileAttributes;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.concurrent.atomic.AtomicLong;
import java.util.function.Predicate;
import java.util.stream.Stream;

import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import com.etendoerp.copilot.engine.tool.ToolExecutionContext;

/** TTL cleanup for conversation workspaces; never follows links or escapes the managed root. */
final class WorkspaceJanitor {
  static final String TTL_HOURS_PROPERTY = "copilot.tools.workspace.ttl.hours";
  static final long DEFAULT_TTL_HOURS = 24;
  static final long RUN_INTERVAL_MILLIS = Duration.ofMinutes(10).toMillis();
  private static final int MAX_CANDIDATES = 2000;
  private static final Logger LOG = LogManager.getLogger(WorkspaceJanitor.class);
  private static final AtomicLong LAST_RUN = new AtomicLong();

  private WorkspaceJanitor() {}

  static void maybeClean(Path root, int layoutDepth, Duration ttl, Predicate<Path> active) {
    maybeClean(root, layoutDepth, ttl, active, Clock.systemUTC(), System.currentTimeMillis());
  }

  static void maybeClean(Path root, int layoutDepth, Duration ttl, Predicate<Path> active, Clock clock, long nowMillis) {
    long previous = LAST_RUN.get();
    if (nowMillis - previous < RUN_INTERVAL_MILLIS || !LAST_RUN.compareAndSet(previous, nowMillis)) return;
    clean(root, layoutDepth, ttl, clock, active);
  }

  static int clean(Path root, int layoutDepth, Duration ttl, Clock clock) {
    return clean(root, layoutDepth, ttl, clock, ignored -> false);
  }

  static int clean(Path root, int layoutDepth, Duration ttl, Clock clock, Predicate<Path> active) {
    if (root == null || ttl == null || ttl.isNegative() || ttl.isZero() || layoutDepth < 1 || layoutDepth > 3
        || !Files.isDirectory(root, LinkOption.NOFOLLOW_LINKS) || Files.isSymbolicLink(root)) return 0;
    final Path normalizedRoot = root.toAbsolutePath().normalize();
    try {
      Path realRoot = normalizedRoot.toRealPath(LinkOption.NOFOLLOW_LINKS);
      Instant cutoff = clock.instant().minus(ttl);
      int deleted = 0;
      int inspected = 0;
      try (Stream<Path> walk = Files.walk(normalizedRoot, layoutDepth)) {
        for (Path candidate : (Iterable<Path>) walk::iterator) {
          if (candidate.equals(normalizedRoot) || !Files.isDirectory(candidate, LinkOption.NOFOLLOW_LINKS)) continue;
          if (normalizedRoot.relativize(candidate).getNameCount() != layoutDepth) continue;
          if (++inspected > MAX_CANDIDATES) break;
          if (containsLink(normalizedRoot, candidate) || active.test(candidate)) continue;
          Path realCandidate = candidate.toRealPath(LinkOption.NOFOLLOW_LINKS);
          if (!realCandidate.startsWith(realRoot) || Files.getLastModifiedTime(candidate, LinkOption.NOFOLLOW_LINKS)
              .toInstant().isAfter(cutoff)) continue;
          deleteTree(candidate);
          ToolWorkspace.forgetUsage(realCandidate);
          deleted++;
        }
      }
      LOG.info("Workspace janitor examined {} managed directories and removed {} expired workspaces under {}",
          inspected, deleted, normalizedRoot);
      return deleted;
    } catch (IOException | RuntimeException e) {
      LOG.warn("Unable to clean Copilot workspaces under {}: {}", normalizedRoot, e.getMessage());
      return 0;
    }
  }

  static boolean isActive(Path candidate, Path root, int layoutDepth) {
    Path relative = root.toAbsolutePath().normalize().relativize(candidate.toAbsolutePath().normalize());
    if (layoutDepth == 3 && relative.getNameCount() == 3) {
      return ToolExecutionContext.isWorkspaceActive(relative.getName(0).toString(), relative.getName(1).toString(),
          relative.getName(2).toString());
    }
    return relative.getNameCount() == 1
        && ToolExecutionContext.isConversationActive(relative.getName(0).toString());
  }

  private static boolean containsLink(Path root, Path candidate) {
    Path current = root;
    for (Path part : root.relativize(candidate)) {
      current = current.resolve(part);
      if (Files.isSymbolicLink(current)) return true;
    }
    return false;
  }

  private static void deleteTree(Path target) throws IOException {
    Files.walkFileTree(target, new SimpleFileVisitor<>() {
      @Override
      public FileVisitResult visitFile(Path file, BasicFileAttributes attrs) throws IOException {
        Files.deleteIfExists(file);
        return FileVisitResult.CONTINUE;
      }

      @Override
      public FileVisitResult postVisitDirectory(Path directory, IOException error) throws IOException {
        if (error != null) throw error;
        Files.deleteIfExists(directory);
        return FileVisitResult.CONTINUE;
      }
    });
  }

  static void resetThrottleForTest() {
    LAST_RUN.set(0);
  }
}
