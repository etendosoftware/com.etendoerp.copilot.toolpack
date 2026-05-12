package com.etendoerp.copilot.toolpack.webhooks;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.sql.Statement;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;
import java.util.regex.Pattern;

import org.apache.commons.lang3.StringUtils;
import org.codehaus.jettison.json.JSONArray;
import org.codehaus.jettison.json.JSONException;
import org.codehaus.jettison.json.JSONObject;
import org.hibernate.Session;
import org.hibernate.query.NativeQuery;
import org.openbravo.base.model.Entity;
import org.openbravo.base.model.Property;
import org.openbravo.base.structure.BaseOBObject;
import org.openbravo.dal.core.OBContext;
import org.openbravo.dal.service.OBDal;
import org.openbravo.dal.service.OBQuery;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import com.etendoerp.webhookevents.services.BaseWebhookService;
import com.smf.securewebservices.utils.WSResult;
import com.smf.securewebservices.utils.WSResult.Status;

/**
 * Webhook service for performing similarity searches.
 * similarity search requests based on provided parameters.
 */
public class SimSearch extends BaseWebhookService {

  private static final Logger LOG = LoggerFactory.getLogger(SimSearch.class);
  private static final String MESSAGE = "message";
  public static final int MIN_SIM_PERCENT = 30;

  /** Cached per (lowercased table . column) — whether a trigram index exists on the column. */
  private static final ConcurrentMap<String, Boolean> TRGM_INDEX_CACHE = new ConcurrentHashMap<>();

  /** SQL identifier whitelist — only used for table/column names that come from entity metadata. */
  private static final Pattern SAFE_IDENTIFIER = Pattern.compile("^[a-z_][a-z0-9_]*$");

  /**
   * Handles the GET request for the webhook.
   * This method retrieves an array of items and entity name from the parameters,
   * performs a similarity search, and constructs a JSON response with the results.
   *
   * @param parameter
   *     A map of request parameters.
   * @param responseVars
   *     A map to store the response variables.
   */
  @Override
  public void get(Map<String, String> parameter, Map<String, String> responseVars) {
    LOG.debug("Executing WebHook: SimilaritySearch");
    for (Map.Entry<String, String> entry : parameter.entrySet()) {
      LOG.debug("Parameter: {} = {}", entry.getKey(), entry.getValue());
    }

    String itemsJson = parameter.get("items");
    String entityName = parameter.get("entityName");

    if (StringUtils.isEmpty(itemsJson) || StringUtils.isEmpty(entityName)) {
      responseVars.put("error", "Missing required parameters");
      return;
    }

    String qtyResultsStr = parameter.getOrDefault("qtyResults", "1");
    if (qtyResultsStr == null || qtyResultsStr.equalsIgnoreCase("null") || qtyResultsStr.isEmpty()) {
      qtyResultsStr = "1";
    }
    int qtyResults = Integer.parseInt(qtyResultsStr);

    String minSimilarityPercent = parameter.getOrDefault("minSimPercent", String.valueOf(MIN_SIM_PERCENT));
    if (minSimilarityPercent == null || minSimilarityPercent.equalsIgnoreCase("null") || minSimilarityPercent.isEmpty()) {
      minSimilarityPercent = "30";
    }

    try {
      JSONArray itemsArray = new JSONArray(itemsJson);
      JSONObject results = new JSONObject();

      for (int i = 0; i < itemsArray.length(); i++) {
        String searchTerm = itemsArray.getString(i);
        searchTerm = searchTerm.replace("'", "");
        String label = "item_" + i;

        if (StringUtils.isNotBlank(searchTerm)) {
          WSResult result = handleSimSearch(searchTerm, entityName, qtyResults, minSimilarityPercent);
          results.put(label, result.getJSONResponse());
        }
      }

      responseVars.put(MESSAGE, results.toString());
    } catch (Exception e) {
      LOG.error("Error processing SimSearch batch", e);
      responseVars.put("error", e.getMessage());
    }
  }

  /**
   * Handles the similarity search based on the provided request parameters.
   *
   * @param searchTerm
   *     Term to search.
   * @param entityName
   *     Name of the entity to search.
   * @param qtyResults
   *     Max amount of results, by default 1.
   * @param minSimilarityPercent
   *     Minimum similarity percent, by default 30%.
   * @return A WSResult object containing the search results.
   * @throws JSONException
   *     If an error occurs while processing JSON data.
   * @throws ClassNotFoundException
   *     If the entity class is not found.
   */
  public static WSResult handleSimSearch(String searchTerm, String entityName, int qtyResults, String minSimilarityPercent) throws JSONException, ClassNotFoundException {
    WSResult wsResult = new WSResult();
    Set<Entity> readableEntities = OBContext.getOBContext().getEntityAccessChecker().getReadableEntities();
    Entity entity = readableEntities.stream().filter(e -> e.getName().equals(entityName)).findFirst().orElse(
        null);
    if (entity == null) {
      wsResult.setStatus(Status.UNPROCESSABLE_ENTITY);
      wsResult.setMessage("Entity not found or not readable");
      return wsResult;
    }
    int minPct = Integer.parseInt(minSimilarityPercent);
    JSONArray arrayResponse;
    List<String> idColumns = identifierColumns(entity);
    if (!idColumns.isEmpty()) {
      arrayResponse = searchEntitiesIndexed(entity, idColumns, searchTerm, qtyResults, minPct);
    } else {
      Class<? extends BaseOBObject> entityClass = Class.forName(entity.getClassName()).asSubclass(BaseOBObject.class);
      String whereOrderByClause = " as p where etcotp_sim_search(:tableName, p.id, :searchTerm) > :minPct "
          + "order by etcotp_sim_search(:tableName, p.id, :searchTerm) desc ";
      arrayResponse = searchEntities(whereOrderByClause, searchTerm, qtyResults, minPct, entityClass,
          entity.getTableName());
    }
    wsResult.setStatus(Status.OK);
    wsResult.setData(arrayResponse);
    return wsResult;
  }

  /**
   * Searches for entities that are similar to the provided search term.
   *
   * @param <T>
   *     The type of the entity to be searched. It must be a subclass of BaseOBObject.
   * @param whereOrderByClause2
   *     The where clause for the search query.
   * @param searchTerm
   *     The search term to be used in the similarity search.
   * @param qtyResults
   *     The maximum number of results to be returned by the search.
   * @param entityClass
   *     The class of the entity to be searched.
   * @param tableName
   *     The name of the table where the entity belongs.
   * @return A JSONArray of JSONObjects, each representing a search result.
   * @throws JSONException
   *     If an error occurs while processing the JSON data.
   */
  private static <T extends BaseOBObject> JSONArray searchEntities(String whereOrderByClause2,
      String searchTerm, int qtyResults, int minPct, Class<T> entityClass, String tableName) throws JSONException {

    OBQuery<T> searchQuery = OBDal.getInstance().createQuery(entityClass, whereOrderByClause2);

    searchQuery.setNamedParameter("tableName", StringUtils.lowerCase(tableName));
    searchQuery.setNamedParameter("searchTerm", searchTerm);
    searchQuery.setNamedParameter("minPct", minPct);
    searchQuery.setMaxResult(qtyResults);
    var resultList = searchQuery.list();
    JSONArray arrayResponse = new JSONArray();
    for (BaseOBObject resultOBJ : resultList) {
      JSONObject searchResultJson = new JSONObject();
      searchResultJson.put("id", resultOBJ.getId());
      searchResultJson.put("name", resultOBJ.getIdentifier());
      BigDecimal percent = calcSimilarityPercent((String) resultOBJ.getId(), searchTerm, tableName);
      searchResultJson.put("similarity_percent", percent.toString() + "%");
      arrayResponse.put(searchResultJson);
    }
    return arrayResponse;
  }

  /**
   * Returns the lowercased physical column names of the entity's identifier properties that
   * are String primitives. Non-string components (dates, numerics, references) are skipped —
   * they aren't useful for trigram similarity. Returns empty only when the identifier has no
   * String component at all, in which case the caller falls back to the etcotp_sim_search
   * HQL path.
   */
  private static List<String> identifierColumns(Entity entity) {
    List<Property> idProps = entity.getIdentifierProperties();
    if (idProps == null || idProps.isEmpty()) {
      return Collections.emptyList();
    }
    List<String> cols = new ArrayList<>(idProps.size());
    for (Property idProp : idProps) {
      if (idProp.getColumnName() == null || !idProp.isPrimitive()
          || idProp.getPrimitiveObjectType() != String.class) {
        continue;
      }
      String col = StringUtils.lowerCase(idProp.getColumnName());
      if (SAFE_IDENTIFIER.matcher(col).matches()) {
        cols.add(col);
      }
    }
    return cols;
  }

  /**
   * Similarity search against an entity's identifier columns. When every identifier column has
   * a pg_trgm GIN/GiST index, the query uses the % and &lt;% operators with pg_trgm session
   * thresholds so the planner picks a bitmap index plan. Otherwise the operator predicates
   * and SET LOCAL are dropped and PG runs a seq scan with only the precise
   * GREATEST(similarity, word_similarity) &gt; :minPct post-filter. Either path avoids the
   * per-row ad_column_identifier_std subquery used by etcotp_sim_search, which is the main
   * cost; the index just turns linear scaling into sublinear when present.
   */
  private static JSONArray searchEntitiesIndexed(Entity entity, List<String> idColumns, String searchTerm,
      int qtyResults, int minSimPercent) throws JSONException {
    Session session = OBDal.getInstance().getSession();
    String tableName = StringUtils.lowerCase(entity.getTableName());
    String pkColumn = tableName + "_id";
    if (!SAFE_IDENTIFIER.matcher(tableName).matches() || !SAFE_IDENTIFIER.matcher(pkColumn).matches()) {
      return new JSONArray();
    }
    boolean useOperators = allColumnsHaveTrgmIndex(session, tableName, idColumns);
    if (useOperators) {
      applyTrgmThresholds(session, minSimPercent);
    }
    String sql = buildIndexedSql(tableName, pkColumn, idColumns, entity.isClientEnabled(),
        entity.isOrganizationEnabled(), useOperators);
    NativeQuery<Object[]> query = bindIndexedParameters(session, sql, tableName, searchTerm,
        entity.isClientEnabled(), entity.isOrganizationEnabled(), minSimPercent, qtyResults);
    return mapIndexedRows(query.list());
  }

  private static void applyTrgmThresholds(Session session, int minSimPercent) {
    double opThreshold = Math.max(minSimPercent / 100.0, 0.30);
    String opThresholdStr = String.format(Locale.US, "%.4f", opThreshold);
    session.doWork(conn -> {
      try (Statement st = conn.createStatement()) {
        st.execute("SET LOCAL pg_trgm.similarity_threshold = " + opThresholdStr);
        st.execute("SET LOCAL pg_trgm.word_similarity_threshold = " + opThresholdStr);
      }
    });
  }

  private static String buildIndexedSql(String tableName, String pkColumn, List<String> idColumns,
      boolean hasClient, boolean hasOrg, boolean useOperators) {
    List<String> scoreParts = new ArrayList<>(idColumns.size() * 2);
    List<String> opPreds = new ArrayList<>(idColumns.size() * 2);
    for (String col : idColumns) {
      scoreParts.add("similarity(upper(t." + col + "), upper(:term))");
      scoreParts.add("word_similarity(upper(:term), upper(t." + col + "))");
      opPreds.add("upper(t." + col + ") % upper(:term)");
      opPreds.add("upper(:term) <% upper(t." + col + ")");
    }
    String scoreExpr = "greatest(" + String.join(", ", scoreParts) + ") * 100";

    StringBuilder sql = new StringBuilder()
        .append("select t.").append(pkColumn).append(", ")
        .append("ad_column_identifier_std(:tn, t.").append(pkColumn).append(") as identifier, ")
        .append("cast(").append(scoreExpr).append(" as numeric) as score ")
        .append("from ").append(tableName).append(" t where ");
    if (hasClient) {
      sql.append("t.ad_client_id in (:clients) and ");
    }
    if (hasOrg) {
      sql.append("t.ad_org_id in (:orgs) and ");
    }
    if (useOperators) {
      sql.append("(").append(String.join(" or ", opPreds)).append(") and ");
    }
    sql.append(scoreExpr).append(" > :minPct ")
        .append("order by score desc limit :qty");
    return sql.toString();
  }

  @SuppressWarnings("unchecked")
  private static NativeQuery<Object[]> bindIndexedParameters(Session session, String sql, String tableName,
      String searchTerm, boolean hasClient, boolean hasOrg, int minSimPercent, int qtyResults) {
    NativeQuery<Object[]> query = session.createNativeQuery(sql);
    query.setParameter("tn", tableName);
    query.setParameter("term", searchTerm);
    if (hasClient) {
      query.setParameterList("clients", Arrays.asList(OBContext.getOBContext().getReadableClients()));
    }
    if (hasOrg) {
      query.setParameterList("orgs", Arrays.asList(OBContext.getOBContext().getReadableOrganizations()));
    }
    query.setParameter("minPct", minSimPercent);
    query.setParameter("qty", qtyResults);
    return query;
  }

  private static JSONArray mapIndexedRows(List<Object[]> rows) throws JSONException {
    JSONArray arrayResponse = new JSONArray();
    for (Object[] row : rows) {
      JSONObject json = new JSONObject();
      json.put("id", row[0]);
      Object nameVal = row[1];
      json.put("name", nameVal == null ? "" : nameVal.toString());
      BigDecimal score = (row[2] instanceof BigDecimal)
          ? (BigDecimal) row[2]
          : new BigDecimal(row[2].toString());
      json.put("similarity_percent", score.setScale(4, RoundingMode.HALF_UP).toString() + "%");
      arrayResponse.put(json);
    }
    return arrayResponse;
  }

  /**
   * Returns true only when every column has a pg_trgm index whose definition references the
   * column name. Index presence is cached in-process; restart the JVM (or invalidate the cache)
   * after creating or dropping indexes for the new state to be picked up.
   */
  private static boolean allColumnsHaveTrgmIndex(Session session, String tableName, List<String> columns) {
    for (String col : columns) {
      String key = tableName + "." + col;
      Boolean cached = TRGM_INDEX_CACHE.get(key);
      if (cached == null) {
        cached = lookupTrgmIndex(session, tableName, col);
        TRGM_INDEX_CACHE.put(key, cached);
      }
      if (!cached) {
        return false;
      }
    }
    return true;
  }

  private static boolean lookupTrgmIndex(Session session, String tableName, String column) {
    String sql = "select 1 from pg_indexes "
        + "where schemaname = current_schema() "
        + "  and lower(tablename) = :tn "
        + "  and indexdef ilike :trgmPat "
        + "  and indexdef ilike :colPat "
        + "limit 1";
    NativeQuery<?> q = session.createNativeQuery(sql);
    q.setParameter("tn", StringUtils.lowerCase(tableName));
    q.setParameter("trgmPat", "%trgm_ops%");
    q.setParameter("colPat", "%(" + StringUtils.lowerCase(column) + ")%");
    return !q.getResultList().isEmpty();
  }

  private static BigDecimal calcSimilarityPercent(String id, String searchTerm, String tableName) {
    @SuppressWarnings("unchecked")
    NativeQuery<BigDecimal> query = OBDal.getInstance().getSession()
        .createNativeQuery("select etcotp_sim_search(:tn, :rid, :term)");
    query.setParameter("tn", StringUtils.lowerCase(tableName));
    query.setParameter("rid", id);
    query.setParameter("term", searchTerm);
    BigDecimal percent = query.uniqueResult();
    return percent.setScale(4, RoundingMode.HALF_UP);
  }

}
