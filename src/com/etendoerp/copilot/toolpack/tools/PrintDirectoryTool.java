package com.etendoerp.copilot.toolpack.tools;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import javax.enterprise.context.ApplicationScoped;
import javax.inject.Named;
import org.codehaus.jettison.json.JSONObject;
import com.etendoerp.copilot.engine.tool.ServerTool;
import com.etendoerp.copilot.engine.tool.ToolExecutionContext;
import dev.langchain4j.agent.tool.ToolSpecification;

@ApplicationScoped @Named("PrintDirectoryTool")
public class PrintDirectoryTool implements ServerTool {
 public String name(){return "PrintDirectoryTool";}
 public ToolSpecification specification(){return FileToolSupport.spec(name()," This tool prints the files and directories of the a directory.","{\"path\":{\"type\":\"string\",\"description\":\"The path of the directory to print\"},\"recursive\":{\"type\":\"boolean\",\"default\":false,\"description\":\"If true, print files recursively.\"},\"extensions\":{\"type\":\"string\",\"default\":null,\"description\":\"Comma-separated extensions to include.\"},\"ignore_folder\":{\"type\":\"string\",\"default\":null,\"description\":\"Comma-separated names to ignore.\"}}","path");}
 public String execute(JSONObject a,ToolExecutionContext c)throws Exception{
   String requested = FileToolSupport.requiredString(a, "path"); Path base=ToolWorkspace.resolveRead(c,requested); if(!Files.exists(base))return new JSONObject().put("error","Path does not exist: "+requested).toString();
   boolean recursive=a.optBoolean("recursive",false); List<String> ext=csv(a.optString("extensions","")), ignore=csv(a.optString("ignore_folder","")); StringBuilder out=new StringBuilder();
   try(var walk=recursive?Files.walk(base):Files.list(base)){ walk.filter(p->!p.equals(base)).filter(p->{Path rel=base.relativize(p);for(Path part:rel)if(part.toString().startsWith(".")||ignore.contains(part.toString()))return false;try{ToolWorkspace.resolveRead(c,p.toString());}catch(IllegalArgumentException e){return false;}return Files.isRegularFile(p);}).filter(p->ext.isEmpty()||ext.stream().anyMatch(x->p.getFileName().toString().toLowerCase().endsWith(x))).forEach(p->out.append(p.toAbsolutePath()).append('\n')); }
   return new JSONObject().put("message",out.toString()).toString();
 }
 private static List<String> csv(String text){List<String> r=new ArrayList<>();for(String x:text.split(","))if(!x.isBlank())r.add(x.trim().toLowerCase());return r;}
}
