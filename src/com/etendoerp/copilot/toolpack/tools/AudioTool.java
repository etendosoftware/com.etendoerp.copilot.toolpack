package com.etendoerp.copilot.toolpack.tools;

import java.nio.file.Files;

import javax.enterprise.context.ApplicationScoped;
import javax.inject.Named;

import org.codehaus.jettison.json.JSONObject;

import com.etendoerp.copilot.engine.tool.ToolExecutionContext;
import com.etendoerp.copilot.engine.tool.ServerTool;

import dev.langchain4j.agent.tool.ToolSpecification;
import dev.langchain4j.model.chat.request.json.JsonObjectSchema;
import dev.langchain4j.model.chat.request.json.JsonRawSchema;

/** OpenAI Whisper transcription tool. */
@ApplicationScoped @Named("AudioTool")
public class AudioTool implements ServerTool {
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
    return com.etendoerp.copilot.util.CopilotAudioTranscription.transcribe(file.toFile());
  }
}
