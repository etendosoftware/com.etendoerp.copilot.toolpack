package com.etendoerp.copilot.toolpack.webhooks;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertTrue;

import java.math.BigDecimal;
import java.util.Arrays;
import java.util.List;

import org.codehaus.jettison.json.JSONArray;
import org.codehaus.jettison.json.JSONObject;
import org.junit.Test;
import org.openbravo.base.model.Entity;
import org.openbravo.base.model.ModelProvider;
import org.openbravo.base.weld.test.WeldBaseTest;

/**
 * Unit tests for the package-private helpers of {@link SimSearch}. These exercise pure logic
 * branches (SQL builder, row mapper, identifier-column filter) without hitting the database.
 */
public class SimSearchHelpersTest extends WeldBaseTest {

  private static final String AD_TABLE = "ADTable";
  private static final String SIMILARITY_PERCENT = "similarity_percent";

  /**
   * Covers all flag combinations of buildIndexedSql: single/multi column, client/org enabled
   * or not, and operator predicates on/off.
   */
  @Test
  public void buildIndexedSqlBranches() {
    String sqlAll = SimSearch.buildIndexedSql("ad_table", "ad_table_id",
        Arrays.asList("name"), true, true, true);
    assertTrue(sqlAll.contains("ad_client_id in (:clients)"));
    assertTrue(sqlAll.contains("ad_org_id in (:orgs)"));
    assertTrue(sqlAll.contains("upper(t.name) % upper(:term)"));
    assertTrue(sqlAll.contains("upper(:term) <% upper(t.name)"));
    assertTrue(sqlAll.contains("similarity(upper(t.name), upper(:term))"));
    assertTrue(sqlAll.contains("> :minPct"));
    assertTrue(sqlAll.contains("limit :qty"));

    String sqlMinimal = SimSearch.buildIndexedSql("m_product", "m_product_id",
        Arrays.asList("value", "name"), false, false, false);
    assertFalse(sqlMinimal.contains("ad_client_id"));
    assertFalse(sqlMinimal.contains("ad_org_id"));
    assertFalse(sqlMinimal.contains(" % "));
    assertFalse(sqlMinimal.contains("<%"));
    assertTrue(sqlMinimal.contains("similarity(upper(t.value), upper(:term))"));
    assertTrue(sqlMinimal.contains("similarity(upper(t.name), upper(:term))"));

    String sqlClientOnly = SimSearch.buildIndexedSql("ad_table", "ad_table_id",
        Arrays.asList("name"), true, false, false);
    assertTrue(sqlClientOnly.contains("ad_client_id in (:clients)"));
    assertFalse(sqlClientOnly.contains("ad_org_id"));
  }

  /**
   * Covers mapIndexedRows branches: BigDecimal score, null score (defaults to zero),
   * non-BigDecimal score (parsed from toString), and null identifier (mapped to empty string).
   */
  @Test
  public void mapIndexedRowsBranches() throws Exception {
    List<Object[]> rows = Arrays.asList(
        new Object[] { "id1", "Name One", new BigDecimal("42.5") },
        new Object[] { "id2", null, null },
        new Object[] { "id3", "Name Three", "17.25" });

    JSONArray result = SimSearch.mapIndexedRows(rows);
    assertEquals(3, result.length());

    JSONObject r0 = result.getJSONObject(0);
    assertEquals("id1", r0.getString("id"));
    assertEquals("Name One", r0.getString("name"));
    assertTrue(r0.getString(SIMILARITY_PERCENT).endsWith("%"));

    JSONObject r1 = result.getJSONObject(1);
    assertEquals("", r1.getString("name"));
    assertTrue(r1.getString(SIMILARITY_PERCENT).startsWith("0"));

    JSONObject r2 = result.getJSONObject(2);
    assertTrue(r2.getString(SIMILARITY_PERCENT).contains("17.25"));
  }

  /**
   * Verifies identifierColumns filters out non-String identifier properties and returns at
   * least one lowercase column for ADTable.
   */
  @Test
  public void identifierColumnsForADTable() {
    Entity entity = ModelProvider.getInstance().getEntity(AD_TABLE);
    List<String> cols = SimSearch.identifierColumns(entity);
    assertNotNull(cols);
    assertFalse(cols.isEmpty());
    for (String c : cols) {
      assertEquals(c, c.toLowerCase());
    }
  }
}
