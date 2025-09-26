package com.etendoerp.copilot.toolpack.webhooks;

import java.util.Map;

import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import com.etendoerp.webhookevents.services.BaseWebhookService;
import com.etendoerp.copilot.rest.RestServiceUtil;

public class GetAvailableAgents extends BaseWebhookService {
    private static final Logger LOG = LogManager.getLogger();
    private static final String AGENTS = "agents";

    @Override
    public void get(Map<String, String> parameter, Map<String, String> responseVars) {
        LOG.debug("Executing WebHook: GetAvailableAgents");
        // Utiliza la función utilitaria proporcionada para obtener los agentes disponibles
        try {
            responseVars.put(AGENTS, RestServiceUtil.handleAssistants().toString());
        } catch(Exception e) {
            LOG.error("Error fetching available agents", e);
            responseVars.put("error", e.getMessage());
        }
    }
}
