package com.etendoerp.copilot.toolpack.tools;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.file.Files;
import java.time.Duration;
import java.util.UUID;

import javax.enterprise.context.ApplicationScoped;
import javax.inject.Named;

import org.codehaus.jettison.json.JSONObject;

import com.etendoerp.copilot.engine.tool.ToolExecutionContext;
import com.etendoerp.copilot.engine.tool.ServerTool;
import com.etendoerp.copilot.toolpack.tools.ToolWorkspace;
import com.etendoerp.copilot.toolpack.tools.support.ToolSecrets;

import dev.langchain4j.agent.tool.ToolSpecification;
import dev.langchain4j.model.chat.request.json.JsonObjectSchema;
import dev.langchain4j.model.chat.request.json.JsonRawSchema;

/** OpenAI Whisper transcription tool. */
@ApplicationScoped @Named("AudioTool")
public class AudioTool implements ServerTool {
  private static final HttpClient HTTP = HttpClient.newHttpClient();
  @Override public String name() { return "AudioTool"; }
  @Override public ToolSpecification specification() {
    return ToolSpecification.builder().name(name()).description("This is a tool that uses OpenAI's API to transcribe audio files.")
        .parameters(JsonObjectSchema.builder().addProperty("path", JsonRawSchema.from("{\"type\":\"string\",\"description\":\"Path of the audio to be processed.\"}" )).required(java.util.Collections.singletonList("path")).build()).build();
  }
  @Override public String execute(JSONObject args, ToolExecutionContext ctx) throws Exception {
    String path = args.optString("path", null);
    if (path == null || path.isBlank()) throw new IllegalArgumentException("path is required");
    java.nio.file.Path file = FileToolSupport.readPath(ctx, path);
    if (!Files.isRegularFile(file)) throw new java.io.FileNotFoundException("Filename " + file + " doesn't exist");
    String key = ToolSecrets.get("openai.api.key");
    if (key == null) throw new IllegalStateException("OpenAI API key is not configured (openai.api.key)");
    String boundary = "----EtendoCopilot" + UUID.randomUUID();
    byte[] data = Files.readAllBytes(file);
    byte[] prefix = ("--"+boundary+"\r\nContent-Disposition: form-data; name=\"model\"\r\n\r\nwhisper-1\r\n--"+boundary+"\r\nContent-Disposition: form-data; name=\"file\"; filename=\""+file.getFileName()+"\"\r\nContent-Type: application/octet-stream\r\n\r\n").getBytes(java.nio.charset.StandardCharsets.UTF_8);
    byte[] suffix = ("\r\n--"+boundary+"--\r\n").getBytes(java.nio.charset.StandardCharsets.UTF_8);
    byte[] body = new byte[prefix.length+data.length+suffix.length];
    System.arraycopy(prefix,0,body,0,prefix.length); System.arraycopy(data,0,body,prefix.length,data.length); System.arraycopy(suffix,0,body,prefix.length+data.length,suffix.length);
    HttpRequest req = HttpRequest.newBuilder(URI.create("https://api.openai.com/v1/audio/transcriptions")).timeout(Duration.ofMinutes(2)).header("Authorization","Bearer "+key).header("Content-Type","multipart/form-data; boundary="+boundary).POST(HttpRequest.BodyPublishers.ofByteArray(body)).build();
    HttpResponse<String> response = HTTP.send(req,HttpResponse.BodyHandlers.ofString());
    if (response.statusCode()<200 || response.statusCode()>=300) throw new IllegalStateException("Audio transcription failed (HTTP "+response.statusCode()+")");
    JSONObject result = new JSONObject(response.body());
    return result.optString("text", response.body());
  }
}
