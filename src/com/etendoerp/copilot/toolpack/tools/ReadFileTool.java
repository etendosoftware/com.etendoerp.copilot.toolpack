package com.etendoerp.copilot.toolpack.tools;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import javax.enterprise.context.ApplicationScoped;
import javax.inject.Named;
import org.codehaus.jettison.json.JSONObject;
import com.etendoerp.copilot.engine.tool.ServerTool;
import com.etendoerp.copilot.engine.tool.ToolExecutionContext;
import dev.langchain4j.agent.tool.ToolSpecification;

@ApplicationScoped @Named("ReadFileTool")
public class ReadFileTool implements ServerTool {
  public String name() { return "ReadFileTool"; }
  public ToolSpecification specification() { return FileToolSupport.spec(name(), "This is a tool for reading files. Receives \\\"filepath\\\" string parameter. The \\\"filepath\\\" parameter is the path of the file to read. The tool will return the content of the file. Example of input: { \\\"filepath\\\": \\\"/tmp/test.txt\\\" }", "{\"filepath\":{\"type\":\"string\",\"title\":\"Filepath\",\"description\":\"The path of the file to read.\"}}", "filepath"); }
  public String execute(JSONObject args, ToolExecutionContext ctx) throws Exception {
    var path = FileToolSupport.readPath(ctx, FileToolSupport.requiredString(args, "filepath"));
    return new JSONObject().put("message", Files.readString(path, StandardCharsets.UTF_8)).toString();
  }
}
