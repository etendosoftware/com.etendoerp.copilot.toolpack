package com.etendoerp.copilot.toolpack.webhooks;

import java.util.Calendar;
import java.util.Date;
import java.util.Map;

import org.hibernate.criterion.Restrictions;
import org.openbravo.dal.service.OBDal;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import com.etendoerp.etendorx.data.ETRXTokenInfo;
import com.etendoerp.webhookevents.services.BaseWebhookService;

/**
 * Webhook service for performing similarity searches.
 * similarity search requests based on provided parameters.
 */
public class ReadOAuthToken extends BaseWebhookService {

  private static final Logger LOG = LoggerFactory.getLogger(ReadOAuthToken.class);
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
    responseVars.put("token", getToken());
  }

  private String getToken() {
    var crit = OBDal.getInstance().createCriteria(ETRXTokenInfo.class);
    crit.setMaxResults(1);
    crit.add(Restrictions.le(ETRXTokenInfo.PROPERTY_VALIDUNTIL, new Date()));
    crit.add(Restrictions.ilike(ETRXTokenInfo.PROPERTY_MIDDLEWAREPROVIDER, "%drive%"));
    ETRXTokenInfo res = (ETRXTokenInfo) crit.uniqueResult();
    if (res == null) {
      LOG.error("No OAuth token found in the database. Try to create one.");
      return null;
    }
    return res.getToken();
  }


}
