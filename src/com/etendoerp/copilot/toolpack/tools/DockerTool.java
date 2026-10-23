package com.etendoerp.copilot.toolpack.tools;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.util.ArrayList;
import java.util.Base64;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;

import javax.enterprise.context.ApplicationScoped;
import javax.inject.Named;

import org.apache.commons.compress.archivers.tar.TarArchiveEntry;
import org.apache.commons.compress.archivers.tar.TarArchiveInputStream;
import org.apache.commons.compress.archivers.tar.TarArchiveOutputStream;
import org.codehaus.jettison.json.JSONArray;
import org.codehaus.jettison.json.JSONObject;
import dev.langchain4j.agent.tool.ToolSpecification;
import dev.langchain4j.model.chat.request.json.JsonObjectSchema;
import dev.langchain4j.model.chat.request.json.JsonRawSchema;

import com.etendoerp.copilot.engine.tool.ServerTool;
import com.etendoerp.copilot.engine.tool.ToolExecutionContext;
import com.github.dockerjava.api.command.CreateContainerResponse;
import com.github.dockerjava.api.DockerClient;
import com.github.dockerjava.api.async.ResultCallback;
import com.github.dockerjava.api.model.Frame;
import com.github.dockerjava.api.model.HostConfig;
import com.github.dockerjava.core.DockerClientBuilder;

@ApplicationScoped
@Named("DockerTool")
public class DockerTool implements ServerTool {
  private static final String IMAGE = "python:3.10-slim";
  private static final String PREFIX = "tempenv-copilot-";
  private static final int MAX_OUTPUT_BYTES = 256 * 1024;
  private static final long MEMORY_LIMIT = 512L * 1024 * 1024;

  @Override public String name() { return "DockerTool"; }
  @Override public ToolSpecification specification() {
    return ToolSpecification.builder().name(name()).description("A tool that manages Docker containers to run Python or Bash code. Containers are deleted when specified after 1 hour of inactivity.")
        .parameters(JsonObjectSchema.builder()
            .addProperty("executor", JsonRawSchema.from("{\"type\":\"string\",\"title\":\"Executor\",\"description\":\"The executor: python or bash.\"}"))
            .addProperty("code", JsonRawSchema.from("{\"type\":\"string\",\"title\":\"Code\",\"description\":\"The code to execute.\"}"))
            .addProperty("files_to_copy", JsonRawSchema.from("{\"type\":\"array\",\"items\":{\"type\":\"string\"},\"title\":\"Files to copy\",\"description\":\"List of file paths to copy to the container. There will be copied to the same path in the container. Example: [\\\"/path/to/file1\\\", \\\"/path/to/file2\\\"]\"}"))
            .required(List.of("executor", "code", "files_to_copy")).build()).build();
  }

  @Override public String execute(JSONObject args, ToolExecutionContext ctx) throws Exception {
    String executor = args.optString("executor", ""), code = args.optString("code", "");
    if (executor.isEmpty()) return "Executor is required for EXEC mode";
    if (!executor.equals("python") && !executor.equals("bash")) return "Invalid executor, must be \"python\" or \"bash\"";
    if (code.isEmpty()) return "Code is required for EXEC mode";
    Path workspace = ToolWorkspace.workDir(ctx).toRealPath();
    List<Path> filePaths = new ArrayList<>();
    JSONArray files = args.optJSONArray("files_to_copy");
    if (files != null) {
      for (int i = 0; i < files.length(); i++) {
        Path file = FileToolSupport.readPath(ctx, files.getString(i)).toRealPath();
        if (!file.startsWith(workspace) || !Files.isRegularFile(file)) throw new IllegalArgumentException("DockerTool accepts only regular files inside the conversation workspace");
        filePaths.add(file);
      }
    }
    String id = containerName(ctx);
    try (DockerClient docker = DockerClientBuilder.getInstance().build()) {
      String containerId = findOrStart(docker, id, environment(ctx), ctx);
      for (Path file : filePaths) copyInto(docker, containerId, workspace, file);
      String[] argsForExec = executor.equals("python") ? new String[] {"python", "-c", code} : new String[] {"bash", "-c", code};
      String output = runCommand(docker, containerId, argsForExec);
      for (Path file : filePaths) copyOut(docker, containerId, workspace, file, ctx);
      return output;
    }
  }

  private static String containerName(ToolExecutionContext ctx) {
    String conversation = ctx.conversationId() == null ? "default" : ctx.conversationId();
    String suffix = Base64.getUrlEncoder().withoutPadding().encodeToString(conversation.getBytes(java.nio.charset.StandardCharsets.UTF_8));
    if (suffix.length() > 40) suffix = suffix.substring(0, 40);
    return PREFIX + suffix.replaceAll("[^A-Za-z0-9_.-]", "_");
  }

  private static List<String> environment(ToolExecutionContext ctx) {
    List<String> env = new ArrayList<>();
    JSONObject extra = ctx.extraInfo();
    if (extra != null) flattenEnv(extra, env);
    return env;
  }

  private static void flattenEnv(JSONObject object, List<String> env) {
    var keys = object.keys();
    while (keys.hasNext()) {
      String key = String.valueOf(keys.next());
      Object value = object.opt(key);
      if (value instanceof String text && !isSecretKey(key)) env.add(key + "=" + text);
      else if (value instanceof JSONObject nested) flattenEnv(nested, env);
    }
  }
  static boolean networkEnabled(ToolExecutionContext ctx) {
    String configured = System.getProperty("copilot.tools.docker.network.enabled");
    if (configured == null) {
      try {
        configured = org.openbravo.base.session.OBPropertiesProvider.getInstance()
            .getOpenbravoProperties().getProperty("copilot.tools.docker.network.enabled");
      } catch (RuntimeException ignored) {
        // Unit tests can run without an initialized Openbravo.properties provider.
      }
    }
    if (configured != null) return Boolean.parseBoolean(configured);
    JSONObject extra = ctx == null ? null : ctx.extraInfo();
    JSONObject appConfig = extra == null ? null : extra.optJSONObject("tool_config");
    appConfig = appConfig == null || ctx == null ? null : appConfig.optJSONObject(ctx.agentId());
    JSONObject tool = appConfig == null ? null : appConfig.optJSONObject("9154462E3B9F427496F00FA5C136F357");
    return tool != null && tool.optBoolean("network_enabled", false);
  }

  static boolean isSecretKey(String key) {
    String lower = key.toLowerCase(java.util.Locale.ROOT);
    return lower.contains("token") || lower.contains("password") || lower.contains("secret") || lower.contains("authorization") || lower.contains("credential") || lower.contains("bearer") || lower.equals("auth") || lower.contains("key");
  }
  private static String findOrStart(DockerClient docker, String name, List<String> environment, ToolExecutionContext ctx) {
    removeExpiredContainers(docker);
    var existing = docker.listContainersCmd().withShowAll(true).exec();
    for (var container : existing) {
      for (String cname : container.getNames()) {
        if (cname.equals("/" + name)) {
          Map<String, String> labels = container.getLabels();
          if (labels == null || !"DockerTool".equals(labels.get("copilot.tool")) || !name.equals(labels.get("copilot.conversation"))) {
            throw new SecurityException("Refusing to reuse an untrusted Docker container");
          }
          var details = docker.inspectContainerCmd(container.getId()).exec();
          if (details.getMounts() != null && !details.getMounts().isEmpty()) {
            throw new SecurityException("Refusing to reuse a Docker container with host mounts");
          }
          String desiredNetwork = networkEnabled(ctx) ? "bridge" : "none";
          if (!desiredNetwork.equals(details.getHostConfig().getNetworkMode())) {
            throw new SecurityException("Refusing to reuse a Docker container with a different network policy");
          }
          return container.getId();
        }
      }
    }
    String networkMode = networkEnabled(ctx) ? "bridge" : "none";
    HostConfig host = HostConfig.newHostConfig().withMemory(MEMORY_LIMIT).withMemorySwap(MEMORY_LIMIT)
        .withCpuPeriod(100_000L).withCpuQuota(50_000L).withPidsLimit(128L).withNetworkMode(networkMode);
    CreateContainerResponse created = docker.createContainerCmd(IMAGE).withName(name)
        .withCmd("sh", "-c", "while true; do sleep 3600; done")
        .withWorkingDir("/workspace").withEnv(environment).withHostConfig(host)
        .withLabels(Map.of("copilot.tool", "DockerTool", "copilot.conversation", name)).exec();
    docker.startContainerCmd(created.getId()).exec();
    return created.getId();
  }

  private static void removeExpiredContainers(DockerClient docker) {
    long cutoff = java.time.Instant.now().minus(Duration.ofHours(1)).getEpochSecond();
    for (var container : docker.listContainersCmd().withShowAll(true).exec()) {
      Map<String, String> labels = container.getLabels();
      if (labels != null && "DockerTool".equals(labels.get("copilot.tool")) && container.getCreated() < cutoff) {
        docker.stopContainerCmd(container.getId()).withTimeout(3).exec();
        docker.removeContainerCmd(container.getId()).withForce(true).exec();
      }
    }
  }

  private static String runCommand(DockerClient docker, String container, String[] command) throws Exception {
    var exec = docker.execCreateCmd(container).withCmd(command).withWorkingDir("/workspace")
        .withAttachStdout(true).withAttachStderr(true).exec();
    BoundedFrames frames = new BoundedFrames(MAX_OUTPUT_BYTES);
    docker.execStartCmd(exec.getId()).exec(frames).awaitCompletion(3, TimeUnit.MINUTES);
    var inspection = docker.inspectExecCmd(exec.getId()).exec();
    if (inspection.isRunning()) {
      docker.stopContainerCmd(container).withTimeout(3).exec();
      docker.removeContainerCmd(container).withForce(true).exec();
      throw new IllegalStateException("Docker command timed out and its container was stopped.");
    }
    return frames.text();
  }

  private static void copyInto(DockerClient docker, String container, Path workspace, Path file) throws Exception {
    Path relative = workspace.relativize(file);
    ByteArrayOutputStream bytes = new ByteArrayOutputStream();
    try (TarArchiveOutputStream tar = new TarArchiveOutputStream(bytes)) {
      tar.setLongFileMode(TarArchiveOutputStream.LONGFILE_POSIX);
      TarArchiveEntry entry = new TarArchiveEntry(relative.toString().replace('\\', '/'));
      entry.setSize(Files.size(file));
      tar.putArchiveEntry(entry);
      Files.copy(file, tar);
      tar.closeArchiveEntry();
      tar.finish();
    }
    docker.copyArchiveToContainerCmd(container).withRemotePath("/workspace").withTarInputStream(new java.io.ByteArrayInputStream(bytes.toByteArray())).exec();
  }

  private static void copyOut(DockerClient docker, String container, Path workspace, Path source,
      ToolExecutionContext ctx) throws Exception {
    String relative = workspace.relativize(source).toString().replace('\\', '/');
    try (InputStream archive = docker.copyArchiveFromContainerCmd(container, "/workspace/" + relative).exec();
        TarArchiveInputStream tar = new TarArchiveInputStream(archive)) {
      TarArchiveEntry entry;
      while ((entry = tar.getNextTarEntry()) != null) {
        if (entry.isSymbolicLink() || entry.isLink()) throw new SecurityException("Container returned a link entry");
        if (entry.isDirectory()) continue;
        Path target = source.getParent().resolve(entry.getName()).normalize();
        if (!target.startsWith(workspace)) throw new SecurityException("Container attempted to write outside the workspace");
        FileToolSupport.writeStream(ctx, target.toString(), tar, ToolWorkspace.maxFileBytes());
      }
    }
  }

  @Override public Duration timeout() { return Duration.ofMinutes(4); }

  private static final class BoundedFrames extends ResultCallback.Adapter<Frame> {
    private final int max;
    private final ByteArrayOutputStream out = new ByteArrayOutputStream();
    BoundedFrames(int max) { this.max = max; }
    @Override public synchronized void onNext(Frame frame) {
      byte[] payload = frame.getPayload();
      int remaining = max - out.size();
      if (remaining > 0) out.write(payload, 0, Math.min(payload.length, remaining));
    }
    synchronized String text() { return out.toString(java.nio.charset.StandardCharsets.UTF_8); }
  }
}
