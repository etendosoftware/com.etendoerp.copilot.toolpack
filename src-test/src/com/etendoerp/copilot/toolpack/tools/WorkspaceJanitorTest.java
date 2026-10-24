package com.etendoerp.copilot.toolpack.tools;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.attribute.FileTime;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneOffset;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class WorkspaceJanitorTest {
  @TempDir Path temp;

  @Test
  void removesOnlyExpiredManagedConversationDirectories() throws Exception {
    Path root = Files.createDirectory(temp.resolve("managed"));
    Path expired = Files.createDirectories(root.resolve("client/user/expired"));
    Path active = Files.createDirectories(root.resolve("client/user/active"));
    Path fresh = Files.createDirectories(root.resolve("client/user/fresh"));
    Files.writeString(expired.resolve("old.txt"), "old");
    Files.writeString(active.resolve("live.txt"), "live");
    Path outside = Files.createDirectories(temp.resolve("outside"));
    Files.writeString(outside.resolve("keep.txt"), "keep");
    Files.writeString(fresh.resolve("fresh.txt"), "fresh");
    Files.createSymbolicLink(expired.resolve("escape"), outside);
    Path externalLink = Files.createSymbolicLink(root.resolve("client/user/external-link"), outside);

    Instant now = Instant.parse("2026-01-02T00:00:00Z");
    Files.setLastModifiedTime(fresh, FileTime.from(now.minus(Duration.ofHours(1))));
    Files.setLastModifiedTime(expired, FileTime.from(now.minus(Duration.ofDays(2))));
    Files.setLastModifiedTime(active, FileTime.from(now.minus(Duration.ofDays(2))));
    int removed = WorkspaceJanitor.clean(root, 3, Duration.ofHours(24), Clock.fixed(now, ZoneOffset.UTC),
        candidate -> candidate.equals(active));

    assertEquals(1, removed);
    assertFalse(Files.exists(expired));
    assertTrue(Files.exists(active.resolve("live.txt")));
    assertTrue(Files.exists(fresh.resolve("fresh.txt")));
    assertTrue(Files.exists(outside.resolve("keep.txt")));
    assertTrue(Files.isSymbolicLink(externalLink));
  }

  @Test
  void customLayoutUsesOneManagedLevelAndRejectsSymlinkRoot() throws Exception {
    Path root = Files.createDirectory(temp.resolve("custom"));
    Path expired = Files.createDirectories(root.resolve("conversation"));
    Files.setLastModifiedTime(expired, FileTime.from(Instant.parse("2025-01-01T00:00:00Z")));
    Clock now = Clock.fixed(Instant.parse("2026-01-02T00:00:00Z"), ZoneOffset.UTC);
    assertEquals(1, WorkspaceJanitor.clean(root, 1, Duration.ofHours(24), now));
    assertFalse(Files.exists(expired));

    Path linkedRoot = temp.resolve("linked-root");
    Files.createSymbolicLink(linkedRoot, root);
    assertEquals(0, WorkspaceJanitor.clean(linkedRoot, 1, Duration.ofHours(24), now));
    assertTrue(Files.exists(root));
  }

  @Test
  void lazyCleanupRunsAtMostOncePerTenMinutes() throws Exception {
    Path root = Files.createDirectory(temp.resolve("throttled"));
    Instant now = Instant.parse("2026-01-02T00:00:00Z");
    Clock clock = Clock.fixed(now, ZoneOffset.UTC);
    Path first = Files.createDirectories(root.resolve("first"));
    Files.setLastModifiedTime(first, FileTime.from(now.minus(Duration.ofDays(2))));
    WorkspaceJanitor.resetThrottleForTest();
    long start = 10_000_000L;

    WorkspaceJanitor.maybeClean(root, 1, Duration.ofHours(24), ignored -> false, clock, start);
    assertFalse(Files.exists(first));

    Path second = Files.createDirectories(root.resolve("second"));
    Files.setLastModifiedTime(second, FileTime.from(now.minus(Duration.ofDays(2))));
    WorkspaceJanitor.maybeClean(root, 1, Duration.ofHours(24), ignored -> false, clock,
        start + WorkspaceJanitor.RUN_INTERVAL_MILLIS / 2);
    assertTrue(Files.exists(second));
    WorkspaceJanitor.maybeClean(root, 1, Duration.ofHours(24), ignored -> false, clock,
        start + WorkspaceJanitor.RUN_INTERVAL_MILLIS);
    assertFalse(Files.exists(second));
    WorkspaceJanitor.resetThrottleForTest();
  }
}
