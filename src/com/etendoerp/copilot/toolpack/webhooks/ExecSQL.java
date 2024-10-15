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

public class ExecSQL extends BaseWebhookService {

  private static final Logger log = LogManager.getLogger();
  public static final String DO_SECURITY_CHECK = "doSecurityCheck";

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
      String format = String.format("Query after security check: %s", query);
      logIfDebug(format);
    }
    try (PreparedStatement statement = conn.prepareStatement(query)) {


      ResultSet result = statement.executeQuery();
      //we will return the result as a JSON object

      //get the columns names
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

  private void logIfDebug(String s) {
    if (log.isDebugEnabled()) {
      log.debug(s);
    }
  }

  private String parseSecurity(String query) {
    // the query will have portions where said "doSecurityCheck(x)" and we will replace them with the actual security check,
    //being x the alias of the table. this can be more than one time for different aliases
    if (StringUtils.containsIgnoreCase(query, "checkReadableEntities(t)")) {
      String tables = OBContext.getOBContext().getEntityAccessChecker().getWritableEntities().stream().map(
          e -> String.format("'%s'", e.getTableId())
      ).collect(Collectors.joining(",", "(", ")"));
      String whereCheck = String.format(" t.ad_table_id in %s", tables);
      return StringUtils.replace(query, "checkReadableEntities(t)", whereCheck);
    }
    if (!StringUtils.contains(query, DO_SECURITY_CHECK)) {
      throw new OBException(OBMessageUtils.messageBD("ETCOPDB_NoSecurityCheck"));
    }
    while (StringUtils.contains(query, DO_SECURITY_CHECK)) {
      int start = StringUtils.indexOf(query, DO_SECURITY_CHECK);
      int end = StringUtils.indexOf(query, ")", start);
      String alias = StringUtils.substring(query, start + 16, end);
      query = StringUtils.replace(query, DO_SECURITY_CHECK + "(" + alias + ")", getSecurityCheck(alias));
    }
    return query;
  }

  private String getSecurityCheck(String alias) {
    //this is a dummy implementation, in a real implementation we would check the security of the user
    String[] cliList = OBContext.getOBContext().getReadableClients();
    String[] orgList = OBContext.getOBContext().getReadableOrganizations();
    String cliSet = getJoin(cliList);
    String orgSet = getJoin(orgList);
    return String.format(" %s.ad_client_id IN (%s) AND %s.ad_org_id IN (%s) ", alias,
        cliSet, alias, orgSet);


  }

  private String getJoin(String[] strList) {
    return Arrays.stream(strList).map(s -> String.format("'%s'", s)).collect(Collectors.joining(","));
  }

}


