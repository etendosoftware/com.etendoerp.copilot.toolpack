package com.etendoerp.copilot.toolpack.webhooks;

import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.util.Arrays;
import java.util.Map;
import java.util.stream.Collectors;

import org.apache.commons.lang.StringUtils;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;
import org.codehaus.jettison.json.JSONArray;
import org.openbravo.base.exception.OBException;
import org.openbravo.dal.core.OBContext;
import org.openbravo.dal.service.OBDal;
import org.openbravo.erpCommon.utility.OBMessageUtils;

import com.etendoerp.webhookevents.services.BaseWebhookService;

/**
 * The ExecSQL class handles the execution of SQL queries received through a webhook and returns the result in JSON format.
 * It also provides optional security checks on the query before execution.
 */
public class ExecSQL extends BaseWebhookService {

  private static final Logger log = LogManager.getLogger();
  public static final String DO_SECURITY_CHECK = "doSecurityCheck";

  /**
   * Executes an SQL query received in the parameter map and stores the result in the response map.
   * The result is returned in JSON format, including the executed query, columns, and data.
   * If a security check is requested, it modifies the query to include security constraints.
   *
   * @param parameter    a map of parameters, including the SQL query and security flag
   * @param responseVars a map to store the response, including query result and potential errors
   */
  @Override
  public void get(Map<String, String> parameter, Map<String, String> responseVars) {
    logIfDebug("Executing process");
    for (Map.Entry<String, String> entry : parameter.entrySet()) {
      logIfDebug(String.format("Parameter: %s = %s", entry.getKey(), entry.getValue()));
    }

    String query = parameter.get("Query");
    String security = parameter.get("SecurityCheck");

    Connection conn = OBDal.getInstance().getConnection();

    logIfDebug(query);
    if (StringUtils.equalsIgnoreCase(security, "true")) {
      query = parseSecurity(query);
      logIfDebug(String.format("Query after security check: %s", query));
    }
    try (PreparedStatement statement = conn.prepareStatement(query)) {
      ResultSet result = statement.executeQuery();

      // Prepare the response as a JSON object
      int columnCount = result.getMetaData().getColumnCount();
      JSONArray columns = new JSONArray();
      for (int i = 1; i <= columnCount; i++) {
        columns.put(result.getMetaData().getColumnName(i));
      }
      JSONArray data = new JSONArray();
      while (result.next()) {
        JSONArray row = new JSONArray();
        for (int i = 1; i <= columnCount; i++) {
          row.put(result.getString(i));
        }
        data.put(row);
      }
      responseVars.put("queryExecuted", query);
      responseVars.put("columns", columns.toString());
      responseVars.put("data", data.toString());
    } catch (Exception e) {
      responseVars.put("error", e.getMessage());
    }
  }

  /**
   * Logs a message in debug mode if debug logging is enabled.
   *
   * @param s the message to be logged
   */
  private void logIfDebug(String s) {
    if (log.isDebugEnabled()) {
      log.debug(s);
    }
  }

  /**
   * Adds security checks to the provided query by replacing any security check placeholders
   * with the actual conditions to enforce user access control.
   *
   * @param query the SQL query to be checked and modified
   * @return the query with the security check applied
   * @throws OBException if no security check is found in the query
   */
  private String parseSecurity(String query) {
    if (StringUtils.containsIgnoreCase(query, "checkReadableEntities(t)")) {
      String tables = OBContext.getOBContext().getEntityAccessChecker().getWritableEntities().stream().map(
          e -> String.format("'%s'", e.getTableId())
      ).collect(Collectors.joining(",", "(", ")"));
      String whereCheck = String.format(" t.ad_table_id in %s", tables);
      return StringUtils.replace(query, "checkReadableEntities(t)", whereCheck);
    }
    if (!StringUtils.contains(query, DO_SECURITY_CHECK)) {
      throw new OBException(OBMessageUtils.messageBD("ETCOPTP_NoSecurityCheck"));
    }
    while (StringUtils.contains(query, DO_SECURITY_CHECK)) {
      int start = StringUtils.indexOf(query, DO_SECURITY_CHECK);
      int end = StringUtils.indexOf(query, ")", start);
      String alias = StringUtils.substring(query, start + 16, end);
      query = StringUtils.replace(query, DO_SECURITY_CHECK + "(" + alias + ")", getSecurityCheck(alias));
    }
    return query;
  }

  /**
   * Returns the security condition based on the user's readable clients and organizations.
   *
   * @param alias the alias of the table for which the security check applies
   * @return the SQL condition to enforce security for the specified alias
   */
  private String getSecurityCheck(String alias) {
    String[] cliList = OBContext.getOBContext().getReadableClients();
    String[] orgList = OBContext.getOBContext().getReadableOrganizations();
    String cliSet = getJoin(cliList);
    String orgSet = getJoin(orgList);
    return String.format(" %s.ad_client_id IN (%s) AND %s.ad_org_id IN (%s) ", alias, cliSet, alias, orgSet);
  }

  /**
   * Joins an array of strings into a single string, with each element quoted and separated by commas.
   *
   * @param strList the array of strings to join
   * @return a comma-separated string of quoted elements
   */
  private String getJoin(String[] strList) {
    return Arrays.stream(strList).map(s -> String.format("'%s'", s)).collect(Collectors.joining(","));
  }
}
