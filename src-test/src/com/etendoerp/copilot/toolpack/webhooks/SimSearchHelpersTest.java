/*
 *************************************************************************
 * The contents of this file are subject to the Etendo License
 * (the "License"), you may not use this file except in compliance with
 * the License.
 * You may obtain a copy of the License at
 * https://github.com/etendosoftware/etendo_core/blob/main/legal/Etendo_license.txt
 * Software distributed under the License is distributed on an
 * "AS IS" basis, WITHOUT WARRANTY OF ANY KIND, either express or
 * implied. See the License for the specific language governing rights
 * and limitations under the License.
 * All portions are Copyright © 2021–2026 FUTIT SERVICES, S.L
 * All Rights Reserved.
 * Contributor(s): Futit Services S.L.
 *************************************************************************
 */
package com.etendoerp.copilot.toolpack.webhooks;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertTrue;

import java.math.BigDecimal;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;

import org.codehaus.jettison.json.JSONArray;
import org.codehaus.jettison.json.JSONObject;
import org.hibernate.Session;
import org.junit.Test;
import org.openbravo.base.model.Entity;
import org.openbravo.base.model.ModelProvider;
import org.openbravo.base.weld.test.WeldBaseTest;
import org.openbravo.dal.core.OBContext;
import org.openbravo.dal.service.OBDal;
import org.openbravo.model.ad.datamodel.Table;
import org.openbravo.test.base.TestConstants;

/**
 * Unit tests for the package-private helpers of {@link SimSearch}. These exercise pure logic
 * branches (SQL builder, row mapper, identifier-column filter) without hitting the database.
 */
public class SimSearchHelpersTest extends WeldBaseTest {

  private static final String AD_TABLE = "ad_table";
  private static final String SIMILARITY_PERCENT = "similarity_percent";
  private static final String TEXT_SIMILARITY_PERCENT = "text_similarity_percent";
  private static final String EXACT_MATCH = "exact_match";
  private static final String FULL_PERCENT = "100.0000%";
  private static final String MATCH_TYPE = "match_type";
  private static final String C_ORDER = "C_Order";
  private static final String METER = "Meter";

  /**
   * Covers all flag combinations of buildIndexedSql: single/multi column, client/org enabled
   * or not, and operator predicates on/off.
   */
  @Test
  public void buildIndexedSqlBranches() {
    String sqlAll = SimSearch.buildIndexedSql(AD_TABLE, "ad_table_id",
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

    String sqlClientOnly = SimSearch.buildIndexedSql(AD_TABLE, "ad_table_id",
        Arrays.asList("name"), true, false, false);
    assertTrue(sqlClientOnly.contains("ad_client_id in (:clients)"));
    assertFalse(sqlClientOnly.contains("ad_org_id"));
  }

  /**
   * Indexed path against real AD_TABLE rows: the name equal to the term comes first as "exact",
   * and every name that merely contains it ("C_OrderLine", "C_OrderTax"...) follows as "fuzzy"
   * with its trigram score untouched, so callers' similarity thresholds keep their meaning.
   */
  @Test
  public void indexedSearchRanksExactNameFirstAndLabelsTheRestFuzzy() throws Exception {
    JSONArray result = searchAdTable(C_ORDER);

    JSONObject first = result.getJSONObject(0);
    assertEquals(C_ORDER, first.getString("name"));
    assertEquals(FULL_PERCENT, first.getString(SIMILARITY_PERCENT));
    assertTrue(first.getBoolean(EXACT_MATCH));
    assertEquals(SimSearch.MATCH_EXACT, first.getString(MATCH_TYPE));
    assertTrue("the term must also match names that contain it", result.length() > 1);
    for (int i = 1; i < result.length(); i++) {
      JSONObject other = result.getJSONObject(i);
      assertFalse(other.getBoolean(EXACT_MATCH));
      assertEquals(other.getString("name"), SimSearch.MATCH_FUZZY, other.getString(MATCH_TYPE));
    }
  }

  /** Case and surrounding/inner whitespace in the term do not break the exact match. */
  @Test
  public void indexedSearchExactMatchIgnoresCaseAndWhitespace() throws Exception {
    JSONObject first = searchAdTable("\t c_ORDER  ").getJSONObject(0);
    assertEquals(C_ORDER, first.getString("name"));
    assertEquals(SimSearch.MATCH_EXACT, first.getString(MATCH_TYPE));
  }

  /** A term that differs only by accents still ranks the record first, labelled "normalized". */
  @Test
  public void indexedSearchLabelsAccentOnlyDifferenceNormalized() throws Exception {
    JSONObject first = searchAdTable("C_Ordér").getJSONObject(0);
    assertEquals(C_ORDER, first.getString("name"));
    assertFalse(first.getBoolean(EXACT_MATCH));
    assertEquals(SimSearch.MATCH_NORMALIZED, first.getString(MATCH_TYPE));
  }

  /** The Java twin used by the non-indexed path classifies like the SQL one. */
  @Test
  public void matchTypeClassifiesExactNormalizedAndFuzzy() {
    assertEquals(SimSearch.MATCH_EXACT, SimSearch.matchType(METER, "\t meter "));
    assertEquals(SimSearch.MATCH_EXACT, SimSearch.matchType("IVA  Normal", "iva normal"));
    assertEquals(SimSearch.MATCH_NORMALIZED, SimSearch.matchType("Arnés Ç", "ARNES c"));
    assertEquals(SimSearch.MATCH_FUZZY, SimSearch.matchType(METER, "Meters"));
    assertEquals(SimSearch.MATCH_FUZZY, SimSearch.matchType("Cubic Meter", METER));
    // ñ is a different letter, not an accented n
    assertEquals(SimSearch.MATCH_FUZZY, SimSearch.matchType("Año", "Ano"));
  }

  private static JSONArray searchAdTable(String term) throws Exception {
    OBContext.setOBContext(TestConstants.Users.ADMIN, TestConstants.Roles.SYS_ADMIN,
        TestConstants.Clients.SYSTEM, TestConstants.Orgs.MAIN);
    Entity entity = ModelProvider.getInstance().getEntity("ADTable");
    JSONArray result = SimSearch.searchEntitiesIndexed(entity, SimSearch.identifierColumns(entity), term, 10, 0);
    assertTrue(result.length() > 0);
    return result;
  }

  /**
   * mapIndexedRows adds text_similarity_percent, exact_match and match_type only when the row
   * carries the extra columns, so a caller that still builds three-column rows gets the original
   * shape.
   */
  @Test
  public void mapIndexedRowsAddsTextSimilarityExactMatchAndMatchType() throws Exception {
    List<Object[]> rows = Arrays.asList(
        new Object[] { "id1", METER, new BigDecimal("100"), new BigDecimal("100"), Boolean.TRUE, 2 },
        new Object[] { "id2", "Cubic Meter", new BigDecimal("100"), "50.0", "f", 0 },
        new Object[] { "id3", "Arnes", new BigDecimal("80"), "80.0", "f", "1" },
        new Object[] { "id4", "Legacy", new BigDecimal("42.5") });

    JSONArray result = SimSearch.mapIndexedRows(rows);

    JSONObject exact = result.getJSONObject(0);
    assertEquals(FULL_PERCENT, exact.getString(SIMILARITY_PERCENT));
    assertEquals(FULL_PERCENT, exact.getString(TEXT_SIMILARITY_PERCENT));
    assertTrue(exact.getBoolean(EXACT_MATCH));
    assertEquals(SimSearch.MATCH_EXACT, exact.getString(MATCH_TYPE));

    JSONObject contained = result.getJSONObject(1);
    assertEquals(FULL_PERCENT, contained.getString(SIMILARITY_PERCENT));
    assertEquals("50.0000%", contained.getString(TEXT_SIMILARITY_PERCENT));
    assertFalse(contained.getBoolean(EXACT_MATCH));
    assertEquals(SimSearch.MATCH_FUZZY, contained.getString(MATCH_TYPE));

    assertEquals(SimSearch.MATCH_NORMALIZED, result.getJSONObject(2).getString(MATCH_TYPE));

    JSONObject legacy = result.getJSONObject(3);
    assertFalse(legacy.has(TEXT_SIMILARITY_PERCENT));
    assertFalse(legacy.has(EXACT_MATCH));
    assertFalse(legacy.has(MATCH_TYPE));
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
    Entity entity = ModelProvider.getInstance().getEntity("ADTable");
    List<String> cols = SimSearch.identifierColumns(entity);
    assertNotNull(cols);
    assertFalse(cols.isEmpty());
    for (String c : cols) {
      assertEquals(c, c.toLowerCase());
    }
  }

  /**
   * calcSimilarityPercent should return a non-null BigDecimal with 4 decimal scale for a real
   * row id and for a missing one (the function returns 0/null which the code maps to ZERO).
   */
  @Test
  public void calcSimilarityPercentBranches() {
    OBContext.setAdminMode(true);
    try {
      Table table = (Table) OBDal.getInstance().createQuery(Table.class, "").setMaxResult(1).uniqueResult();
      assertNotNull(table);
      BigDecimal real = SimSearch.calcSimilarityPercent(table.getId(), table.getName(), AD_TABLE);
      assertNotNull(real);
      assertEquals(4, real.scale());

      BigDecimal missing = SimSearch.calcSimilarityPercent("00000000000000000000000000000000",
          "x", AD_TABLE);
      assertNotNull(missing);
      assertEquals(4, missing.scale());
    } finally {
      OBContext.restorePreviousMode();
    }
  }

  /**
   * Exercises applyTrgmThresholds — sets the pg_trgm thresholds on the current session.
   */
  @Test
  public void applyTrgmThresholdsRuns() {
    Session session = OBDal.getInstance().getSession();
    SimSearch.applyTrgmThresholds(session, 50);
  }

  /**
   * lookupTrgmIndex must execute the pg_indexes lookup and return a Boolean without crashing,
   * regardless of whether the index actually exists in the test DB.
   */
  @Test
  public void lookupTrgmIndexRuns() {
    Session session = OBDal.getInstance().getSession();
    SimSearch.lookupTrgmIndex(session, AD_TABLE, "name");
  }

  /**
   * allColumnsHaveTrgmIndex short-circuits to false on the first column without an index. Pass
   * an empty list to force the all-pass branch (returns true vacuously).
   */
  @Test
  public void allColumnsHaveTrgmIndexEmptyList() {
    Session session = OBDal.getInstance().getSession();
    assertTrue(SimSearch.allColumnsHaveTrgmIndex(session, AD_TABLE, Collections.emptyList()));
  }

  /**
   * searchEntitiesIndexed must short-circuit to an empty JSONArray when the table name fails the
   * SAFE_IDENTIFIER whitelist (line 235-237 branch).
   */
  @Test
  public void searchEntitiesIndexedRejectsUnsafeTableName() throws Exception {
    Entity entity = new Entity();
    entity.setTableName("bad-name; drop table");
    JSONArray empty = SimSearch.searchEntitiesIndexed(entity, Arrays.asList("name"), "x", 1, 30);
    assertNotNull(empty);
    assertEquals(0, empty.length());
  }
}
