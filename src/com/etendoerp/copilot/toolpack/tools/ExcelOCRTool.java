package com.etendoerp.copilot.toolpack.tools;

import java.awt.Color;
import java.awt.Font;
import java.awt.FontMetrics;
import java.awt.Graphics2D;
import java.awt.image.BufferedImage;
import java.io.ByteArrayOutputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Base64;
import java.util.List;
import javax.enterprise.context.ApplicationScoped;
import javax.imageio.ImageIO;
import javax.inject.Named;

import org.codehaus.jettison.json.JSONArray;
import org.codehaus.jettison.json.JSONException;
import org.codehaus.jettison.json.JSONObject;

import com.etendoerp.copilot.engine.ChatModelFactory;
import com.etendoerp.copilot.engine.tool.ServerTool;
import com.etendoerp.copilot.engine.tool.ToolExecutionContext;

import dev.langchain4j.data.image.Image;
import dev.langchain4j.data.message.ChatMessage;
import dev.langchain4j.data.message.ImageContent;
import dev.langchain4j.data.message.SystemMessage;
import dev.langchain4j.data.message.TextContent;
import dev.langchain4j.data.message.UserMessage;
import dev.langchain4j.model.chat.request.ChatRequest;
import dev.langchain4j.model.chat.ChatModel;
import dev.langchain4j.agent.tool.ToolSpecification;

/** Extracts spreadsheet contents using a vision-capable chat model. */
@ApplicationScoped
@Named("ExcelOCRTool")
public class ExcelOCRTool implements ServerTool {
  static final String DESCRIPTION = "Extract structured data from Excel using OCR + Vision model.";
  static final String DEFAULT_PROMPT = "Extract all useful information from the Excel file as a structured JSON. Don't summarize or omit rows.";
  static final String SYSTEM_PROMPT = "You are an expert spreadsheet OCR agent. Extract all useful information from each sheet as structured JSON. Don't summarize or omit rows.";
  private static final int MAX_ROWS_PER_IMAGE = 70;
  private static final int CELL_WIDTH = 180;
  private static final int ROW_HEIGHT = 24;

  public String name() { return "ExcelOCRTool"; }

  public ToolSpecification specification() {
    return FileToolSupport.spec(name(), DESCRIPTION,
        "{\"path\":{\"type\":\"string\",\"description\":\"Path to the Excel file (xls/xlsx/csv)\"},\"question\":{\"type\":\"string\",\"description\":\"Precise instruction on what to extract from the file content.\"}}", "path", "question");
  }

  public String execute(JSONObject arguments, ToolExecutionContext context) throws Exception {
    String input = FileToolSupport.requiredString(arguments, "path");
    Path path = FileToolSupport.readPath(context, input);
    if (!Files.isRegularFile(path)) throw new IllegalArgumentException("Filename " + input + " doesn't exist");
    String extension = input.substring(input.lastIndexOf('.') + 1).toLowerCase();
    if (!List.of("csv", "xls", "xlsx").contains(extension)) throw new IllegalArgumentException("The file must have a .xls, .xlsx, or .csv extension");
    List<JSONArray> sheets = XLSTool.readAllSheets(path);
    if (sheets.stream().allMatch(sheet -> sheet.length() == 0)) throw new IllegalArgumentException("The spreadsheet contains no rows");
    String question = arguments.optString("question", DEFAULT_PROMPT);
    if (question == null || question.isBlank()) question = DEFAULT_PROMPT;
    List<ChatMessage> messages = buildMessages(sheets, question);
    JSONObject request = new JSONObject().put("provider", "openai").put("model", modelName()).put("temperature", 0);
    ChatModel model = ChatModelFactory.build(request);
    return model.chat(ChatRequest.builder().messages(messages).build()).aiMessage().text();
  }

  static List<ChatMessage> buildMessages(JSONArray rows, String question) throws Exception {
    return buildMessages(List.of(rows), question);
  }

  static List<ChatMessage> buildMessages(List<JSONArray> sheets, String question) throws Exception {
    List<ChatMessage> messages = new ArrayList<>();
    messages.add(SystemMessage.from(SYSTEM_PROMPT));
    for (JSONArray rows : sheets) {
      for (int start = 0; start < rows.length(); start += MAX_ROWS_PER_IMAGE) {
        int end = Math.min(start + MAX_ROWS_PER_IMAGE, rows.length());
        JSONArray page = new JSONArray();
        for (int i = start; i < end; i++) page.put(rows.getJSONArray(i));
        messages.add(UserMessage.from(List.of(ImageContent.from(Image.builder()
            .base64Data(Base64.getEncoder().encodeToString(renderTable(page))).mimeType("image/png").build()))));
      }
    }
    messages.add(UserMessage.from(question));
    return messages;
  }

  static String modelName() {
    String model = System.getProperty("COPILOT_OCRTOOL_MODEL");
    if (model == null || model.isBlank()) model = System.getenv("COPILOT_OCRTOOL_MODEL");
    return model == null || model.isBlank() ? "gpt-4.1" : model;
  }


  private static byte[] renderTable(JSONArray rows) throws Exception {
    int columns = 0;
    for (int i = 0; i < rows.length(); i++) columns = Math.max(columns, rows.getJSONArray(i).length());
    columns = Math.max(columns, 1);
    int width = Math.min(2400, columns * CELL_WIDTH + 2);
    int height = Math.max(ROW_HEIGHT + 2, (rows.length() * ROW_HEIGHT) + 2);
    BufferedImage image = new BufferedImage(width, height, BufferedImage.TYPE_INT_RGB);
    Graphics2D graphics = image.createGraphics();
    try {
      graphics.setColor(Color.WHITE);
      graphics.fillRect(0, 0, width, height);
      graphics.setFont(new Font(Font.SANS_SERIF, Font.PLAIN, 12));
      FontMetrics metrics = graphics.getFontMetrics();
      for (int row = 0; row < rows.length(); row++) {
        int y = row * ROW_HEIGHT;
        graphics.setColor(row == 0 ? new Color(225, 232, 240) : (row % 2 == 0 ? Color.WHITE : new Color(247, 247, 247)));
        graphics.fillRect(0, y, width, ROW_HEIGHT);
        graphics.setColor(new Color(190, 190, 190));
        graphics.drawLine(0, y + ROW_HEIGHT - 1, width, y + ROW_HEIGHT - 1);
        JSONArray values = rows.getJSONArray(row);
        for (int column = 0; column < columns; column++) {
          int x = column * CELL_WIDTH;
          graphics.setColor(new Color(210, 210, 210));
          graphics.drawLine(x, y, x, y + ROW_HEIGHT);
          String value = column < values.length() ? values.optString(column, "") : "";
          graphics.setColor(Color.BLACK);
          graphics.drawString(clip(value, metrics, CELL_WIDTH - 10), x + 5, y + 16);
        }
      }
      graphics.setColor(new Color(210, 210, 210));
      graphics.drawRect(0, 0, width - 1, height - 1);
    } finally { graphics.dispose(); }
    ByteArrayOutputStream output = new ByteArrayOutputStream();
    ImageIO.write(image, "png", output);
    return output.toByteArray();
  }

  private static String clip(String value, FontMetrics metrics, int maxWidth) {
    if (metrics.stringWidth(value) <= maxWidth) return value;
    int end = value.length();
    while (end > 0 && metrics.stringWidth(value.substring(0, end) + "…") > maxWidth) end--;
    return value.substring(0, end) + "…";
  }
}
