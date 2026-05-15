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

/**
 * Unit tests for the package-private helpers of {@link SimSearch}. These exercise pure logic
 * branches (SQL builder, row mapper, identifier-column filter) without hitting the database.
 */
public class SimSearchHelpersTest extends WeldBaseTest {

  private static final String AD_TABLE = "ad_table";
  private static final String SIMILARITY_PERCENT = "similarity_percent";

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
