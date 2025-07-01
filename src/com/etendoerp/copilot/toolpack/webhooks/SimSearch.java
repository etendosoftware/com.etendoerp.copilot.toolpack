package com.etendoerp.copilot.toolpack.webhooks;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.Map;
import java.util.Set;

import org.apache.commons.lang3.StringUtils;
import org.codehaus.jettison.json.JSONArray;
import org.codehaus.jettison.json.JSONException;
import org.codehaus.jettison.json.JSONObject;
import org.hibernate.ScrollMode;
import org.hibernate.ScrollableResults;
import org.hibernate.query.Query;
import org.openbravo.base.model.Entity;
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

  /**
   * Handles the GET request for the webhook.
   * This method retrieves the search term and entity name from the parameters,
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

    String searchTerm = parameter.get("searchTerm");
    String entityName = parameter.get("entityName");

    if (StringUtils.isEmpty(searchTerm) || StringUtils.isEmpty(entityName)) {
      responseVars.put("error", "Missing required parameters");
      return;
    }
    WSResult result = null;
    String responseText = "";
    try {
      result = handleSimSearch(parameter);
      responseText = result.getJSONResponse().toString(4);
    } catch (Exception e) {
      LOG.error("Error executing process", e);
      responseVars.put("error", e.getMessage());
    }

    responseVars.put(MESSAGE, responseText);
  }

  /**
   * Handles the similarity search based on the provided request parameters.
   *
   * @param requestParams
   *     A map of request parameters.
   * @return A WSResult object containing the search results.
   * @throws JSONException
   *     If an error occurs while processing JSON data.
   * @throws NoSuchFieldException
   *     If a field is not found.
   * @throws IllegalAccessException
   *     If access to a field is denied.
   * @throws ClassNotFoundException
   *     If the entity class is not found.
   */
  public static WSResult handleSimSearch(
      Map<String, String> requestParams) throws JSONException, NoSuchFieldException, IllegalAccessException, ClassNotFoundException {
    String searchTerm = requestParams.get("searchTerm");
    String entityName = requestParams.get("entityName");
    Result result = new Result(searchTerm, entityName);
    int qtyResults = Integer.parseInt(requestParams.getOrDefault("qtyResults", "1"));
    String minSimmilarityPercent = requestParams.getOrDefault("minSimPercent", String.valueOf(MIN_SIM_PERCENT));

    WSResult wsResult = new WSResult();
    JSONArray arrayResponse;
    String whereOrderByClause2 = String.format(
        " as p where  etcotp_sim_search(:tableName, p.id, :searchTerm) > %s order by etcotp_sim_search(:tableName, p.id, :searchTerm) desc ",
        Integer.parseInt(minSimmilarityPercent));
    Set<Entity> readableEntities = OBContext.getOBContext().getEntityAccessChecker().getReadableEntities();
    Entity entity = readableEntities.stream().filter(e -> e.getName().equals(entityName)).findFirst().orElse(
        null);
    if (entity == null) {
      wsResult.setStatus(Status.UNPROCESSABLE_ENTITY);
      wsResult.setMessage("Entity not found or not readable");
      return wsResult;
    }
    Class<? extends BaseOBObject> entityClass = Class.forName(entity.getClassName()).asSubclass(BaseOBObject.class);
    arrayResponse = searchEntities(whereOrderByClause2, result.searchTerm, qtyResults,
        entityClass, entity.getTableName()
    );
    wsResult.setStatus(Status.OK);
    wsResult.setData(arrayResponse);
    return wsResult;
  }

  /**
   * This is a helper class used to encapsulate the search term and entity name into a single object.
   * It is used in the handleSimSearch method to simplify the handling of these two parameters.
   */
  private static class Result {
    /**
     * The search term to be used in the similarity search.
     */
    public final String searchTerm;

    /**
     * The name of the entity to be searched for similarity.
     */
    public final String entityName;

    /**
     * Constructs a new Result object with the specified search term and entity name.
     *
     * @param searchTerm
     *     The search term to be used in the similarity search.
     * @param entityName
     *     The name of the entity to be searched for similarity.
     */
    public Result(String searchTerm, String entityName) {
      this.searchTerm = searchTerm;
      this.entityName = entityName;
    }
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
      String searchTerm, int qtyResults, Class<T> entityClass, String tableName) throws JSONException {

    OBQuery<T> searchQuery = OBDal.getInstance().createQuery(entityClass, whereOrderByClause2);

    searchQuery.setNamedParameter("tableName", StringUtils.lowerCase(tableName));
    searchQuery.setNamedParameter("searchTerm", searchTerm);
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
   * Calculates the similarity percentage between a provided ID and a search term for a specific table.
   *
   * @param id
   *     The ID of the entity.
   * @param searchTerm
   *     The search term to compare against.
   * @param tableName
   *     The name of the table where the entity belongs.
   * @return The similarity percentage as a BigDecimal.
   */
  private static BigDecimal calcSimilarityPercent(String id, String searchTerm, String tableName) {
    String sql = String.format("select etcotp_sim_search('%s', '%s', '%s')", tableName, id, searchTerm);
    Query query = OBDal.getInstance().getSession().createSQLQuery(sql);
    ScrollableResults scroll = query.scroll(ScrollMode.FORWARD_ONLY);
    scroll.next();
    BigDecimal percent = (BigDecimal) scroll.get(0);
    return percent.setScale(4, RoundingMode.HALF_UP);
  }

}
