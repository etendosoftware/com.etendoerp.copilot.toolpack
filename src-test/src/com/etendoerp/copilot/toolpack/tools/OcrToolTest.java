package com.etendoerp.copilot.toolpack.tools;

import static org.junit.jupiter.api.Assertions.*;
import java.nio.file.Files;
import java.nio.file.Path;
import java.awt.image.BufferedImage;
import javax.imageio.ImageIO;
import org.codehaus.jettison.json.JSONObject;
import org.junit.jupiter.api.Test;
import com.etendoerp.copilot.util.OcrSchemaBuilder;

class OcrToolTest {
  @Test void exposesRequiredArguments() {
    assertEquals("OcrTool",new OcrTool().name());
    assertNotNull(new OcrTool().specification());
  }
  @Test void loadsNamedSchemaAndRejectsUnknownNames() throws Exception {
    JSONObject schema = OcrSchemaBuilder.loadSchema("testdocument");
    assertNotNull(schema);
    assertEquals("object", schema.getString("type"));
    assertEquals("string", schema.getJSONObject("properties").getJSONObject("document_id").getString("type"));
    assertEquals("document_id", schema.getJSONArray("required").getString(0));
    assertNull(OcrSchemaBuilder.loadSchema("invoice"));
  }
  @Test void missingReferenceUsesOrdinaryPrompt() {
    assertTrue(OcrTool.BASIC.contains("DO NOT SUMMARIZE"));
    assertTrue(OcrTool.REFERENCE_PROMPT.contains("reference image"));
  }
  @Test void rendersEachPdfPageAsJpegPayload() throws Exception {
    Path pdf=Files.createTempFile("ocr-pages-", ".pdf");
    try(org.apache.pdfbox.pdmodel.PDDocument doc=new org.apache.pdfbox.pdmodel.PDDocument()) {
      for(int i=0;i<2;i++){org.apache.pdfbox.pdmodel.PDPage page=new org.apache.pdfbox.pdmodel.PDPage();doc.addPage(page);} doc.save(pdf.toFile());
    }
    try { assertEquals(2,OcrTool.loadImages(pdf,"application/pdf",1.0).size()); } finally { Files.deleteIfExists(pdf); }
  }
  @Test void selectsFirstPageAsReferenceSearchInputAndHandlesImageTypes() throws Exception {
    Path image=Files.createTempFile("ocr-image-", ".png");
    try { ImageIO.write(new BufferedImage(2,2,BufferedImage.TYPE_INT_RGB),"png",image.toFile()); assertEquals("image/png",OcrTool.mime(image)); assertEquals(1,OcrTool.loadImages(image,"image/png",3).size()); } finally { Files.deleteIfExists(image); }
  }
}
