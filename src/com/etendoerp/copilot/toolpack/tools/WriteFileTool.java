package com.etendoerp.copilot.toolpack.tools;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.nio.file.attribute.PosixFilePermissions;
import java.nio.file.attribute.PosixFileAttributeView;
import java.time.Instant;
import javax.enterprise.context.ApplicationScoped;
import javax.inject.Named;
import org.codehaus.jettison.json.JSONObject;
import com.etendoerp.copilot.engine.tool.ServerTool;
import com.etendoerp.copilot.engine.tool.ToolExecutionContext;
import dev.langchain4j.agent.tool.ToolSpecification;

@ApplicationScoped @Named("WriteFileTool")
public class WriteFileTool implements ServerTool {
  public String name() { return "WriteFileTool"; }
  public ToolSpecification specification() { return FileToolSupport.spec(name(), "This is a tool for writing files. Receives filepath, content, override and lineno. When override is false, appends or inserts content at the given line number.", "{\"filepath\":{\"type\":\"string\",\"description\":\"The path of the file to write.\"},\"content\":{\"type\":\"string\",\"description\":\"The content of the file to write.\"},\"override\":{\"type\":\"boolean\",\"default\":true,\"description\":\"If true, the tool will override the file.\"},\"lineno\":{\"type\":\"integer\",\"default\":-1,\"description\":\"The line number where to write the content.\"}}", "filepath", "content"); }
  public String execute(JSONObject args, ToolExecutionContext ctx) throws Exception {
    Path path = FileToolSupport.writePath(ctx, FileToolSupport.requiredString(args, "filepath"));
    String content = args.optString("content", null);
    if (content == null) throw new IllegalArgumentException("'content' is required");
    boolean backup = Files.exists(path);
    String old = "";
    if (backup) {
      old = Files.readString(FileToolSupport.readPath(ctx, path.toString()), StandardCharsets.UTF_8);
      FileToolSupport.writeBytes(ctx, path + ".bak" + Instant.now().toEpochMilli(), Files.readAllBytes(path));
    }
    boolean override = args.optBoolean("override", true);
    if (!override) {
      int line = args.optInt("lineno", -1);
      if (line == -1) old += content;
      else { String[] lines = old.split("\\n", -1); if (line < 0 || line > lines.length) throw new IllegalArgumentException("lineno is outside the file"); var list = new java.util.ArrayList<>(java.util.Arrays.asList(lines)); list.add(line, content); old = String.join("\n", list); }
      content = old;
    }
    FileToolSupport.writeString(ctx, path.toString(), content);
    return new JSONObject().put("message", "File " + path + " written successfully, backup: " + backup).toString();
  }
  private static String mode(String octal) { int bits = Integer.parseInt(octal, 8); StringBuilder out = new StringBuilder(9); char[] symbols = {'r','w','x'}; for (int i=8;i>=0;i--) out.append((bits & (1<<i)) != 0 ? symbols[(8-i)%3] : '-'); return out.toString(); }
}
