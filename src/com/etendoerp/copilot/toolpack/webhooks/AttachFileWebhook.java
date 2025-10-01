package com.etendoerp.copilot.toolpack.webhooks;

import java.io.File;
import java.io.FileOutputStream;
import java.nio.file.Files;
import java.util.HashMap;
import java.util.Map;

import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;
import org.openbravo.base.weld.WeldUtils;
import org.openbravo.client.application.attachment.AttachImplementationManager;
import org.openbravo.dal.service.OBDal;

import com.etendoerp.webhookevents.services.BaseWebhookService;

/*
 * This class is used to attach a file to a record in Etendo.
 */
public class AttachFileWebhook extends BaseWebhookService {

  private static final Logger log = LogManager.getLogger();

  @Override
  public void get(Map<String, String> parameter, Map<String, String> responseVars) {
    log.info("Executing AttachmentWebHook process");

    String adTabId = parameter.get("ADTabId");
    String recordId = parameter.get("RecordId");
    String fileName = parameter.get("FileName");
    String fileContent = parameter.get("FileContent");

    if (adTabId == null || recordId == null || fileContent == null || fileName == null) {
      responseVars.put("error", "Missing required parameters");
      return;
    }

    try {
      File file = storeBase64ToTempFile(fileContent, fileName);
      createAttachment(adTabId, recordId, fileName, file);
      responseVars.put("message", "Attachment created successfully");
    } catch (Exception e) {
      log.error("Error creating attachment", e);
      responseVars.put("error", e.getMessage());
    }
  }

  public File storeBase64ToTempFile(String fileContent, String fileName) {
    if (fileContent == null || fileName == null) {
      return null;
    }
    File tempFile = null;
    try {
      tempFile = Files.createTempFile(null, fileName).toFile();
      try (FileOutputStream fos = new FileOutputStream(tempFile)) {
        byte[] fileBytes = java.util.Base64.getDecoder().decode(fileContent);
        fos.write(fileBytes);
      }
    } catch (Exception e) {
      log.error("Error storing base64 content to temp file", e);
      // Clean up the temp file if it was created but writing failed
      if (tempFile != null && tempFile.exists()) {
        try {
          Files.delete(tempFile.toPath());
        } catch (Exception deleteE) {
          log.error("Error deleting temp file", deleteE);
        }
      }
      tempFile = null;
    }
    return tempFile;
  }

  public void createAttachment(String adTabId, String recordId, String fileName, File file) {
    try {
      AttachImplementationManager aim = WeldUtils.getInstanceFromStaticBeanManager(
          AttachImplementationManager.class);
      aim.upload(new HashMap<>(), adTabId, recordId, fileName, file);
    } catch (Exception e) {
      OBDal.getInstance().rollbackAndClose();
      throw e;
    }
  }

}
