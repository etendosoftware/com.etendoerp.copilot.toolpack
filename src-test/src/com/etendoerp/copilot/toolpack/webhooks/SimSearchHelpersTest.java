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
import static org.junit.Assert.assertTrue;

import java.math.BigDecimal;
import java.util.Arrays;
import java.util.Collections;

import org.codehaus.jettison.json.JSONArray;
import org.codehaus.jettison.json.JSONObject;
import org.junit.Test;

/**
 * Unit tests for the package-private helpers of {@link SimSearch}. They exercise pure logic (SQL
 * builder and row mapper) and need no database.
 *
 * @covers com.etendoerp.copilot.toolpack.webhooks.SimSearch
 */
public class SimSearchHelpersTest {

  private static final String AD_TABLE = "ad_table";
  private static final String AD_TABLE_ID = "ad_table_id";
  private static final String NAME = "name";
  private static final String SIMILARITY_PERCENT = "similarity_percent";
  private static final String TEXT_SIMILARITY_PERCENT = "text_similarity_percent";
  private static final String EXACT_MATCH = "exact_match";
  private static final String FULL_PERCENT = "100.0000%";
  private static final String HALF_PERCENT = "50.0000%";
  private static final String TIE_BREAK_ORDER = "order by score desc, text_score desc, t."
      + AD_TABLE_ID + " asc";

  /**
   * The indexed query must report whole-string similarity and exact equality next to the score
   * and break ties by text_score then primary key, for any identifier shape and operator mode.
   */
  @Test
  public void buildIndexedSqlReportsTextSimilarityAndBreaksTies() {
    String single = SimSearch.buildIndexedSql(AD_TABLE, AD_TABLE_ID, Collections.singletonList(NAME),
        true, true, true);
    assertTrue(single.contains(" as exact_match"));
    assertTrue(single.contains(" as text_score"));
    assertTrue(single.contains("upper(t.name) = upper(:term)"));
    assertTrue(single.contains(TIE_BREAK_ORDER));

    String multi = SimSearch.buildIndexedSql("m_product", "m_product_id",
        Arrays.asList("value", NAME), false, false, false);
    assertTrue(multi.contains(" as exact_match"));
    assertTrue(multi.contains(" as text_score"));
    assertTrue(multi.contains("upper(t.value) = upper(:term) or upper(t.name) = upper(:term)"));
    assertTrue(multi.contains("order by score desc, text_score desc, t.m_product_id asc"));
  }

  /**
   * A five-column row exposes text_similarity_percent (4 decimals, % suffix) and a boolean
   * exact_match; a legacy three-column row keeps the original shape without either field.
   */
  @Test
  public void mapIndexedRowsAddsTextSimilarityAndExactMatch() throws Exception {
    JSONArray result = SimSearch.mapIndexedRows(Arrays.asList(
        new Object[] { "id1", "ACME", new BigDecimal("100"), new BigDecimal("100"), Boolean.TRUE },
        new Object[] { "id2", "ACME INC", new BigDecimal("100"), new BigDecimal("50"),
            Boolean.FALSE },
        new Object[] { "id3", "Legacy", new BigDecimal("42.5") }));

    JSONObject exact = result.getJSONObject(0);
    assertEquals(FULL_PERCENT, exact.getString(SIMILARITY_PERCENT));
    assertEquals(FULL_PERCENT, exact.getString(TEXT_SIMILARITY_PERCENT));
    assertTrue(exact.getBoolean(EXACT_MATCH));

    JSONObject contained = result.getJSONObject(1);
    assertEquals(FULL_PERCENT, contained.getString(SIMILARITY_PERCENT));
    assertEquals(HALF_PERCENT, contained.getString(TEXT_SIMILARITY_PERCENT));
    assertFalse(contained.getBoolean(EXACT_MATCH));

    JSONObject legacy = result.getJSONObject(2);
    assertEquals("42.5000%", legacy.getString(SIMILARITY_PERCENT));
    assertFalse(legacy.has(TEXT_SIMILARITY_PERCENT));
    assertFalse(legacy.has(EXACT_MATCH));
  }
}
