package com.etendoerp.copilot.toolpack.tools;

import java.awt.image.BufferedImage;
import java.io.ByteArrayOutputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Base64;
import java.util.List;
import java.util.Optional;
import javax.enterprise.context.ApplicationScoped;
import javax.enterprise.inject.Instance;
import javax.inject.Inject;
import javax.inject.Named;
import javax.imageio.ImageIO;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;
import org.codehaus.jettison.json.JSONObject;
import com.etendoerp.copilot.engine.ChatModelFactory;
import com.etendoerp.copilot.engine.tool.ServerTool;
import com.etendoerp.copilot.engine.tool.ToolExecutionContext;
import com.etendoerp.copilot.util.OcrSchemaBuilder;
import com.etendoerp.copilot.util.PdfRenderer;
import com.etendoerp.copilot.toolpack.tools.ocr.ReferenceSearch;
import dev.langchain4j.agent.tool.ToolSpecification;
import dev.langchain4j.data.image.Image;
import dev.langchain4j.data.message.AiMessage;
import dev.langchain4j.data.message.ImageContent;
import dev.langchain4j.data.message.SystemMessage;
import dev.langchain4j.data.message.UserMessage;
import dev.langchain4j.model.chat.ChatModel;
import dev.langchain4j.model.chat.request.ChatRequest;
import dev.langchain4j.model.chat.request.ResponseFormat;
import dev.langchain4j.model.chat.request.ResponseFormatType;
import dev.langchain4j.model.chat.request.json.JsonRawSchema;
import dev.langchain4j.model.chat.request.json.JsonSchema;
import dev.langchain4j.model.chat.response.ChatResponse;

/** Image and PDF OCR tool with optional agent-specific reference templates. */
@ApplicationScoped @Named("OcrTool")
public class OcrTool implements ServerTool {
  private static final Logger LOG = LogManager.getLogger(OcrTool.class);
  static final String BASIC = " Thoroughly analyze and extract all the information from the image(s).\n DO NOT SUMMARIZE OR OMIT INFORMATION, EVEN IF IT IS REPEATED OR THERE ARE SIMILAR PARTS.\n The information has to be returned in JSON format.\n";
  static final String REFERENCE_PROMPT = "You are an expert in extracting information from invoices and structured documents. Extract the key information from the document provided in the images.\n\nStrict instructions:\n- Use ONLY the reference image (first image) to determine what data to extract. The data must be clearly highlighted in red with boxes in the reference image. GIVE ABSOLUTE PRIORITY to data indicated in red; ignore or do not consider data labeled in black or other colors if they do not match the red highlights.\n- If a data point is not indicated or highlighted in red in the reference image, DO NOT extract it or include it in the output. Leave it as null or empty.\n- Use the exact text from the document for extractions, but only from the areas highlighted in red.\n- The information has to be returned in JSON format.\n- DO NOT SUMMARIZE OR OMIT INFORMATION from the highlighted red areas, EVEN IF IT IS REPEATED OR THERE ARE SIMILAR PARTS.\n\nThe first image is the REFERENCE with red markers. The following images are the document to extract data from.\n";
  private static final String DESCRIPTION = "Extracts structured data from images and PDF documents and returns JSON. Automatically finds and uses similar reference templates from the agent's vector database to guide extraction. Reference templates contain visual markers (red boxes) highlighting which data fields to extract. Best for: invoices, receipts, forms, contracts, and any structured document with consistent layouts. Reference images must be uploaded to the agent's database using the /addToVectorDB endpoint. Supports: JPEG, PNG, WebP, GIF, and multi-page PDF files. Supports extensible structured output schemas - add new schemas in tools/schemas/ directory. File must be accessible in the local file system.";
  @Inject Instance<ReferenceSearch> referenceSearch;
  @Override public String name() { return "OcrTool"; }
  @Override public ToolSpecification specification() { return FileToolSupport.spec(name(), DESCRIPTION,
      "{\"path\":{\"type\":\"string\",\"description\":\"Absolute or relative path to the image or PDF file to be processed. The file must exist in the local file system.\"},\"question\":{\"type\":\"string\",\"description\":\"Specific instructions or question describing what information to extract from the document. Be precise about the data fields needed (e.g., 'Extract invoice number, date, total amount, and vendor name'). Clear instructions improve extraction accuracy.\"},\"structured_output\":{\"type\":\"string\",\"description\":\"Specify a schema name to use structured output format (e.g., 'Invoice'). Available schemas are loaded from tools/schemas/ directory. When specified, the response will follow the predefined schema structure. Leave None for unstructured JSON extraction.\"},\"force_structured_output_compat\":{\"type\":\"boolean\",\"default\":false,\"description\":\"Optional. When True (or when the selected model starts with 'gpt-5'), do not use the LLM's structured-output wrapper. Instead the tool will request structured output by embedding the schema JSON directly into the system prompt for compatibility with older agents.\"},\"disable_threshold_filter\":{\"type\":\"boolean\",\"default\":false,\"description\":\"Optional. When True, ignore the configured similarity threshold and return the most similar reference found in the agent database (disables threshold filtering). Default: False.\"},\"scale\":{\"type\":\"number\",\"default\":3.0,\"description\":\"PDF render scale factor (e.g., 2.0 = ~200 DPI, 3.0 = ~300 DPI). Higher values yield better quality but larger size and slower processing. Default: 3.0.\"}}", "path", "question"); }
  @Override public String execute(JSONObject a, ToolExecutionContext ctx) throws Exception {
    Path searchImage = null;
    boolean temporarySearchImage = false;
    try {
      String input = FileToolSupport.requiredString(a, "path");
      Path file = FileToolSupport.readPath(ctx, input);
      if (!Files.isRegularFile(file)) throw new java.io.FileNotFoundException("Filename " + file + " doesn't exist");
      String mime = mime(file);
      if (mime == null || !(mime.startsWith("image/") || mime.equals("application/pdf"))) {
        throw new IllegalArgumentException("File " + file + " invalid file format with mime " + mime
            + ". Supported formats: {JPEG=image/jpeg, JPG=image/jpeg, PNG=image/png, WEBP=image/webp, GIF=image/gif, PDF=application/pdf}.");
      }
      List<String> images = loadImages(file, mime, a.optDouble("scale", 3.0));
      String agent = ctx.agentId();
      if (agent == null || agent.isBlank()) {
        return error("OcrTool requires agent_id to access the reference database. Please ensure the tool is properly configured with an agent.");
      }

      if ("application/pdf".equals(mime) && !images.isEmpty()) {
        searchImage = FileToolSupport.writeBytes(ctx,
            ToolWorkspace.workDir(ctx).resolve("ocr-search-" + java.util.UUID.randomUUID() + ".jpeg").toString(),
            Base64.getDecoder().decode(images.get(0)));
        temporarySearchImage = true;
      } else {
        searchImage = file;
      }
      ReferenceSearch.Reference ref = null;
      try {
        if (referenceSearch != null && !referenceSearch.isUnsatisfied() && Files.isRegularFile(searchImage)) {
          Optional<ReferenceSearch.Reference> found = referenceSearch.get().find(
              agent, searchImage, 0.0, a.optBoolean("disable_threshold_filter", false));
          ref = found.orElse(null);
        }
      } catch (Exception e) {
        LOG.debug("OCR reference search unavailable", e);
      }

      String model = "gpt-5-mini";
      String provider = "openai";
      JSONObject extra = ctx.extraInfo();
      JSONObject toolConfig = extra == null ? null : extra.optJSONObject("tool_config");
      JSONObject agents = toolConfig == null ? null : toolConfig.optJSONObject(agent);
      JSONObject config = agents == null ? null : agents.optJSONObject("EB58EEA0AA804C219C4D64260550745A");
      if (config != null) {
        model = config.optString("model", model);
        provider = config.optString("provider", provider);
      }

      String question = a.optString("question", ref == null ? BASIC : REFERENCE_PROMPT);
      String schemaName = a.optString("structured_output", null);
      JSONObject schemaJson = schemaName == null ? null : OcrSchemaBuilder.loadSchema(schemaName);
      if (schemaName != null && schemaJson == null) {
        LOG.debug("OCR schema '{}' was not found", schemaName);
      }
      boolean compatibility = a.optBoolean("force_structured_output_compat", false) || model.startsWith("gpt-5");
      String system = "You are an agent specializing in OCR. You may receive “reference images” with sectors marked in color (usually red) with labels to indicate relevant sectors. Use them in real cases to prioritize content.";
      if (compatibility && schemaJson != null) {
        system += "\nExpected output JSON schema for structured output: " + schemaJson.toString(2);
      }

      List<dev.langchain4j.data.message.ChatMessage> messages = new ArrayList<>();
      messages.add(SystemMessage.from(system));
      if (ref != null) {
        messages.add(UserMessage.from("I will send you an image as an example of a REFERENCE with visual markers (red borders) indicating the positions/sections where the most relevant data on the invoice is located. Next to the box is a label for the section. Use it only as a template to know which areas are important in real images."));
        messages.add(UserMessage.from(ImageContent.from(Image.builder().base64Data(ref.base64()).mimeType("image/jpeg").build())));
        messages.add(AiMessage.from("Understood. Now please send me the real images and specify the information you need me to extract."));
      }
      messages.add(UserMessage.from(question));
      for (String image : images) {
        messages.add(UserMessage.from(ImageContent.from(Image.builder().base64Data(image).mimeType("image/jpeg").build())));
      }

      ChatModel chat = ChatModelFactory.build(new JSONObject()
          .put("provider", provider).put("model", model).put("temperature", 1));
      ChatRequest.Builder request = ChatRequest.builder().messages(messages);
      if (schemaJson != null && !compatibility) {
        request.responseFormat(ResponseFormat.builder()
            .type(ResponseFormatType.JSON)
            .jsonSchema(JsonSchema.builder().name("ocr_output")
                .rootElement(JsonRawSchema.from(schemaJson.toString())).build())
            .build());
      }
      ChatResponse result = chat.chat(request.build());
      if (result.tokenUsage() != null) LOG.debug("OcrTool token usage: {}", result.tokenUsage());
      String response = result.aiMessage().text();
      return schemaJson == null ? response : new JSONObject(response).toString();
    } catch (Exception e) {
      LOG.debug("OCR failure", e);
      return error("An error occurred: " + (e.getMessage() == null ? e.getClass().getSimpleName() : e.getMessage()));
    } finally {
      if (temporarySearchImage) FileToolSupport.deleteTracked(ctx, searchImage);
    }
  }

  static List<String> loadImages(Path file, String mime, double scale) throws Exception {
    List<String> out = new ArrayList<>();
    if ("application/pdf".equals(mime)) {
      for (BufferedImage image : PdfRenderer.render(file, (float) scale)) {
        out.add(encodeJpeg(image));
      }
    } else if ("image/jpeg".equals(mime(file))) {
      out.add(Base64.getEncoder().encodeToString(Files.readAllBytes(file)));
    } else {
      BufferedImage image = ImageIO.read(file.toFile());
      if (image == null) throw new IllegalArgumentException("Unable to decode image: " + file);
      out.add(encodeJpeg(image));
    }
    return out;
  }

  private static String encodeJpeg(BufferedImage image) throws Exception {
    BufferedImage rgb = new BufferedImage(image.getWidth(), image.getHeight(), BufferedImage.TYPE_INT_RGB);
    rgb.getGraphics().drawImage(image, 0, 0, null);
    ByteArrayOutputStream bytes = new ByteArrayOutputStream();
    ImageIO.write(rgb, "jpeg", bytes);
    return Base64.getEncoder().encodeToString(bytes.toByteArray());
  }

  static String mime(Path p) throws Exception {
    String n = p.getFileName().toString().toLowerCase();
    if (n.endsWith(".pdf")) return "application/pdf";
    if (n.endsWith(".jpg") || n.endsWith(".jpeg")) return "image/jpeg";
    if (n.endsWith(".png")) return "image/png";
    if (n.endsWith(".webp")) return "image/webp";
    if (n.endsWith(".gif")) return "image/gif";
    return Files.probeContentType(p);
  }

  static String error(String s) throws Exception { return new JSONObject().put("error", s).toString(); }
}
