package com.etendoerp.copilot.toolpack.tools;

import java.awt.image.BufferedImage;
import java.io.ByteArrayOutputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.UUID;
import javax.enterprise.context.ApplicationScoped;
import javax.imageio.ImageIO;
import javax.inject.Named;
import org.codehaus.jettison.json.JSONArray;
import org.codehaus.jettison.json.JSONObject;
import com.etendoerp.copilot.engine.tool.ServerTool;
import com.etendoerp.copilot.engine.tool.ToolExecutionContext;
import com.etendoerp.copilot.util.PdfRenderer;
import dev.langchain4j.agent.tool.ToolSpecification;

@ApplicationScoped @Named("PdfToImagesTool")
public class PdfToImagesTool implements ServerTool {
  public String name() { return "PdfToImagesTool"; }
  public ToolSpecification specification() {
    return FileToolSupport.spec(name(), "Converts a PDF file into an array of images, each representing a page of the PDF.",
        "{\"path\":{\"type\":\"string\",\"description\":\"Path of the PDF to be converted\"}}", "path");
  }
  public String execute(JSONObject args, ToolExecutionContext context) throws Exception {
    String input = FileToolSupport.requiredString(args, "path");
    Path pdf = FileToolSupport.readPath(context, input);
    List<BufferedImage> images = PdfRenderer.render(pdf, 2f);
    Path output = ToolWorkspace.resolveWrite(context,
        ToolWorkspace.workDir(context).resolve("pdf-pages-" + UUID.randomUUID()).toString());
    Files.createDirectories(output);
    ToolWorkspace.resolveWrite(context, output.toString());
    JSONArray paths = new JSONArray();
    for (int i = 0; i < images.size(); i++) {
      ByteArrayOutputStream bytes = new ByteArrayOutputStream();
      if (!ImageIO.write(images.get(i), "png", bytes)) throw new IllegalStateException("PNG writer is unavailable");
      Path page = FileToolSupport.writeBytes(context, output.resolve("page_" + i + ".png").toString(), bytes.toByteArray());
      paths.put(page.toString());
    }
    return paths.toString();
  }
}
