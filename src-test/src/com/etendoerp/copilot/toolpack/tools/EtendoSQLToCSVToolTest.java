package com.etendoerp.copilot.toolpack.tools;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public class EtendoSQLToCSVToolTest {

  @Test
  public void acceptsSelectQuery() {
    assertTrue(EtendoSQLToCSVTool.validateSqlQuery("SELECT u.name FROM ad_user u"));
  }

  @Test
  public void rejectsNonSelectStatements() {
    assertFalse(EtendoSQLToCSVTool.validateSqlQuery("UPDATE ad_user u SET name = 'x'"));
    assertFalse(EtendoSQLToCSVTool.validateSqlQuery("select 1; delete from ad_user"));
  }

  @Test
  public void rejectsDangerousKeywordsEvenInsideOtherSqlTextLikePythonValidation() {
    assertFalse(EtendoSQLToCSVTool.validateSqlQuery("SELECT updated FROM ad_user u"));
  }
}
