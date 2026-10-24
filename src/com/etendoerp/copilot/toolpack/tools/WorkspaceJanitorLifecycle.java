package com.etendoerp.copilot.toolpack.tools;

import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.ThreadFactory;
import java.util.concurrent.TimeUnit;

import javax.annotation.PostConstruct;
import javax.annotation.PreDestroy;
import javax.enterprise.context.ApplicationScoped;

/** Starts and stops the daemon workspace janitor with the application context. */
@ApplicationScoped
public class WorkspaceJanitorLifecycle {
  private ScheduledExecutorService executor;

  @PostConstruct
  public void start() {
    ThreadFactory factory = runnable -> {
      Thread thread = new Thread(runnable, "copilot-workspace-janitor");
      thread.setDaemon(true);
      return thread;
    };
    executor = Executors.newSingleThreadScheduledExecutor(factory);
    executor.scheduleWithFixedDelay(ToolWorkspace::cleanExpiredWorkspaces, 10, 10, TimeUnit.MINUTES);
  }

  @PreDestroy
  public void stop() {
    if (executor != null) executor.shutdownNow();
  }
}
