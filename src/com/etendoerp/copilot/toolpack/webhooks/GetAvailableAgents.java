package com.etendoerp.copilot.toolpack.webhooks;

import java.util.Map;

import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;
import org.openbravo.erpCommon.utility.OBMessageUtils;

import com.etendoerp.copilot.rest.RestServiceUtil;
import com.etendoerp.webhookevents.services.BaseWebhookService;

/**
 * Webhook service that retrieves available copilot agents/assistants.
 *
 * This service extends BaseWebhookService and provides functionality to fetch
 * the list of available agents through the REST service utility. The response
 * includes agent information that can be used by the copilot system.
 *
 * @author Etendo Software
 */
public class GetAvailableAgents extends BaseWebhookService {
  private static final Logger LOG = LogManager.getLogger();
  private static final String AGENTS = "agents";

  @Override
  public void get(Map<String, String> parameter, Map<String, String> responseVars) {
    LOG.debug("Executing WebHook: GetAvailableAgents");
    // Uses the provided utility function to get the available agents
    try {
      responseVars.put(AGENTS, RestServiceUtil.handleAssistants().toString());
    } catch (Exception e) {
      LOG.error("Error fetching available agents", e);

      responseVars.put("error", OBMessageUtils.messageBD("ETCOPTP_GetAvailAgentErr"));
    }
  }
}
