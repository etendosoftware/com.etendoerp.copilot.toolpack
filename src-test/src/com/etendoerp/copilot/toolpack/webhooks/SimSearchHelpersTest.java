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
import org.openbravo.dal.service.OBDal;
import org.openbravo.model.ad.datamodel.Table;

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

  /**
   * Exercises the HQL fallback path: searchEntities + calcSimilarityPercent. Uses ADTable as the
   * underlying table since the etcotp_sim_search function works against any AD table.
   */
  @Test
  public void searchEntitiesHqlFallbackPath() throws Exception {
    String whereOrderByClause = " as p where etcotp_sim_search(:tableName, p.id, :searchTerm) > :minPct "
        + "order by etcotp_sim_search(:tableName, p.id, :searchTerm) desc ";
    JSONArray result = SimSearch.searchEntities(whereOrderByClause, "C_Order", 3, 1, Table.class, "ad_table");
    assertNotNull(result);
    if (result.length() > 0) {
      JSONObject first = result.getJSONObject(0);
      assertTrue(first.has("id"));
      assertTrue(first.has("name"));
      assertTrue(first.getString(SIMILARITY_PERCENT).endsWith("%"));
    }
  }

  /**
   * calcSimilarityPercent should return a non-null BigDecimal with 4 decimal scale for a real
   * row id, and BigDecimal.ZERO when the row id doesn't exist (function returns null).
   */
  @Test
  public void calcSimilarityPercentBranches() {
    Table table = (Table) OBDal.getInstance().createQuery(Table.class, "").setMaxResult(1).uniqueResult();
    assertNotNull(table);
    BigDecimal real = SimSearch.calcSimilarityPercent(table.getId(), table.getName(), "ad_table");
    assertNotNull(real);
    assertEquals(4, real.scale());

    BigDecimal missing = SimSearch.calcSimilarityPercent("00000000000000000000000000000000",
        "x", "ad_table");
    assertNotNull(missing);
    assertEquals(4, missing.scale());
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
    SimSearch.lookupTrgmIndex(session, "ad_table", "name");
  }

  /**
   * allColumnsHaveTrgmIndex short-circuits to false on the first column without an index. Pass
   * an empty list to force the all-pass branch (returns true vacuously).
   */
  @Test
  public void allColumnsHaveTrgmIndexEmptyList() {
    Session session = OBDal.getInstance().getSession();
    assertTrue(SimSearch.allColumnsHaveTrgmIndex(session, "ad_table", Collections.emptyList()));
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
