package com.etendoerp.copilot.toolpack.tools;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.List;

import org.codehaus.jettison.json.JSONArray;
import org.codehaus.jettison.json.JSONException;
import org.codehaus.jettison.json.JSONObject;

import com.etendoerp.copilot.engine.tool.ToolExecutionContext;

import dev.langchain4j.agent.tool.ToolSpecification;
import dev.langchain4j.model.chat.request.json.JsonObjectSchema;
import dev.langchain4j.model.chat.request.json.JsonRawSchema;

final class FileToolSupport {
  private FileToolSupport() {}

  static ToolSpecification spec(String name, String description, String rawProperties, String... required) {
    try {
      JSONObject props = new JSONObject(rawProperties);
      JsonObjectSchema.Builder schema = JsonObjectSchema.builder();
      JSONArray names = props.names();
      for (int i = 0; names != null && i < names.length(); i++) {
        String key = names.getString(i);
        schema.addProperty(key, JsonRawSchema.from(props.getJSONObject(key).toString()));
      }
      if (required.length > 0) schema.required(List.of(required));
      return ToolSpecification.builder().name(name).description(description).parameters(schema.build()).build();
    } catch (JSONException e) { throw new IllegalStateException(e); }
  }

  static String requiredString(JSONObject args, String key) throws JSONException {
    String value = args.optString(key, null);
    if (value == null || value.isBlank()) throw new IllegalArgumentException("'" + key + "' is required");
    return value;
  }

  static Path readPath(ToolExecutionContext ctx, String path) throws IOException {
    Path resolved = ToolWorkspace.resolveRead(ctx, path);
    if (!Files.isRegularFile(resolved) || !Files.isReadable(resolved)) {
      throw new java.io.FileNotFoundException("File does not exist or is not readable: " + path);
    }
    long size = Files.size(resolved);
    if (size > ToolWorkspace.maxFileBytes()) throw new IllegalArgumentException("File exceeds the configured per-file size limit");
    return resolved;
  }

  static Path writePath(ToolExecutionContext ctx, String path) throws IOException {
    return ToolWorkspace.resolveWriteParent(ctx, path);
  }

  static Path writeBytes(ToolExecutionContext ctx, String path, byte[] content) throws IOException {
    if (content.length > ToolWorkspace.maxFileBytes()) throw new IllegalArgumentException("File exceeds the configured per-file size limit");
    Path target = writePath(ctx, path);
    synchronized (ToolWorkspace.writeLock(ctx)) {
      ToolWorkspace.checkWrite(ctx, target, content.length, 1);
      Files.write(target, content, StandardOpenOption.CREATE, StandardOpenOption.TRUNCATE_EXISTING,
          StandardOpenOption.WRITE, java.nio.file.LinkOption.NOFOLLOW_LINKS);
      ToolWorkspace.recordWrite(ctx, target);
    }
    return target;
  }

  static Path writeString(ToolExecutionContext ctx, String path, String content) throws IOException {
    return writeBytes(ctx, path, content.getBytes(StandardCharsets.UTF_8));
  }

  static Path writeStream(ToolExecutionContext ctx, String path, InputStream input, long maxBytes)
      throws IOException {
    Path target = writePath(ctx, path);
    synchronized (ToolWorkspace.writeLock(ctx)) {
      ToolWorkspace.checkWrite(ctx, target, 0, 1);
      ByteArrayOutputStream buffer = new ByteArrayOutputStream();
      byte[] bytes = new byte[8192];
      long count = 0;
      int read;
      while ((read = input.read(bytes)) >= 0) {
        count += read;
        if (count > Math.min(maxBytes, ToolWorkspace.maxFileBytes())) {
          throw new IllegalArgumentException("File exceeds the configured size limit");
        }
        ToolWorkspace.checkWrite(ctx, target, count, 1);
        buffer.write(bytes, 0, read);
      }
      Files.write(target, buffer.toByteArray(), StandardOpenOption.CREATE, StandardOpenOption.TRUNCATE_EXISTING,
          StandardOpenOption.WRITE, java.nio.file.LinkOption.NOFOLLOW_LINKS);
      ToolWorkspace.recordWrite(ctx, target);
    }
    return target;
  }


  static String sanitizeFilename(String filename) {
    String name = Path.of(filename).getFileName().toString().replaceAll("[^A-Za-z0-9._-]", "_");
    return name.isBlank() || name.equals(".") || name.equals("..") ? "downloaded_file" : name;
  }
  static void deleteTracked(ToolExecutionContext ctx, Path path) throws IOException {
    ToolWorkspace.recordDelete(ctx, path);
  }
}
