package com.etendoerp.copilot.toolpack.tools;

import static org.junit.Assert.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import org.junit.Test;

public class GoogleServiceUtilTest {

  @Test
  public void extractsSpreadsheetIdFromStandardGoogleUrl() {
    assertEquals("sheet_123-abc", GoogleServiceUtil.extractSheetIdFromUrl(
        "https://docs.google.com/spreadsheets/d/sheet_123-abc/edit#gid=0"));
  }

  @Test
  public void rejectsUrlsWithoutSpreadsheetId() {
    IllegalArgumentException error = assertThrows(IllegalArgumentException.class,
        () -> GoogleServiceUtil.extractSheetIdFromUrl("https://drive.google.com/file/d/not-a-sheet"));
    assertEquals("Invalid URL. Couldn't extract spreadsheet ID.", error.getMessage());
  }
}
