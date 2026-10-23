package com.etendoerp.copilot.toolpack.tools;

import java.util.Date;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

import javax.enterprise.context.ApplicationScoped;
import javax.inject.Named;

import org.codehaus.jettison.json.JSONException;
import org.codehaus.jettison.json.JSONObject;
import org.hibernate.criterion.Restrictions;
import org.openbravo.dal.service.OBCriteria;
import org.openbravo.dal.service.OBDal;

import com.etendoerp.copilot.engine.tool.ServerTool;
import com.etendoerp.copilot.engine.tool.ToolExecutionContext;
import com.etendoerp.copilot.engine.tool.http.WebhookInvoker;
import com.etendoerp.etendorx.data.ETRXTokenInfo;

import dev.langchain4j.agent.tool.ToolSpecification;

/** Loads the current OAuth access token into per-question tool context under an alias. */
@ApplicationScoped
@Named("LoadOAuthTokenTool")
public class LoadOAuthTokenTool implements ServerTool {

  private static final String DESCRIPTION = "This tool loads an OAuth token and returns a message indicating the alias which was used to load the token.";

  @Override
  public String name() {
    return "LoadOAuthTokenTool";
  }

  @Override
  public ToolSpecification specification() {
    return FileToolSupport.spec(name(), DESCRIPTION,
        "{\"al\":{\"anyOf\":[{\"type\":\"string\"},{\"type\":\"null\"}],\"default\":null,\"title\":\"Al\",\"description\":\"Alias of the OAuth token to load. If not provided, the default alias will be used. Only set if you want to use a specific alias.\"}}");
  }

  @Override
  public String execute(JSONObject args, ToolExecutionContext ctx) throws Exception {
    try {
      String alias = args == null ? null : args.optString("al", null);
      if (alias == null) {
        alias = "TOKEN_" + UUID.randomUUID();
      }
      // Retain the Python webhook's role grant, while doing its token lookup directly through DAL.
      WebhookInvoker.authorize(ctx, "ReadOAuthToken");
      OBCriteria<ETRXTokenInfo> criteria = OBDal.getInstance().createCriteria(ETRXTokenInfo.class);
      criteria.setMaxResults(1);
      criteria.add(Restrictions.ge(ETRXTokenInfo.PROPERTY_VALIDUNTIL, new Date()));
      criteria.add(Restrictions.ilike(ETRXTokenInfo.PROPERTY_MIDDLEWAREPROVIDER, "%drive%"));
      ETRXTokenInfo found = (ETRXTokenInfo) criteria.uniqueResult();
      if (found == null || found.getToken() == null) {
        return error("Error loading OAuth token: No OAuth token found. Error message:{\"token\":null}");
      }
      Map<String, Object> tokens = tokenMap(ctx);
      tokens.put(alias, Map.of("token", found.getToken()));
      String message = "OAuth token loaded successfully with alias: " + alias
          + ". You can now use this alias to access the token.";
      return new JSONObject().put("message", message).toString();
    } catch (Exception e) {
      return error("Error loading OAuth token: " + (e.getMessage() == null ? e.getClass().getSimpleName() : e.getMessage()));
    }
  }

  @SuppressWarnings("unchecked")
  private static Map<String, Object> tokenMap(ToolExecutionContext ctx) {
    Object stored = ctx.attributes().computeIfAbsent("oauth_tokens", key -> new ConcurrentHashMap<String, Object>());
    if (!(stored instanceof Map<?, ?>)) {
      throw new IllegalStateException("OAuth token context has an invalid format.");
    }
    return (Map<String, Object>) stored;
  }

  private static String error(String value) throws JSONException {
    return new JSONObject().put("error", value).toString();
  }
}
